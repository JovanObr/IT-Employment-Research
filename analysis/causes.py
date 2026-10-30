"""A4: three hypotheses about WHY tech layoffs happened, each with a stated test, a result and a limit.

H1  Interest rates / the market. Do changes in the Fed funds rate or the NASDAQ lead tracker layoffs?
    Test: lead-lag correlation of 12-month changes with 3-month layoff counts, lags -12..+12 months; p-value from
    all circular shifts of the layoff series (keeps its autocorrelation). Limit: ONE rate cycle, ~6 years of data; any
    two trending series correlate, and 25 lags are searched (the p-value accounts for that, not for the cycle).
H2  Two dated shocks. Did tracker layoffs jump after the first Fed hike (2022-03-16) or after ChatGPT (2022-11-30)?
    Test: mean weekly events in the 26 weeks after vs before, ranked against the same before/after difference at
    EVERY other week (placebo dates). Limit: the two dates are 8 months apart inside the same downturn, so the data
    cannot separate them; a high rank says "a jump happened around then", not why.
H3  Over-hiring. Did companies that grew costs faster than revenue in the 2020-2021 boom lay off more later?
    Test: AUC and a size-controlled logistic regression of "layoff in 2022-2023" on boom growth, bootstrap over
    companies. Limit: no headcount data (costs are a proxy); size dominates who appears in the tracker; ~tens of
    positives.

Associations are not causes. Run:  python -m analysis.causes   (needs: layoffs, macro, sec, sec_universe, sec_fin)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from analysis.company_panel import qindex, quarterly_table
from collectors.common import PROCESSED, RAW

log = logging.getLogger("covid_it_data")

FED_HIKE = pd.Timestamp("2022-03-16")
CHATGPT = pd.Timestamp("2022-11-30")


# ---------------------------------------------------------------------------------------- layoff series
def monthly_layoffs(events: pd.DataFrame, region: str = "US") -> pd.DataFrame:
    """Events and people laid off per month, complete months only (the first and last month of the tracker are partial)."""
    e = events[(events["region"] == region)].dropna(subset=["date"]).copy()
    lo, hi = events["date"].min(), events["date"].max()
    first = (lo + pd.offsets.MonthBegin(1)).normalize()
    last = hi.to_period("M").to_timestamp() - pd.offsets.MonthBegin(1)
    e["month"] = e["date"].dt.to_period("M").dt.to_timestamp()
    g = e.groupby("month").agg(events=("date", "size"), laid_off=("total_laid_off", "sum"))
    return g.reindex(pd.date_range(first, last, freq="MS"), fill_value=0)


def weekly_layoffs(events: pd.DataFrame, region: str = "US") -> pd.Series:
    """Events per week (weeks start on Monday), complete weeks only."""
    e = events[events["region"] == region].dropna(subset=["date"])
    wk = (e["date"] - pd.to_timedelta(e["date"].dt.day_of_week, unit="D")).dt.normalize()
    lo, hi = events["date"].min().normalize(), events["date"].max().normalize()
    first = lo - pd.Timedelta(days=lo.weekday()) + pd.Timedelta(days=7)
    last = hi - pd.Timedelta(days=hi.weekday()) - pd.Timedelta(days=7)
    idx = pd.date_range(first, last, freq="7D")
    return wk.value_counts().reindex(idx, fill_value=0).sort_index().rename("events")


def monthly_macro(fred: pd.DataFrame) -> pd.DataFrame:
    """Monthly: Fed funds rate, NASDAQ (monthly mean), and their 12-month changes."""
    w = fred.pivot_table(index="date", columns="series_id", values="value")
    m = pd.DataFrame({"fedfunds": w["FEDFUNDS"].resample("MS").mean(), "nasdaq": w["NASDAQCOM"].resample("MS").mean()})
    m["fedfunds_chg12"] = m["fedfunds"].diff(12)
    m["nasdaq_chg12"] = np.log(m["nasdaq"]).diff(12)
    return m


# ---------------------------------------------------------------------------------------- H1: lead-lag
def _xcorr(xv: np.ndarray, yv: np.ndarray, lags) -> np.ndarray:
    """corr(x_t, y_{t+lag}); a POSITIVE lag means x comes first (leads)."""
    out = []
    for L in lags:
        a, b = (xv[: len(xv) - L], yv[L:]) if L >= 0 else (xv[-L:], yv[: len(yv) + L])
        out.append(np.corrcoef(a, b)[0, 1] if len(a) >= 12 and a.std() > 0 and b.std() > 0 else np.nan)
    return np.array(out)


def lead_lag_test(x: pd.Series, y: pd.Series, max_lag: int = 12) -> dict:
    """Cross-correlation over lags -max_lag..+max_lag and a p-value for the LARGEST |correlation|.
    Null: y is moved circularly around the calendar by every shift larger than `max_lag` months (this keeps its
    autocorrelation and its hump, and only breaks the timing against x). All such shifts are used, so the p-value is
    exact for this null; with n months there are n - 2*max_lag - 1 of them, so the smallest possible p is
    1/(n_shifts + 1) (about 0.02 for 76 months). Both series are first cut to their common non-missing months."""
    d = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    lags = list(range(-max_lag, max_lag + 1))
    xv, yv = d["x"].to_numpy(float), d["y"].to_numpy(float)
    corr = _xcorr(xv, yv, lags)
    stat = np.nanmax(np.abs(corr))
    shifts = range(max_lag + 1, len(yv) - max_lag)
    null = np.array([np.nanmax(np.abs(_xcorr(xv, np.roll(yv, k), lags))) for k in shifts])
    best = int(np.nanargmax(np.abs(corr)))
    return {"table": pd.DataFrame({"lag_months": lags, "corr": corr}), "n_months": len(d), "n_shifts": len(null),
            "best_lag": lags[best], "best_corr": float(corr[best]),
            "p_value": float((1 + (null >= stat).sum()) / (len(null) + 1))}


# ---------------------------------------------------------------------------------------- H2: event studies
def _centre_diffs(s: pd.Series, before: int, after: int) -> pd.Series:
    vals = s.to_numpy(float)
    out = {s.index[i]: vals[i: i + after].mean() - vals[i - before: i].mean()
           for i in range(before, len(s) - after + 1)}
    return pd.Series(out)


def event_study(s: pd.Series, date, before: int = 26, after: int = 26) -> dict:
    """`s`: weekly counts (index = Monday of each week). Mean per period in `after` periods from the event vs `before` periods before it, ranked among the same
    difference computed at every other possible date (placebo dates). Overlapping windows: the placebo dates are
    not independent, so read the rank as descriptive, not as a p-value."""
    date = pd.Timestamp(date)
    start = date.normalize() - pd.Timedelta(days=date.weekday())      # `s` is weekly, weeks start on Monday
    placebo = _centre_diffs(s, before, after)
    if start not in placebo.index:
        raise ValueError(f"{date.date()} is too close to the edge of the series for {before}+{after} periods")
    i = s.index.get_loc(start)
    b, a = s.iloc[i - before: i].mean(), s.iloc[i: i + after].mean()
    return {"date": date, "before_mean": b, "after_mean": a, "diff": a - b, "ratio": a / b if b > 0 else np.nan,
            "rank_share": float((placebo <= (a - b)).mean()), "n_placebo_dates": len(placebo),
            "largest_jump_date": placebo.idxmax(), "largest_jump": float(placebo.max()), "placebo": placebo}


def monthly_event_window(s: pd.Series, date, k: int = 6) -> dict:
    """Mean of a monthly series in the k months before the event month vs from the event month on."""
    m = pd.Timestamp(date).to_period("M").to_timestamp()
    b = s[(s.index >= m - pd.DateOffset(months=k)) & (s.index < m)]
    a = s[(s.index >= m) & (s.index < m + pd.DateOffset(months=k))]
    return {"before": b.mean(), "after": a.mean(), "diff": a.mean() - b.mean(), "n_before": len(b), "n_after": len(a)}


def rate_context(fred: pd.DataFrame, date, weeks: int = 26) -> dict:
    """Fed funds rate and NASDAQ around an event date, for the reader (not a test)."""
    date = pd.Timestamp(date)
    w = fred.pivot_table(index="date", columns="series_id", values="value").sort_index()
    at = lambda sid, d: float(w[sid].dropna().loc[:d].iloc[-1])
    end = date + pd.Timedelta(weeks=weeks)
    return {"fed_funds_day_before": at("DFF", date - pd.Timedelta(days=1)), f"fed_funds_{weeks}w_later": at("DFF", end),
            "nasdaq_change_pct": 100 * (at("NASDAQCOM", end) / at("NASDAQCOM", date - pd.Timedelta(days=1)) - 1)}


# ---------------------------------------------------------------------------------------- H3: over-hiring
def company_boom_table(fin: pd.DataFrame, revenue: pd.DataFrame, universe: pd.DataFrame, matches: pd.DataFrame,
                       events: pd.DataFrame, boom=(2019, 2021), outcome=(2022, 2023)) -> pd.DataFrame:
    """One row per tech company with four complete quarters of revenue and operating income in both boom years.
    boom_growth = ln(revenue_end / revenue_start); cost_growth = same for costs (revenue - operating income);
    overbuild = cost_growth - boom_growth (costs grew faster than revenue). Outcome: a tracker layoff in the
    outcome years. Companies with a tracker layoff BEFORE the outcome years (in or after the start year) are dropped."""
    tech = universe[universe["is_tech"]].copy()
    tech["sic2"] = tech["sic"].astype(str).str.zfill(4).str[:2]
    q = quarterly_table(fin[fin["cik"].isin(tech["cik"])], revenue[revenue["cik"].isin(tech["cik"])])
    q["year"], q["quarter"] = q["qi"] // 4, q["qi"] % 4 + 1

    def annual(year: int) -> pd.DataFrame:
        y = q[q["year"] == year].dropna(subset=["revenue", "operating_income"])
        g = y.groupby("cik").agg(n=("qi", "nunique"), revenue=("revenue", "sum"), op_income=("operating_income", "sum"))
        g = g[g["n"] == 4]
        g["cost"] = g["revenue"] - g["op_income"]
        return g[["revenue", "cost"]]

    a0, a1 = annual(boom[0]), annual(boom[1])
    d = a0.add_suffix("_0").join(a1.add_suffix("_1"), how="inner")
    d = d[(d[["revenue_0", "revenue_1", "cost_0", "cost_1"]] > 0).all(axis=1)]
    d["boom_growth"] = np.log(d["revenue_1"] / d["revenue_0"])
    d["cost_growth"] = np.log(d["cost_1"] / d["cost_0"])
    d["overbuild"] = d["cost_growth"] - d["boom_growth"]
    start_q = q[(q["year"] == boom[0]) & (q["quarter"] == 4)].set_index("cik")["assets"]
    d["log_assets_start"] = np.log(start_q.where(start_q > 0)).reindex(d.index)
    d = d.reset_index().merge(tech[["cik", "name", "sic2"]], on="cik")

    ev = events.merge(matches[["layoffs_company", "cik"]], left_on="company", right_on="layoffs_company").dropna(subset=["date"])
    yr = ev["date"].dt.year
    in_outcome = ev[(yr >= outcome[0]) & (yr <= outcome[1])]["cik"].unique()
    before = ev[(yr >= boom[0]) & (yr < outcome[0])]["cik"].unique()
    d["layoff_before_outcome"] = d["cik"].isin(before)
    d["y_layoff"] = d["cik"].isin(in_outcome).astype(int)
    return d


def _winsor(s: pd.Series, p: float = 0.01) -> pd.Series:
    return s.clip(s.quantile(p), s.quantile(1 - p))


def univariate_auc(d: pd.DataFrame, cols, n_boot: int = 500, seed: int = 0) -> pd.DataFrame:
    """AUC of each growth measure alone for 'layoff in the outcome years' (0.5 = no signal), bootstrap over companies."""
    rng = np.random.default_rng(seed)
    rows = []
    for c in cols:
        x = _winsor(d[c]).to_numpy(); y = d["y_layoff"].to_numpy()
        auc = roc_auc_score(y, x)
        boots = []
        for _ in range(n_boot):
            i = rng.integers(0, len(d), len(d))
            if 0 < y[i].sum() < len(i):
                boots.append(roc_auc_score(y[i], x[i]))
        rows.append({"measure": c, "auc": auc, "ci_lo": np.percentile(boots, 2.5), "ci_hi": np.percentile(boots, 97.5)})
    return pd.DataFrame(rows)


def controlled_logit(d: pd.DataFrame, cols, n_boot: int = 500, seed: int = 0) -> pd.DataFrame:
    """Logistic regression of the outcome on `cols` + company size (log assets at the start of the boom) + SIC group.
    Reports odds ratios per 1 standard deviation with a bootstrap interval over companies."""
    d = d.dropna(subset=list(cols) + ["log_assets_start"]).reset_index(drop=True)
    X = pd.DataFrame({c: _winsor(d[c]) for c in cols})
    X["log_assets_start"] = d["log_assets_start"]
    X = (X - X.mean()) / X.std()
    X = pd.concat([X, pd.get_dummies(d["sic2"], prefix="sic", dtype=float)], axis=1)
    y = d["y_layoff"].to_numpy()
    fit = lambda idx: LogisticRegression(C=1.0, max_iter=2000).fit(X.iloc[idx], y[idx]).coef_[0]
    base = fit(np.arange(len(d)))
    rng = np.random.default_rng(seed)
    boots = np.array([fit(i) for i in (rng.integers(0, len(d), len(d)) for _ in range(n_boot)) if 0 < y[i].sum() < len(i)])
    keep = list(cols) + ["log_assets_start"]
    pos = [list(X.columns).index(c) for c in keep]
    return pd.DataFrame({"term": keep, "odds_ratio": np.exp(base[pos]),
                         "ci_lo": np.exp(np.percentile(boots[:, pos], 2.5, axis=0)),
                         "ci_hi": np.exp(np.percentile(boots[:, pos], 97.5, axis=0)), "n_companies": len(d),
                         "n_positive": int(y.sum())})


def quartile_table(d: pd.DataFrame, col: str) -> pd.DataFrame:
    g = pd.qcut(d[col], 4, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"])
    return d.groupby(g, observed=True).agg(companies=("cik", "size"), laid_off=("y_layoff", "sum"),
                                           rate=("y_layoff", "mean")).reset_index().rename(columns={col: "quartile"})


# ---------------------------------------------------------------------------------------- run everything
def run_h1(events: pd.DataFrame, fred: pd.DataFrame, jolts: pd.DataFrame | None) -> dict:
    lay = monthly_layoffs(events)
    macro = monthly_macro(fred)
    y = {"tracker events (3-month sum)": lay["events"].rolling(3).sum(),
         "tracker people laid off (3-month sum, log)": np.log1p(lay["laid_off"].rolling(3).sum())}
    if jolts is not None and len(jolts):
        j = jolts[jolts["series_id"].str.endswith("LDR") & jolts["series_id"].str.startswith("JTS51")]
        if len(j):
            y["JOLTS information layoff rate (%)"] = j.set_index("date")["value"]
    results = {}
    for yname, ys in y.items():
        for xname in ("fedfunds_chg12", "nasdaq_chg12"):
            results[(xname, yname)] = lead_lag_test(macro[xname], ys)
    return {"monthly": lay, "macro": macro, "tests": results}


def run_h2(events: pd.DataFrame, fred: pd.DataFrame, jolts: pd.DataFrame | None) -> dict:
    wk = weekly_layoffs(events)
    out = {"weekly": wk, "studies": {}, "context": {}, "jolts": {}}
    for name, d in (("first Fed hike 2022-03-16", FED_HIKE), ("ChatGPT 2022-11-30", CHATGPT)):
        out["studies"][name] = event_study(wk, d)
        out["context"][name] = rate_context(fred, d)
        if jolts is not None and len(jolts):
            p = jolts.pivot_table(index="date", columns="series_id", values="value")
            info, tot = "JTS510000000000000LDR", "JTS000000000000000LDR"
            if info in p and tot in p:
                out["jolts"][name] = {"information": monthly_event_window(p[info], d),
                                      "total nonfarm": monthly_event_window(p[tot], d),
                                      "information minus total": monthly_event_window(p[info] - p[tot], d)}
    return out


def run_h3(fin, revenue, universe, matches, events) -> dict:
    d = company_boom_table(fin, revenue, universe, matches, events)
    use = d[~d["layoff_before_outcome"]]
    cols = ["boom_growth", "cost_growth", "overbuild"]
    return {"all": d, "used": use, "dropped_early_layoff": int(d["layoff_before_outcome"].sum()),
            "auc": univariate_auc(use, cols), "logit_overbuild": controlled_logit(use, ["overbuild"]),
            "logit_both": controlled_logit(use, ["boom_growth", "cost_growth"]),
            "quartiles": {c: quartile_table(use, c) for c in cols}}


def load_inputs() -> dict:
    need = {"events": PROCESSED / "layoffs_clean.csv", "fred": RAW / "fred_series.csv",
            "fin": RAW / "sec_financials_quarterly.csv", "revenue": RAW / "sec_revenue_universe.csv",
            "universe": RAW / "sec_universe_sic.csv", "matches": RAW / "sec_company_matches.csv"}
    missing = [str(p) for p in need.values() if not p.exists()]
    if missing:
        raise SystemExit("Missing inputs (run collect.py for layoffs, macro, sec, sec_universe, sec_fin): " + ", ".join(missing))
    d = {k: pd.read_csv(p) for k, p in need.items() if k != "universe"}
    d["universe"] = pd.read_csv(need["universe"], dtype={"sic": str})
    d["events"]["date"] = pd.to_datetime(d["events"]["date"], errors="coerce")
    d["fred"]["date"] = pd.to_datetime(d["fred"]["date"])
    jp = RAW / "bls_jolts.csv"
    d["jolts"] = pd.read_csv(jp, parse_dates=["date"]) if jp.exists() else None
    return d


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    d = load_inputs()
    h1 = run_h1(d["events"], d["fred"], d["jolts"])
    for (x, y), r in h1["tests"].items():
        log.info("H1  %-15s vs %-45s best lag %+3d months (corr %+.2f), p=%.3f, %d months", x, y, r["best_lag"],
                 r["best_corr"], r["p_value"], r["n_months"])
    h2 = run_h2(d["events"], d["fred"], d["jolts"])
    for name, s in h2["studies"].items():
        log.info("H2  %s: weekly events %.1f before -> %.1f after (diff %+.1f); this jump is larger than at %.0f%% of %d dates; "
                 "largest jump in the sample: week of %s (%+.1f)", name, s["before_mean"], s["after_mean"], s["diff"],
                 100 * s["rank_share"], s["n_placebo_dates"], s["largest_jump_date"].date(), s["largest_jump"])
        log.info("    context: %s", {k: round(v, 2) for k, v in h2["context"][name].items()})
        for k, v in h2["jolts"].get(name, {}).items():
            log.info("    JOLTS layoff rate, %-24s %.2f%% before -> %.2f%% after", k, v["before"], v["after"])
    h3 = run_h3(d["fin"], d["revenue"], d["universe"], d["matches"], d["events"])
    log.info("H3  %d tech companies with complete 2019 and 2021 data; %d dropped for a layoff before 2022; %d used, %d with a "
             "layoff in 2022-2023", len(h3["all"]), h3["dropped_early_layoff"], len(h3["used"]), int(h3["used"]["y_layoff"].sum()))
    log.info("H3  AUC of each measure alone:\n%s", h3["auc"].round(3).to_string(index=False))
    log.info("H3  size-controlled logistic regression (overbuild):\n%s", h3["logit_overbuild"].round(3).to_string(index=False))
    log.info("H3  size-controlled logistic regression (revenue and cost growth):\n%s", h3["logit_both"].round(3).to_string(index=False))
    for c, t in h3["quartiles"].items():
        log.info("H3  layoff rate by quartile of %s:\n%s", c, t.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
