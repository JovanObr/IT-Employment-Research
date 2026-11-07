"""Like-for-like checks against published studies (milestone 2). Each test copies the method of a study in the
"Case studies vs. our findings" doc, so our numbers can be set beside theirs.

1. stock_by_share       Worrell et al. (1991), Eshghi & Astvansh (2024): do bigger layoffs (share of staff) move the share
                        price more? Same event study, events split by the share of the workforce laid off.
2. within_firm_model    Weingarden (2017): does falling revenue raise the chance of a layoff WITHIN a firm? Linear
                        probability model with firm and quarter fixed effects, so company size (which barely changes
                        within a firm) no longer drives the result. Standard errors clustered by firm.
3. headcount_overhiring Srivastava et al. (2023): did firms that hired fastest in 2019-2021 cut later? Employee counts
                        from 10-K filings (collectors/sec_headcount.py); two outcomes: a tracker layoff 2022-2023, and
                        the 10-K headcount change 2022 -> 2023, which does not depend on the tracker at all.
4. challenger_compare   Our people totals (US companies in the tracker) beside the Challenger, Gray & Christmas counts
                        of US technology job cuts.

    python -m analysis.comparisons            # prints all four; reads local files only
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from analysis import causes as cs
from collectors.common import PROCESSED, RAW

log = logging.getLogger("covid_it_data")

# ---------------------------------------------------------------------------------------- 1. stock reaction by layoff share
SHARE_BINS = (0, 0.05, 0.10, 0.20, 1.0)
SHARE_LABELS = ("do 5 %", "5-10 %", "10-20 %", "nad 20 %")


def event_layoff_size(layoffs: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Per (cik, announcement day): share of staff laid off (0-1, largest stated that day) and people laid off (sum).
    Missing when the tracker does not say."""
    e = layoffs.merge(matches[["layoffs_company", "cik"]].dropna(), left_on="company", right_on="layoffs_company")
    e = e.dropna(subset=["date"]).assign(date=lambda x: pd.to_datetime(x["date"]).dt.normalize(),
                                         share=lambda x: cs.parse_share(x["percentage_laid_off"]))
    return (e.groupby(["cik", "date"]).agg(share=("share", "max"), people=("total_laid_off", lambda s: s.sum(min_count=1)))
            .reset_index())


def add_share_groups(cars: pd.DataFrame, size: pd.DataFrame) -> pd.DataFrame:
    d = cars.assign(date=pd.to_datetime(cars["date"]).dt.normalize()).merge(size, on=["cik", "date"], how="left")
    d["share_group"] = pd.cut(d["share"], SHARE_BINS, labels=SHARE_LABELS, include_lowest=False).astype(str)
    d.loc[d["share"].isna(), "share_group"] = "ni podatka"
    d["share_big"] = np.where(d["share"].isna(), "ni podatka", np.where(d["share"] > 0.10, "nad 10 %", "do 10 %"))
    return d


def stock_by_share(cars: pd.DataFrame, size: pd.DataFrame, n_boot: int = 2000) -> dict:
    """CAR (days 0..+1) per share group, and big (> 10 %) minus small (<= 10 %) with a day-clustered bootstrap interval.
    Also a rank correlation between share and CAR over the events with a stated share."""
    from analysis import event_study as es
    d = add_share_groups(cars, size)
    known = d.dropna(subset=["share", "car_ann_0_1"])
    rho = float(known["share"].rank().corr(known["car_ann_0_1"].rank())) if len(known) > 2 else np.nan
    rng = np.random.default_rng(0)
    perm = np.array([known["share"].rank().corr(pd.Series(rng.permutation(known["car_ann_0_1"].rank().to_numpy()), index=known.index))
                     for _ in range(2000)]) if len(known) > 2 else np.array([np.nan])
    return {"events": d, "by_group": es.group_summary(d, "share_group", n_boot=n_boot),
            "by_big": es.group_summary(d, "share_big", n_boot=n_boot),
            "diff_big_minus_small": es.group_difference(d, "share_big", "nad 10 %", "do 10 %", n_boot=n_boot),
            "spearman": rho, "spearman_p": float((np.abs(perm) >= abs(rho)).mean()), "n_known": len(known)}


# ---------------------------------------------------------------------------------------- 2. within-firm model
WITHIN_FEATURES = ("rev_yoy", "rev_qoq", "op_margin", "net_loss", "cash_assets", "log_assets")


