"""Round 2, Stream A: the pre-registered tests C2 and E (docs/hypotheses/round2/C2_E.md, registered in commit ad835e5).

C2  Announced layoffs show up in the same year's headcount (t = 2024, 2025 pooled): difference in medians, permutation within year.
E   Layoff announcements cluster within 3 business days of the company's earnings release (8-K item 2.02): observed vs. expected count.

Follow the registration exactly; any change after the real run is a dated amendment in the registration file.

    python -m analysis.hypotheses2_a        # runs C2 and E on the local files, writes reports/hypotheses2_a_results.json
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
from scipy import stats

from analysis.hypotheses import ALPHA, file_hashes, mde

log = logging.getLogger("covid_it_data")
C2_YEARS = (2024, 2025)
E_START, E_END = "2020-03-11", "2026-06-30"
E_WINDOW, E_MIN_RELEASES = 3, 3


# ---------------------------------------------------------------------------------------- C2
def announcements(layoffs: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Tracker announcements of matched companies: one row per (cik, date)."""
    e = layoffs.merge(matches[["layoffs_company", "cik"]].dropna(), left_on="company", right_on="layoffs_company")
    e = e.assign(date=pd.to_datetime(e["date"], errors="coerce").dt.normalize(), cik=lambda x: x["cik"].astype(int)).dropna(subset=["date"])
    return e.drop_duplicates(["cik", "date"])[["cik", "date"]].reset_index(drop=True)


def sample_c2(heads: pd.DataFrame, universe: pd.DataFrame, ann: pd.DataFrame, panel: pd.DataFrame | None = None,
              years=C2_YEARS, max_jump: float = np.log(10)) -> pd.DataFrame:
    """One row per tech company and year t with headcounts for t-1 and t: outcome log(emp_t / emp_t-1), announced in year t (0/1),
    size (last log_assets of year t-1 in the company panel) and SIC 3-digit group."""
    h = heads.dropna(subset=["employees"]).drop_duplicates(["cik", "period_year"], keep="last")
    w = h.pivot(index="cik", columns="period_year", values="employees")
    tech = universe[universe["is_tech"].astype(str).str.lower().isin(["true", "1"])]
    sic3 = tech.set_index("cik")["sic"].astype(str).str.zfill(4).str[:3]
    rows = []
    for t in years:
        if t not in w or t - 1 not in w:
            continue
        d = pd.DataFrame({"outcome": np.log(w[t] / w[t - 1])}).dropna()
        d = d[(d["outcome"].abs() <= max_jump) & d.index.isin(sic3.index)].reset_index()
        anns = set(ann.loc[ann["date"].dt.year == t, "cik"])
        d["year"], d["announced"], d["sic3"] = t, d["cik"].isin(anns).astype(int), d["cik"].map(sic3)
        if panel is not None:
            q = panel[panel["quarter"].astype(str).str.startswith(str(t - 1))].sort_values("qi").groupby("cik")["log_assets"].last()
            d["log_assets"] = d["cik"].map(q)
        rows.append(d)
    cols = ["cik", "outcome", "year", "announced", "sic3", "log_assets"]
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=cols)


def _median_diff(y: np.ndarray, lab: np.ndarray) -> float:
    return float(np.median(y[lab == 1]) - np.median(y[lab == 0]))


def perm_within(y: np.ndarray, lab: np.ndarray, strata: np.ndarray, n_perm: int, rng) -> np.ndarray:
    """Null distribution of the difference in medians, labels shuffled within each stratum (group sizes per stratum kept)."""
    idx = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    out = np.empty(n_perm)
    for k in range(n_perm):
        l2 = lab.copy()
        for i in idx:
            l2[i] = rng.permutation(lab[i])
        out[k] = _median_diff(y, l2)
    return out


