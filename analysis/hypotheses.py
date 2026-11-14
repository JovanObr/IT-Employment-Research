"""Milestone 3, Stream A: the pre-registered tests C and D (docs/hypotheses/PREREGISTRATION.md). Also `holm`, used to combine
all four primary p-values (A and B come from Stream B).

C  Do announced layoffs show up in headcount?   Mann-Whitney U on log(employees 2023 / 2021), announced vs. not.
D  Repeat announcements and the stock price.    Permutation test on the mean abnormal return (days 0..+1), repeat - first.

Every function follows the registration exactly; do not change a test, a sample rule or a threshold without adding a dated
amendment to the registration first.

    python -m analysis.hypotheses            # runs C and D on the local files, prints and writes reports/hypotheses_a_results.json
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

log = logging.getLogger("covid_it_data")
ALPHA = 0.05
C_WINDOW = (2021, 2023)
C_EXPOSURE = ("2022-01-01", "2023-12-31")
D_EARLY_CUTOFF = "2020-09-11"


# ---------------------------------------------------------------------------------------- shared
def holm(pvalues: dict[str, float], alpha: float = ALPHA) -> pd.DataFrame:
    """Holm step-down adjusted p-values for one family. Returns hypothesis, p, p_holm, reject (at alpha)."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m, running, rows = len(items), 0.0, []
    for i, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        rows.append({"hypothesis": name, "p": p, "p_holm": running, "reject": running < alpha})
    return pd.DataFrame(rows)


def file_hashes(paths) -> dict[str, str]:
    """SHA-256 of each input file, recorded with the results (the registration freezes the inputs)."""
    out = {}
    for p in paths:
        p = Path(p)
        out[str(p).replace("\\", "/")] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"
    return out