def two_way_demean(df: pd.DataFrame, cols, a: str, b: str, tol: float = 1e-10, max_iter: int = 500) -> pd.DataFrame:
    """Remove firm (a) and quarter (b) means from `cols` on an unbalanced panel by alternating projections."""
    x = df[list(cols)].astype(float).copy()
    for _ in range(max_iter):
        prev = x.to_numpy().copy()
        x = x - x.groupby(df[a]).transform("mean")
        x = x - x.groupby(df[b]).transform("mean")
        if np.max(np.abs(x.to_numpy() - prev)) < tol:
            break
    return x


def ols_cluster(X: np.ndarray, y: np.ndarray, groups: np.ndarray, dof_absorbed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """OLS coefficients and cluster-robust standard errors (CR1, as in Stata's vce(cluster))."""
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    u = y - X @ beta
    G = len(np.unique(groups))
    meat = np.zeros((k, k))
    for g in np.unique(groups):
        s = X[groups == g].T @ u[groups == g]
        meat += np.outer(s, s)
    c = G / (G - 1) * (n - 1) / max(n - k - dof_absorbed, 1)
    V = c * xtx_inv @ meat @ xtx_inv
    return beta, np.sqrt(np.clip(np.diag(V), 0, None))


def within_firm_model(panel: pd.DataFrame, features=WITHIN_FEATURES, label: str = "y_next2q") -> pd.DataFrame:
    """Linear probability model of `label` on standardised, winsorised features. Two versions:
    'quarter FE' (compares firms with each other, like our earlier models) and 'firm + quarter FE' (compares each firm
    with itself in other quarters). Coefficients are percentage points of probability per 1 standard deviation, or for a
    0/1 feature (net_loss, rev_decline) the gap in points between 1 and 0."""
    panel = panel.assign(rev_decline=(panel["rev_yoy"] < 0).astype(float).where(panel["rev_yoy"].notna()))
    d = panel.dropna(subset=list(features) + [label]).copy()
    for c in features:                                     # 0/1 features stay 0/1: their coefficient is the gap in points
        if d[c].nunique() > 2:
            d[c] = cs._winsor(d[c])
            d[c] = (d[c] - d[c].mean()) / d[c].std()
    y = d[label].astype(float)
    rows = []
    for name, firm_fe in (("med podjetji (FE četrtletja)", False), ("znotraj podjetja (FE podjetja + četrtletja)", True)):
        if firm_fe:
            Z = two_way_demean(d.assign(_y=y), list(features) + ["_y"], "cik", "qi")
            X, yy = Z[list(features)].to_numpy(), Z["_y"].to_numpy()
        else:
            X = (d[list(features)] - d[list(features)].groupby(d["qi"]).transform("mean")).to_numpy()
            yy = (y - y.groupby(d["qi"]).transform("mean")).to_numpy()
        beta, se = ols_cluster(X, yy, d["cik"].to_numpy())
        varying = d.groupby("cik")[label].agg(lambda s: s.nunique() > 1)
        for f, b, s in zip(features, beta, se):
            rows.append({"model": name, "feature": f, "pp_effect": 100 * b, "ci_lo": 100 * (b - 1.96 * s), "ci_hi": 100 * (b + 1.96 * s),
                         "p": float(2 * (1 - _norm_cdf(abs(b / s)))) if s > 0 else np.nan, "rows": len(d),
                         "firms": d["cik"].nunique(), "firms_with_variation": int(varying.sum()) if firm_fe else d["cik"].nunique(),
                         "base_rate": float(y.mean())})
    return pd.DataFrame(rows)


def _norm_cdf(z: float) -> float:
    from math import erf, sqrt
    return 0.5 * (1 + erf(z / sqrt(2)))


# ---------------------------------------------------------------------------------------- 3. headcount and over-hiring
def headcount_table(heads: pd.DataFrame, max_jump: float = np.log(10)) -> pd.DataFrame:
    """One row per company: employees per period year, hiring growth 2019 -> 2021 and the change 2022 -> 2023 (log).
    A year-on-year jump of more than 10x is treated as a parsing error and blanked."""
    h = heads.dropna(subset=["employees"]).drop_duplicates(["cik", "period_year"], keep="last")
    w = h.pivot(index="cik", columns="period_year", values="employees")
    w.columns = [f"emp_{c}" for c in w.columns]
    for c in ("emp_2019", "emp_2021", "emp_2022", "emp_2023"):
        if c not in w:
            w[c] = np.nan
    w["hire_growth"] = np.log(w["emp_2021"] / w["emp_2019"])
    w["cut_22_23"] = np.log(w["emp_2023"] / w["emp_2022"])
    w["chg_21_23"] = np.log(w["emp_2023"] / w["emp_2021"])
    for c in ("hire_growth", "cut_22_23", "chg_21_23"):
        w.loc[w[c].abs() > max_jump, c] = np.nan
    return w.reset_index()


def headcount_overhiring(heads: pd.DataFrame, boom: pd.DataFrame, n_boot: int = 500) -> dict:
    """`boom`: causes.run_h3(...)['used'] (tech companies, tracker outcome 2022-2023, size at the start).
    Outcome A: tracker layoff 2022-2023 (quartiles, AUC, size-controlled logit, as in H3).
    Outcome B: did the 10-K headcount fall from 2022 to 2023, and by how much (independent of the tracker)."""
    w = headcount_table(heads)
    d = boom.merge(w, on="cik", how="inner").dropna(subset=["hire_growth"])
    out = {"table": d, "n": len(d), "n_layoff": int(d["y_layoff"].sum()) if len(d) else 0}
    if len(d) >= 20 and 0 < d["y_layoff"].sum() < len(d):
        out["quartiles"] = cs.quartile_table(d, "hire_growth")
        out["auc"] = cs.univariate_auc(d, ["hire_growth", "boom_growth"], n_boot=n_boot)
        out["logit"] = cs.controlled_logit(d, ["hire_growth"], n_boot=n_boot)
    b = d.dropna(subset=["cut_22_23"])
    if len(b) >= 20:
        rng = np.random.default_rng(0)
        rho = lambda x: x["hire_growth"].rank().corr(x["cut_22_23"].rank())
        boots = [rho(b.iloc[rng.integers(0, len(b), len(b))]) for _ in range(n_boot)]
        q = pd.qcut(b["hire_growth"], 4, labels=["Q1 najmanj", "Q2", "Q3", "Q4 največ"])
        out["cut"] = {"n": len(b), "spearman": float(rho(b)), "ci_lo": float(np.percentile(boots, 2.5)), "ci_hi": float(np.percentile(boots, 97.5))}
        out["cut_quartiles"] = b.groupby(q, observed=True).agg(
            companies=("cik", "size"), median_hire_growth_pct=("hire_growth", lambda s: 100 * np.expm1(s.median())),
            median_change_22_23_pct=("cut_22_23", lambda s: 100 * np.expm1(s.median())),
            share_cut_5pct=("cut_22_23", lambda s: float((s < np.log(0.95)).mean()))).reset_index().rename(columns={"hire_growth": "quartile"})
        cutters = b[b["cut_22_23"] < 0]
        out["cut_vs_hire"] = {"cutters": len(cutters),
                              "median_cut_pct": float(100 * np.expm1(cutters["cut_22_23"].median())) if len(cutters) else np.nan,
                              "median_prior_growth_pct": float(100 * np.expm1(cutters["hire_growth"].median())) if len(cutters) else np.nan,
                              "share_still_above_2019": float((cutters["emp_2023"] > cutters["emp_2019"]).mean()) if len(cutters) else np.nan}
    return out


# ---------------------------------------------------------------------------------------- 4. Challenger
# Challenger, Gray & Christmas: announced job cuts by US-based employers, Technology sector (verified 2026-11-07).
CHALLENGER = [
    {"period": "2022", "start": "2022-01-01", "end": "2022-12-31", "challenger": 97_171, "url": "https://www.challengergray.com/?p=20395"},
    {"period": "2022-11", "start": "2022-11-01", "end": "2022-11-30", "challenger": 52_771, "url": "https://www.challengergray.com/?p=17169"},
    {"period": "2022Q1", "start": "2022-01-01", "end": "2022-03-31", "challenger": 267, "url": "https://www.challengergray.com/?p=17832"},
    {"period": "2023Q1", "start": "2023-01-01", "end": "2023-03-31", "challenger": 102_391, "url": "https://www.challengergray.com/?p=17832"},
    {"period": "2023", "start": "2023-01-01", "end": "2023-12-31", "challenger": 168_032, "url": "https://www.challengergray.com/?p=20395"},
    {"period": "2024", "start": "2024-01-01", "end": "2024-12-31", "challenger": 133_988, "url": "https://www.challengergray.com/?p=24257"},
    {"period": "2025", "start": "2025-01-01", "end": "2025-12-31", "challenger": 154_445, "url": "https://www.challengergray.com/?p=27592"},
]


def challenger_compare(layoffs: pd.DataFrame, ref=CHALLENGER) -> pd.DataFrame:
    """Tracker people laid off at US companies per Challenger period (a lower bound: many announcements give no number),
    the share of those announcements with a number, the all-country total, and the ratio tracker US / Challenger."""
    e = layoffs.assign(date=pd.to_datetime(layoffs["date"], errors="coerce")).dropna(subset=["date"])
    us = e["country"].astype(str).str.strip().eq("United States")
    rows = []
    for r in ref:
        inside = e["date"].between(pd.Timestamp(r["start"]), pd.Timestamp(r["end"]))
        u = e[inside & us]
        rows.append({"period": r["period"], "challenger": r["challenger"], "tracker_us": float(u["total_laid_off"].sum()),
                     "tracker_us_announcements": len(u), "share_with_number": float(u["total_laid_off"].notna().mean()) if len(u) else np.nan,
                     "tracker_all_countries": float(e[inside]["total_laid_off"].sum()),
                     "ratio_us_to_challenger": float(u["total_laid_off"].sum() / r["challenger"]) if r["challenger"] else np.nan,
                     "source": r["url"]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------- run everything
def _rounded(d: dict) -> dict:
    return {k: round(float(v), 3) if isinstance(v, (float, np.floating)) else v for k, v in d.items()}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    pd.set_option("display.width", 200)
    d = cs.load_inputs()
    log.info("4. Tracker vs Challenger (US technology job cuts):\n%s",
             challenger_compare(d["events"]).drop(columns="source").round(2).to_string(index=False))

    ev_path = PROCESSED / "event_study_events.csv"
    if ev_path.exists():
        cars = pd.read_csv(ev_path, parse_dates=["date", "event_day"])
        s = stock_by_share(cars, event_layoff_size(d["events"], d["matches"]))
        cols = ["n", "mean_pct", "median_pct", "share_positive", "ci_lo_pct", "ci_hi_pct"]
        log.info("1. Stock reaction (days 0..+1) by share of staff laid off:\n%s", s["by_group"][["share_group"] + cols].round(3).to_string(index=False))
        log.info("   %s", s["by_big"][["share_big"] + cols].round(3).to_string(index=False))
        log.info("   bigger (> 10 %%) minus smaller (<= 10 %%): %s", _rounded(s["diff_big_minus_small"]))
        log.info("   rank correlation share vs CAR: %.3f (permutation p = %.3f, %d events with a stated share)", s["spearman"], s["spearman_p"], s["n_known"])
    else:
        log.info("1. skipped: run python -m analysis.event_study first")

    panel = pd.read_csv(PROCESSED / "company_panel.csv", dtype={"sic": str, "sic2": str})
    log.info("2. Within-firm model (percentage points of layoff probability per 1 sd; 0/1 features: gap between 1 and 0):\n%s", within_firm_model(panel).round(3).to_string(index=False))
    log.info("   Weingarden-style: revenue below a year earlier (0/1) instead of revenue growth:\n%s",
             within_firm_model(panel, ("rev_decline", "op_margin", "net_loss", "cash_assets", "log_assets")).round(3).to_string(index=False))

    hp = RAW / "sec_headcount.csv"
    if hp.exists():
        boom = cs.run_h3(d["fin"], d["revenue"], d["universe"], d["matches"], d["events"])["used"]
        h = headcount_overhiring(pd.read_csv(hp), boom)
        log.info("3. Headcount from 10-K: %d companies with 2019 and 2021 headcount (%d with a tracker layoff 2022-2023)", h["n"], h["n_layoff"])
        for k in ("quartiles", "auc", "logit", "cut_quartiles"):
            if k in h:
                log.info("   %s:\n%s", k, h[k].round(3).to_string(index=False))
        for k in ("cut", "cut_vs_hire"):
            if k in h:
                log.info("   %s: %s", k, _rounded(h[k]))
    else:
        log.info("3. skipped: run python collect.py --sources sec_headcount first (about 30-60 min, resumable)")


if __name__ == "__main__":
    main()