def test_c2(d: pd.DataFrame, n_perm: int = 10000, n_boot: int = 5000, seed: int = 0) -> dict:
    """Primary: pooled difference in medians (announced - not), two-sided permutation p shuffling within year; company bootstrap interval."""
    y, lab, yr = d["outcome"].to_numpy(float), d["announced"].to_numpy(int), d["year"].to_numpy()
    rng = np.random.default_rng(seed)
    obs = _median_diff(y, lab)
    null = perm_within(y, lab, yr, n_perm, rng)
    p = float((np.sum(np.abs(null) >= abs(obs)) + 1) / (n_perm + 1))
    groups = {c: g.index.to_numpy() for c, g in d.groupby("cik")}
    keys = np.array(list(groups))
    boots = []
    for _ in range(n_boot):
        rows = np.concatenate([groups[c] for c in rng.choice(keys, len(keys))])
        yy, ll = y[rows], lab[rows]
        if ll.sum() and (ll == 0).sum():
            boots.append(_median_diff(yy, ll))
    return {"n_rows": len(d), "n_companies": int(d["cik"].nunique()), "n_announced": int(lab.sum()), "n_not": int((lab == 0).sum()),
            "by_year": {int(t): {"announced": int(g["announced"].sum()), "not": int((g["announced"] == 0).sum())} for t, g in d.groupby("year")},
            "median_announced": float(np.median(y[lab == 1])), "median_not": float(np.median(y[lab == 0])), "diff_median": obs,
            "ci_lo": float(np.percentile(boots, 2.5)), "ci_hi": float(np.percentile(boots, 97.5)), "p": p, "predicted_sign": obs < 0,
            "mde_log": mde(float(d["outcome"].std()), int(lab.sum()), int((lab == 0).sum()))}


def secondary_c2(d: pd.DataFrame, n_perm: int = 5000) -> dict:
    from analysis.comparisons import ols_cluster
    out = {}
    for t, g in d.groupby("year"):
        r = test_c2(g.reset_index(drop=True), n_perm=n_perm, n_boot=1000)
        out[f"year_{int(t)}"] = {k: r[k] for k in ("n_announced", "n_not", "diff_median", "ci_lo", "ci_hi", "p")}
    mw = stats.mannwhitneyu(d.loc[d["announced"] == 1, "outcome"], d.loc[d["announced"] == 0, "outcome"])
    out["mannwhitney_pooled_p"] = float(mw.pvalue)
    x = d.dropna(subset=["log_assets"]) if "log_assets" in d else d.iloc[0:0]
    if len(x) >= 30:
        dum = pd.get_dummies(x[["sic3", "year"]].astype(str), drop_first=True, dtype=float)
        X = np.column_stack([np.ones(len(x)), x["announced"], x["log_assets"], dum.to_numpy()])
        b, se = ols_cluster(X, x["outcome"].to_numpy(float), x["cik"].to_numpy())
        out["ols"] = {"n": len(x), "coef_announced": float(b[1]), "ci_lo": float(b[1] - 1.96 * se[1]), "ci_hi": float(b[1] + 1.96 * se[1]),
                      "p": float(2 * stats.norm.sf(abs(b[1] / se[1]))) if se[1] > 0 else None}
    return out


def placebo_c2(d: pd.DataFrame, n_rep: int = 500, n_perm: int = 400, seed: int = 1) -> dict:
    """Shuffle the announced label within year, then run the primary test; share of runs with p < 0.05."""
    rng = np.random.default_rng(seed)
    y, lab, yr = d["outcome"].to_numpy(float), d["announced"].to_numpy(int), d["year"].to_numpy()
    rej = 0
    for _ in range(n_rep):
        l2 = lab.copy()
        for s in np.unique(yr):
            i = np.flatnonzero(yr == s)
            l2[i] = rng.permutation(lab[i])
        obs = _median_diff(y, l2)
        null = perm_within(y, l2, yr, n_perm, rng)
        rej += ((np.sum(np.abs(null) >= abs(obs)) + 1) / (n_perm + 1)) < ALPHA
    return {"n_rep": n_rep, "false_positive_rate": rej / n_rep}