def mde(sd: float, n1: int, n0: int, alpha: float = ALPHA, power: float = 0.8) -> float:
    """Minimum detectable difference in means for two groups (normal approximation)."""
    return float((stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * sd * np.sqrt(1 / n1 + 1 / n0))


def _winsor(s: pd.Series, p: float = 0.01) -> pd.Series:
    return s.clip(s.quantile(p), s.quantile(1 - p))


# ---------------------------------------------------------------------------------------- C. announced layoffs and headcount
def announced_ciks(layoffs: pd.DataFrame, matches: pd.DataFrame, window=C_EXPOSURE) -> set[int]:
    e = layoffs.merge(matches[["layoffs_company", "cik"]].dropna(), left_on="company", right_on="layoffs_company")
    d = pd.to_datetime(e["date"], errors="coerce")
    return {int(c) for c in e.loc[d.between(pd.Timestamp(window[0]), pd.Timestamp(window[1])), "cik"]}


def headcount_sample(heads: pd.DataFrame, universe: pd.DataFrame, announced: set[int], panel: pd.DataFrame | None = None,
                     years=C_WINDOW, max_jump: float = np.log(10)) -> pd.DataFrame:
    """One row per tech company with a headcount in both years: outcome log(emp_end / emp_start), announced (0/1),
    size (last log_assets of the start year in the company panel) and 3-digit SIC group."""
    h = heads.dropna(subset=["employees"]).drop_duplicates(["cik", "period_year"], keep="last")
    w = h.pivot(index="cik", columns="period_year", values="employees")
    y0, y1 = years
    if y0 not in w or y1 not in w:
        return pd.DataFrame(columns=["cik", "outcome", "announced", "log_assets", "sic3"])
    d = pd.DataFrame({"outcome": np.log(w[y1] / w[y0])}).dropna()
    d = d[d["outcome"].abs() <= max_jump].reset_index()
    tech = universe[universe["is_tech"].astype(str).str.lower().isin(["true", "1"])]
    d = d.merge(tech[["cik", "sic"]].assign(sic3=lambda x: x["sic"].astype(str).str.zfill(4).str[:3])[["cik", "sic3"]], on="cik")
    d["announced"] = d["cik"].isin(announced).astype(int)
    if panel is not None:
        q = panel[panel["quarter"].astype(str).str.startswith(str(y0))].sort_values("qi").groupby("cik")["log_assets"].last()
        d["log_assets"] = d["cik"].map(q)
    return d


def test_c(d: pd.DataFrame, n_boot: int = 5000, seed: int = 0) -> dict:
    """Primary: Mann-Whitney U (two-sided); effect = median(announced) - median(not), 95 % bootstrap interval over companies."""
    a, b = d.loc[d["announced"] == 1, "outcome"].to_numpy(), d.loc[d["announced"] == 0, "outcome"].to_numpy()
    u = stats.mannwhitneyu(a, b, alternative="two-sided")
    rng = np.random.default_rng(seed)
    boots = [np.median(rng.choice(a, len(a))) - np.median(rng.choice(b, len(b))) for _ in range(n_boot)]
    diff = float(np.median(a) - np.median(b))
    return {"n_announced": len(a), "n_not": len(b), "median_announced": float(np.median(a)), "median_not": float(np.median(b)),
            "diff_median": diff, "ci_lo": float(np.percentile(boots, 2.5)), "ci_hi": float(np.percentile(boots, 97.5)),
            "p": float(u.pvalue), "predicted_sign": diff < 0, "mde_log": mde(float(d["outcome"].std()), len(a), len(b))}


def ols_hc3(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OLS coefficients and HC3 standard errors (X includes the constant)."""
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    u = y - X @ beta
    h = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    meat = (X * (u / np.clip(1 - h, 1e-12, None))[:, None] ** 2).T @ X
    return beta, np.sqrt(np.clip(np.diag(xtx_inv @ meat @ xtx_inv), 0, None))


def secondary_c(d: pd.DataFrame) -> dict:
    """OLS of the outcome on announced + log assets + SIC 3-digit dummies, HC3 errors (rows without size are dropped)."""
    x = d.dropna(subset=["log_assets"]) if "log_assets" in d else d.iloc[0:0]
    if len(x) < 20:
        return {"n": len(x)}
    dum = pd.get_dummies(x["sic3"], prefix="sic", drop_first=True, dtype=float)
    X = np.column_stack([np.ones(len(x)), x["announced"], x["log_assets"], dum.to_numpy()])
    b, se = ols_hc3(x["outcome"].to_numpy(float), X)
    return {"n": len(x), "coef_announced": float(b[1]), "ci_lo": float(b[1] - 1.96 * se[1]), "ci_hi": float(b[1] + 1.96 * se[1]),
            "p": float(2 * (1 - stats.norm.cdf(abs(b[1] / se[1])))) if se[1] > 0 else np.nan}


def placebo_c(d: pd.DataFrame, n_rep: int = 1000, seed: int = 0) -> dict:
    """Shuffle the announced label across companies; share of shuffles where the primary test rejects at 0.05."""
    rng = np.random.default_rng(seed)
    y, lab = d["outcome"].to_numpy(), d["announced"].to_numpy()
    rej = [stats.mannwhitneyu(y[l == 1], y[l == 0]).pvalue < ALPHA for l in (rng.permutation(lab) for _ in range(n_rep))]
    return {"n_rep": n_rep, "false_positive_rate": float(np.mean(rej))}


# ---------------------------------------------------------------------------------------- D. repeat announcements
def label_repeat(cars: pd.DataFrame, layoffs: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """repeat = 1 if the company (CIK) has a tracker announcement on an earlier date (all tracker rows count)."""
    e = layoffs.merge(matches[["layoffs_company", "cik"]].dropna(), left_on="company", right_on="layoffs_company")
    first = pd.to_datetime(e["date"], errors="coerce").groupby(e["cik"]).min()
    out = cars.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["repeat"] = (out["date"] > out["cik"].map(first).dt.normalize()).astype(int)
    return out


def perm_diff(values: np.ndarray, labels: np.ndarray, n_perm: int = 10000, seed: int = 0) -> tuple[float, float]:
    """Mean(label 1) - mean(label 0) and its two-sided permutation p-value."""
    rng = np.random.default_rng(seed)
    obs = values[labels == 1].mean() - values[labels == 0].mean()
    n1 = int(labels.sum())
    perms = np.array([rng.permutation(values) for _ in range(n_perm)])
    null = perms[:, :n1].mean(axis=1) - perms[:, n1:].mean(axis=1)
    return float(obs), float((np.sum(np.abs(null) >= abs(obs)) + 1) / (n_perm + 1))


def test_d(cars: pd.DataFrame, n_perm: int = 10000, seed: int = 0) -> dict:
    """Primary: permutation test on the winsorised (1 %/99 %) mean CAR over days 0..+1, repeat - first. In per cent."""
    d = cars.dropna(subset=["car_ann_0_1"])
    v = _winsor(d["car_ann_0_1"]).to_numpy(float)
    lab = d["repeat"].to_numpy(int)
    diff, p = perm_diff(v, lab, n_perm, seed)
    return {"n_repeat": int(lab.sum()), "n_first": int((lab == 0).sum()), "mean_repeat_pct": 100 * float(v[lab == 1].mean()),
            "mean_first_pct": 100 * float(v[lab == 0].mean()), "diff_pct": 100 * diff, "p": p, "predicted_sign": diff < 0,
            "mde_pct": 100 * mde(float(v.std()), int(lab.sum()), int((lab == 0).sum()))}


def secondary_d(cars: pd.DataFrame, n_boot: int = 2000) -> dict:
    from analysis import event_study as es
    d = cars.dropna(subset=["car_ann_0_1"]).copy()
    d["group"] = np.where(d["repeat"] == 1, "repeat", "first")
    w = d.assign(car_ann_0_1=_winsor(d["car_ann_0_1"]))
    boot = es.group_difference(w, "group", "repeat", "first", n_boot=n_boot)
    mw = stats.mannwhitneyu(d.loc[d["repeat"] == 1, "car_ann_0_1"], d.loc[d["repeat"] == 0, "car_ann_0_1"])
    out = {"day_bootstrap": {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in boot.items()},
           "mannwhitney_p_raw": float(mw.pvalue)}
    for name, sub in (("without_first_6_months", d[d["date"] >= pd.Timestamp(D_EARLY_CUTOFF)]), ("without_2020", d[d["date"].dt.year != 2020])):
        r = test_d(sub, n_perm=5000)
        out[name] = {k: r[k] for k in ("n_repeat", "n_first", "diff_pct", "p")}
    return out


def placebo_d(cars: pd.DataFrame, returns: pd.DataFrame, n_rep: int = 100, n_perm: int = 1000, seed: int = 0, exclude_days: int = 10) -> dict:
    """Random non-event days of the same companies, same repeat labels: how often does the primary test reject at 0.05?"""
    from analysis import event_study as es
    rng = np.random.default_rng(seed)
    days = returns[es.BENCH].dropna().index
    rm = returns[es.BENCH].reindex(days).to_numpy(float)
    per = []
    for e in cars.itertuples(index=False):
        if e.ticker not in returns:
            continue
        ri = returns[e.ticker].reindex(days).to_numpy(float)
        real = [es.event_position(x, days) for x in cars.loc[cars["ticker"] == e.ticker, "date"]]
        lo, hi = -es.ESTIMATION[0], len(days) - max(w[1] for w in es.WINDOWS.values()) - 1
        cand = np.array([p for p in range(lo, hi) if all(abs(p - r) > exclude_days for r in real if r is not None)])
        if len(cand):
            per.append((ri, cand, e.repeat))
    rej, diffs = [], []
    for k in range(n_rep):
        v, lab = [], []
        for ri, cand, r in per:
            res = es.cars_at(ri, rm, int(rng.choice(cand)), {"ann_0_1": es.WINDOWS["ann_0_1"]})
            if res is not None and np.isfinite(res["car_ann_0_1"]):
                v.append(res["car_ann_0_1"]); lab.append(r)
        v = _winsor(pd.Series(v)).to_numpy()
        diff, p = perm_diff(v, np.array(lab), n_perm, seed + k)
        rej.append(p < ALPHA); diffs.append(100 * diff)
    return {"n_rep": n_rep, "false_positive_rate": float(np.mean(rej)), "mean_diff_pct": float(np.mean(diffs)), "sd_diff_pct": float(np.std(diffs))}


# ---------------------------------------------------------------------------------------- run
def run(placebo_reps_d: int = 100) -> dict:
    from analysis import causes as cs
    from analysis import event_study as es
    from collectors import sec_headcount as sh
    from collectors.common import PROCESSED, RAW
    inputs = [PROCESSED / "layoffs_clean.csv", RAW / "sec_company_matches.csv", RAW / "sec_headcount.csv", RAW / "sec_universe_sic.csv",
              PROCESSED / "company_panel.csv", PROCESSED / "event_study_events.csv", RAW / "prices_daily.csv"]
    out = {"inputs_sha256": file_hashes(inputs)}
    d = cs.load_inputs()
    panel = pd.read_csv(PROCESSED / "company_panel.csv", dtype={"sic": str, "sic2": str})
    heads = sh.recheck(pd.read_csv(RAW / "sec_headcount.csv"))[0]
    c = headcount_sample(heads, d["universe"], announced_ciks(d["events"], d["matches"]), panel)
    c22 = headcount_sample(heads, d["universe"], announced_ciks(d["events"], d["matches"]), panel, years=(2022, 2023))
    out["C"] = {"primary": test_c(c), "secondary_ols": secondary_c(c), "secondary_2022_2023": test_c(c22) if len(c22) else {},
                "placebo": placebo_c(c)}
    cars = label_repeat(pd.read_csv(PROCESSED / "event_study_events.csv", parse_dates=["date", "event_day"]), d["events"], d["matches"])
    out["D"] = {"primary": test_d(cars), "secondary": secondary_d(cars)}
    if placebo_reps_d:
        returns, _ = es.prepare_returns(pd.read_csv(RAW / "prices_daily.csv", parse_dates=["date"]))
        out["D"]["placebo"] = placebo_d(cars, returns, n_rep=placebo_reps_d)
    return out


def main() -> None:
    import sys
    from analysis.viz_theme import ROOT
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    res = run(placebo_reps_d=reps)
    path = ROOT / "reports" / "hypotheses_a_results.json"
    path.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "inputs_sha256"}, indent=2, default=float))
    print(f"written {path}")


if __name__ == "__main__":
    main()