# ---------------------------------------------------------------------------------------- E
def earnings_dates(sub: dict) -> list[str]:
    """Filing dates of 8-K filings that list item 2.02 (earnings release), from an SEC submissions reply."""
    r = sub.get("filings", {}).get("recent", {})
    return sorted({d for f, d, it in zip(r.get("form", []), r.get("filingDate", []), r.get("items", [])) if f == "8-K" and "2.02" in str(it)})


def _bday(d) -> np.datetime64:
    return np.busday_offset(np.datetime64(pd.Timestamp(d).date(), "D"), 0, roll="forward")


def window_days(releases, year: int, before: int = E_WINDOW, after: int = E_WINDOW) -> set:
    """Business days of `year` within [-before, +after] business days of any release."""
    out = set()
    for r in releases:
        b = _bday(r)
        for k in range(-before, after + 1):
            day = np.busday_offset(b, k)
            if day.astype("datetime64[Y]").astype(int) + 1970 == year:
                out.add(day)
    return out


def business_days(year: int) -> int:
    return int(np.busday_count(np.datetime64(f"{year}-01-01"), np.datetime64(f"{year + 1}-01-01")))


def event_table(ann: pd.DataFrame, releases: dict[int, list[str]], start=E_START, end=E_END, min_releases: int = E_MIN_RELEASES,
                before: int = E_WINDOW, after: int = E_WINDOW) -> pd.DataFrame:
    """One row per usable announcement: near (0/1) and p (chance of being near if its business day were random within its year)."""
    rows = []
    a = ann[(ann["date"] >= pd.Timestamp(start)) & (ann["date"] <= pd.Timestamp(end))]
    cache = {}
    for e in a.itertuples(index=False):
        d = _bday(e.date)
        y = int(d.astype("datetime64[Y]").astype(int) + 1970)
        rel = [r for r in releases.get(int(e.cik), []) if int(r[:4]) in (y - 1, y, y + 1)]
        if sum(int(r[:4]) == y for r in rel) < min_releases:
            continue
        key = (int(e.cik), y, before, after)
        if key not in cache:
            cache[key] = window_days(rel, y, before, after)
        w = cache[key]
        rows.append({"cik": int(e.cik), "date": pd.Timestamp(str(d)), "year": y, "near": int(d in w), "p": len(w) / business_days(y)})
    return pd.DataFrame(rows, columns=["cik", "date", "year", "near", "p"])


def test_e(t: pd.DataFrame, n_sim: int = 10000, n_boot: int = 5000, seed: int = 0) -> dict:
    """Observed count near a release vs. the count when every announcement moves to a random business day of its own year
    (each is then near with probability p_i). Two-sided simulation p; O / E with a company bootstrap interval."""
    rng = np.random.default_rng(seed)
    p, near = t["p"].to_numpy(float), t["near"].to_numpy(int)
    O, E = int(near.sum()), float(p.sum())
    sims = (rng.random((n_sim, len(p))) < p).sum(axis=1)
    pval = float(min(1.0, 2 * min((np.sum(sims >= O) + 1) / (n_sim + 1), (np.sum(sims <= O) + 1) / (n_sim + 1))))
    groups = {c: g.index.to_numpy() for c, g in t.groupby("cik")}
    keys = np.array(list(groups))
    ratios = []
    for _ in range(n_boot):
        rows = np.concatenate([groups[c] for c in rng.choice(keys, len(keys))])
        ratios.append(near[rows].sum() / p[rows].sum())
    sd = float(np.sqrt((p * (1 - p)).sum()))
    return {"n": len(t), "n_companies": int(t["cik"].nunique()), "observed": O, "expected": E, "ratio": O / E if E else None,
            "ci_lo": float(np.percentile(ratios, 2.5)), "ci_hi": float(np.percentile(ratios, 97.5)), "p": pval, "predicted_sign": O > E,
            "mean_window_share": float(p.mean()), "mde_excess": 2.8 * sd, "mde_ratio": (E + 2.8 * sd) / E if E else None}


def shift_releases(releases: dict[int, list[str]], days: int) -> dict[int, list[str]]:
    return {c: [str((pd.Timestamp(r) + pd.Timedelta(days=days)).date()) for r in rs] for c, rs in releases.items()}


def secondary_e(ann, releases) -> dict:
    out = {}
    # (before, after) in business days around each release; after = -1 means the window ends the day before the release
    for name, b, a in (("after_only_0_3", 0, 3), ("before_only_3_1", 3, -1), ("window_1", 1, 1), ("window_5", 5, 5)):
        r = test_e(event_table(ann, releases, before=b, after=a), n_sim=5000, n_boot=500)
        out[name] = {k: r[k] for k in ("n", "observed", "expected", "ratio", "p")}
    t = event_table(ann, releases, start="2022-01-01", end="2023-12-31")
    r = test_e(t, n_sim=5000, n_boot=500)
    out["years_2022_2023"] = {k: r[k] for k in ("n", "observed", "expected", "ratio", "p")}
    return out


def placebo_e(ann, releases, shifts=(45, -45, 30, -30)) -> dict:
    out = {}
    for s in shifts:
        r = test_e(event_table(ann, shift_releases(releases, s)), n_sim=5000, n_boot=500)
        out[f"shift_{s:+d}"] = {k: r[k] for k in ("n", "observed", "expected", "ratio", "p")}
    out["share_p_below_005"] = float(np.mean([v["p"] < ALPHA for v in out.values() if isinstance(v, dict)]))
    return out


# ---------------------------------------------------------------------------------------- run
def load_releases(ciks) -> dict[int, list[str]]:
    from collectors.common import fetch
    from collectors.sec import SUBMISSIONS
    out = {}
    for c in ciks:
        try:
            out[int(c)] = earnings_dates(json.loads(fetch(SUBMISSIONS.format(cik=int(c)), max_age_days=3650, delay=0.25)))
        except Exception as e:  # noqa: BLE001 - a company without a submissions file has no release calendar
            log.warning("no submissions for %s (%s)", c, e)
    return out


def run() -> dict:
    from analysis import causes as cs
    from collectors import sec_headcount as sh
    from collectors.common import PROCESSED, RAW
    inputs = [PROCESSED / "layoffs_clean.csv", RAW / "sec_company_matches.csv", RAW / "sec_headcount.csv", RAW / "sec_universe_sic.csv",
              PROCESSED / "company_panel.csv"]
    out = {"inputs_sha256": file_hashes(inputs), "registration_commit": "ad835e5"}
    d = cs.load_inputs()
    ann = announcements(d["events"], d["matches"])
    heads = sh.recheck(pd.read_csv(RAW / "sec_headcount.csv"))[0]
    panel = pd.read_csv(PROCESSED / "company_panel.csv", dtype={"sic": str, "sic2": str})
    c2 = sample_c2(heads, d["universe"], ann, panel)
    log.info("C2 design (before the comparison): %d company-years, %d announced; minimum detectable shift %.3f log points", len(c2),
             int(c2["announced"].sum()), mde(float(c2["outcome"].std()), int(c2["announced"].sum()), int((c2["announced"] == 0).sum())))
    out["C2"] = {"primary": test_c2(c2), "secondary": secondary_c2(c2), "placebo": placebo_c2(c2)}
    rel = load_releases(sorted(ann["cik"].unique()))
    t = event_table(ann, rel)
    sd = float(np.sqrt((t["p"] * (1 - t["p"])).sum()))
    log.info("E design (before the comparison): %d usable announcements of %d companies; expected near a release %.1f; detectable excess %.1f",
             len(t), t["cik"].nunique(), t["p"].sum(), 2.8 * sd)
    out["E"] = {"primary": test_e(t), "secondary": secondary_e(ann, rel), "placebo": placebo_e(ann, rel)}
    return out


def main() -> None:
    from analysis.viz_theme import ROOT
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    res = run()
    path = ROOT / "reports" / "hypotheses2_a_results.json"
    path.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "inputs_sha256"}, indent=2, default=float))
    print(f"written {path}")


if __name__ == "__main__":
    main()
