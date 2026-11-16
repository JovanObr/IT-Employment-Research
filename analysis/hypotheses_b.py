"""Milestone 3, Stream B: the pre-registered tests A and B (docs/hypotheses/PREREGISTRATION.md).

A  Slovenia's ICT specialists.  Prediction-interval t test: Slovenia's change 2021 -> 2024 in the ICT-specialist share
   (Eurostat isoc_sks_itspt, unit PC_EMP) against the other 26 EU countries; t with 25 df, two-sided.
B  San Francisco vs. Austin.    d_t = log(emp SF) - log(emp Austin) (QCEW, NAICS 5415, private); d_t = a + b * post (+ trend
   if the 2019Q1-2022Q1 pre-trend is significant at 0.05); Newey-West (Bartlett, 4 lags) standard error for b.

Every function follows the registration; do not change a test, a sample rule or a threshold without adding a dated amendment
to the registration first. Choices the registration leaves open are fixed here, before the real run:
- A: a country "has" a year only if its PC_EMP value is a number (flags such as `e`, `u`, `b` are used as published and listed).
- B: a quarter is missing when `disclosure_code` is set (`N` or `-`) or any of the three monthly levels is 0 or missing; it is
  never filled or treated as zero. Pre-trend: ordinary OLS t test on the slope (classical standard error), as written in the
  registration. Newey-West: Bartlett weights 1 - l/(L+1), small-sample factor n/(n-k), p from Student t with n-k df
  (equal to statsmodels `OLS.fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": True}, use_t=True)`).
  Quarters with a missing d_t are dropped from the regression (the time index keeps the calendar spacing).
- B placebo: the 30 largest metros (mean NAICS 5415 employment in 2019) among metro areas whose series is complete from 2019Q1 to
  the last quarter of the SF-Austin series; every unordered pair (i, j) with i before j in code order; SF-Austin is left out of
  the comparison distribution. rank_of_sf_austin = 1 + number of pairs with a strictly larger |b|.

    python -m analysis.hypotheses_b          # runs A and B on the local files, writes reports/hypotheses_b_results.json
"""
from __future__ import annotations

import json
import logging
import math
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

from analysis.hypotheses import ALPHA, file_hashes

log = logging.getLogger("covid_it_data")

# ---------------------------------------------------------------------------------------- A. constants
EU27 = ("AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
        "NL", "PL", "PT", "RO", "SE", "SI", "SK")
A_UNIT = "PC_EMP"
A_YEARS = (2021, 2024)
A_YEARS_LONG = (2019, 2024)
A_BREAK_YEAR = 2021

# ---------------------------------------------------------------------------------------- B. constants
B_NAICS = "5415"
SF_CBSA, AUSTIN_CBSA = "41860", "12420"
B_START = "2019Q1"
B_PRE_END = "2022Q1"
B_POST_START = "2022Q2"
NW_LAGS = 4
PLACEBO_METROS = 30


# ======================================================================================== A
def _a_wide(eurostat: pd.DataFrame, years, countries=EU27, unit: str = A_UNIT) -> pd.DataFrame:
    """country x year table of PC_EMP values (floats) for the given years; raises if any country lacks a year."""
    e = eurostat.copy()
    if "unit" in e:
        e = e[e["unit"].astype(str) == unit]
    e = e.assign(time=e["time"].astype(str).str[:4].astype(int), value=pd.to_numeric(e["value"], errors="coerce"))
    e = e[e["time"].isin(years)].dropna(subset=["value"])
    w = e.pivot_table(index="geo", columns="time", values="value", aggfunc="first")
    missing = [f"{c} {y}" for c in countries for y in years if c not in w.index or y not in w.columns or pd.isna(w.at[c, y])]
    if missing:
        raise ValueError(f"Eurostat {unit}: missing values for {', '.join(missing)} (all 27 EU countries need both years)")
    return w.loc[list(countries), list(years)]


def changes(eurostat: pd.DataFrame, years=A_YEARS, countries=EU27) -> pd.Series:
    """Change in percentage points (last year - first year) per country."""
    w = _a_wide(eurostat, years, countries)
    return (w[years[1]] - w[years[0]]).astype(float)


def pi_test(values: pd.Series, country: str) -> dict:
    """Prediction-interval test of one country against the rest: t = (x - mean) / (sd * sqrt(1 + 1/m)), t with m - 1 df."""
    x = float(values[country])
    others = values.drop(country).to_numpy(float)
    m = len(others)
    mean, sd = float(others.mean()), float(others.std(ddof=1))
    t = (x - mean) / (sd * math.sqrt(1 + 1 / m)) if sd > 0 else float("nan")
    p = float(2 * stats.t.sf(abs(t), df=m - 1)) if np.isfinite(t) else float("nan")
    return {"x": x, "mean_others": mean, "sd_others": sd, "t": float(t), "p": p, "df": m - 1}


def _rank(values: pd.Series, country: str) -> int:
    """1 = largest change (ties share the best rank)."""
    return int(1 + (values > values[country]).sum())


def test_a(eurostat: pd.DataFrame, country: str = "SI", years=A_YEARS) -> dict:
    """Primary test A (registered). `values` = change 2021 -> 2024 in percentage points for all 27 countries."""
    v = changes(eurostat, years)
    r = pi_test(v, country)
    return {"country": country, "years": list(years), "x_si": r["x"], "mean_others": r["mean_others"], "sd_others": r["sd_others"],
            "t": r["t"], "df": r["df"], "p": r["p"], "predicted_sign": bool(r["t"] > 0), "rank": _rank(v, country),
            "n_countries": int(len(v)), "values": {k: float(x) for k, x in v.items()}}


def estimated_flags(eurostat: pd.DataFrame, years=A_YEARS, countries=EU27) -> list[str]:
    """Country-year cells used by the test whose Eurostat flag is not empty, e.g. 'SI 2024: e' (listed in the report)."""
    e = eurostat.copy()
    if "unit" in e:
        e = e[e["unit"].astype(str) == A_UNIT]
    if "flag" not in e:
        return []
    e = e[e["geo"].isin(countries) & e["time"].astype(str).str[:4].astype(int).isin(years)]
    f = e["flag"].fillna("").astype(str)
    e = e[f != ""]
    return sorted(f"{g} {str(t)[:4]}: {fl}" for g, t, fl in zip(e["geo"], e["time"], e["flag"]))


def secondary_a(eurostat: pd.DataFrame, country: str = "SI") -> dict:
    """Rank p; the same for 2019 -> 2024 (crosses the 2021 break); relative change in %; country vs. EU27_2020; Shapiro-Wilk."""
    v = changes(eurostat, A_YEARS)
    w = _a_wide(eurostat, A_YEARS)
    rank = _rank(v, country)
    out = {"rank": rank, "rank_p": rank / len(v)}
    try:
        v_long = changes(eurostat, A_YEARS_LONG)
        r = pi_test(v_long, country)
        out["long_2019_2024"] = {"x": r["x"], "mean_others": r["mean_others"], "sd_others": r["sd_others"], "t": r["t"], "p": r["p"],
                                 "rank": _rank(v_long, country), "rank_p": _rank(v_long, country) / len(v_long),
                                 "crosses_break": A_YEARS_LONG[0] < A_BREAK_YEAR <= A_YEARS_LONG[1],
                                 "warning": "2019 -> 2024 crosses the 2021 break in the Labour Force Survey series"}
    except ValueError as err:
        out["long_2019_2024"] = {"error": str(err), "crosses_break": True}
    rel = 100 * (w[A_YEARS[1]] / w[A_YEARS[0]] - 1)
    out["relative_change_pct"] = {"country": float(rel[country]), "mean_others": float(rel.drop(country).mean()),
                                  "rank": _rank(rel, country)}
    try:
        eu = _a_wide(eurostat, A_YEARS, countries=("EU27_2020",))
        eu_change = float(eu.iloc[0, 1] - eu.iloc[0, 0])
        out["vs_eu27"] = {"eu27_change": eu_change, "country_minus_eu27": float(v[country] - eu_change)}
    except ValueError as err:
        out["vs_eu27"] = {"error": str(err)}
    sw = stats.shapiro(v.drop(country).to_numpy(float))
    out["shapiro_p_others"] = float(sw.pvalue)
    out["primary_p_approximate"] = bool(sw.pvalue < ALPHA)
    out["flagged_cells"] = estimated_flags(eurostat)
    return out


def placebo_a(eurostat: pd.DataFrame, country: str = "SI") -> dict:
    """The primary test for each of the other 26 countries against the rest; share with p < 0.05."""
    v = changes(eurostat, A_YEARS)
    ps = {c: pi_test(v, c)["p"] for c in v.index if c != country}
    return {"n": len(ps), "share_p_below_005": float(np.mean([p < ALPHA for p in ps.values()])),
            "countries_p_below_005": sorted(c for c, p in ps.items() if p < ALPHA), "p": ps}


# ======================================================================================== B
def qcew_area_codes(cbsa: str, crosswalk: pd.DataFrame | None = None) -> list[str]:
    """QCEW area code(s) for a CBSA: 'C' + the first 4 digits, plus any older code that the crosswalk maps to it."""
    code = "C" + str(cbsa).zfill(5)[:4]
    codes = [code]
    if crosswalk is not None and len(crosswalk):
        codes += [o for o, n in zip(crosswalk["old_area_fips"], crosswalk["new_area_fips"]) if n == code]
    return codes


def _period(year, qtr) -> pd.PeriodIndex:
    return pd.PeriodIndex([pd.Period(f"{int(y)}Q{int(q)}", freq="Q") for y, q in zip(year, qtr)], freq="Q")


def quarterly_series(qcew: pd.DataFrame, cbsa: str, crosswalk: pd.DataFrame | None = None, metric: str = "employment",
                     naics: str = B_NAICS) -> pd.Series:
    """Quarterly NAICS 5415 series for one metro (private ownership, already filtered by the collector).

    employment = mean of the three monthly levels; establishments = qtrly_estabs. A disclosed quarter (`disclosure_code` set) or a
    zero/missing level is NaN, never zero. Indexed by quarterly Period; if a code changed (crosswalk), the new code wins where both exist."""
    codes = qcew_area_codes(cbsa, crosswalk)
    q = qcew[(qcew["area_fips"].astype(str).isin(codes)) & (qcew["industry_code"].astype(str) == naics)].copy()
    if q.empty:
        return pd.Series(dtype=float, name=str(cbsa))
    disc = q["disclosure_code"].fillna("").astype(str).str.strip() if "disclosure_code" in q else pd.Series("", index=q.index)
    if metric == "employment":
        m = q[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].apply(pd.to_numeric, errors="coerce")
        val = m.mean(axis=1).where((m > 0).all(axis=1) & (disc == ""))
    elif metric == "establishments":
        val = pd.to_numeric(q["qtrly_estabs"], errors="coerce")
        val = val.where(val > 0)
    else:
        raise ValueError(f"unknown metric {metric!r}")
    q = q.assign(_v=val.to_numpy(), _period=_period(q["year"], q["qtr"]),
                 _pri=q["area_fips"].astype(str).map(lambda a: 0 if a == codes[0] else 1))
    q = q.sort_values(["_period", "_pri"])
    q = q[~(q["_v"].isna() & q.duplicated("_period", keep=False))]  # a reported value beats a missing one for the same quarter
    s = q.drop_duplicates("_period", keep="first").set_index("_period")["_v"].astype(float)
    s.index = pd.PeriodIndex(s.index, freq="Q")
    s.name = str(cbsa)
    return s.sort_index()


def ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """OLS coefficients, residuals and (X'X)^-1."""
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    return beta, y - X @ beta, xtx_inv


def newey_west(y: np.ndarray, X: np.ndarray, lags: int = NW_LAGS) -> dict:
    """OLS with Newey-West (Bartlett) covariance: weights 1 - l/(L+1), small-sample factor n/(n-k); t with n-k df."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    n, k = X.shape
    beta, u, xtx_inv = ols(y, X)
    g = X * u[:, None]
    S = g.T @ g
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1 - lag / (lags + 1)
        G = g[lag:].T @ g[:-lag]
        S += w * (G + G.T)
    cov = xtx_inv @ S @ xtx_inv * n / (n - k)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    tval = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    p = 2 * stats.t.sf(np.abs(tval), df=n - k)
    return {"beta": beta, "se": se, "t": tval, "p": p, "df": n - k, "n": n}


def ols_classic(y: np.ndarray, X: np.ndarray) -> dict:
    """OLS with the classical (homoskedastic) standard error and t with n-k df."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    n, k = X.shape
    beta, u, xtx_inv = ols(y, X)
    se = np.sqrt(np.diag(xtx_inv) * (u @ u) / (n - k))
    tval = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    return {"beta": beta, "se": se, "t": tval, "p": 2 * stats.t.sf(np.abs(tval), df=n - k), "df": n - k, "n": n}


def _gap(sf: pd.Series, austin: pd.Series, start: str = B_START, end: str | None = None) -> pd.Series:
    """d_t = log(SF) - log(Austin) from `start` to `end` (default: the last quarter either series has); NaN where either is missing."""
    idx = sf.index.union(austin.index)
    end_p = pd.Period(end, freq="Q") if end else idx.max()
    full = pd.period_range(pd.Period(start, freq="Q"), end_p, freq="Q")
    a, b = sf.reindex(full).astype(float), austin.reindex(full).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = np.log(a.where(a > 0)) - np.log(b.where(b > 0))
    return pd.Series(d.to_numpy(), index=full)


def test_b(sf: pd.Series, austin: pd.Series, post_start: str = B_POST_START, pre_end: str = B_PRE_END, start: str = B_START,
           end: str | None = None, lags: int = NW_LAGS, exclude: tuple[str, ...] = ()) -> dict:
    """Primary test B (registered): pre-trend check, then d_t = a + b * post (+ trend), Newey-West 4 lags. Predicted b < 0."""
    d = _gap(sf, austin, start, end)
    if exclude:
        d = d.drop([pd.Period(q, freq="Q") for q in exclude if pd.Period(q, freq="Q") in d.index])
    t0 = pd.Period(start, freq="Q")
    time = np.array([(p - t0).n for p in d.index], float)
    post = np.array([p >= pd.Period(post_start, freq="Q") for p in d.index], float)
    ok = d.notna().to_numpy()
    pre = ok & np.array([p <= pd.Period(pre_end, freq="Q") for p in d.index])
    n_pre, n_post = int(pre.sum()), int((ok & (post == 1)).sum())
    base = {"n_pre": n_pre, "n_post": n_post, "n_missing": int((~ok).sum()), "post_start": post_start, "lags": lags}
    if n_pre < 3 or n_post < 2:
        return {**base, "b": None, "se": None, "ci_lo": None, "ci_hi": None, "p": None, "predicted_sign": None,
                "trend_added": None, "pretrend_p": None, "error": "too few quarters"}
    y = d.to_numpy()
    pt = ols_classic(y[pre], np.column_stack([np.ones(n_pre), time[pre]]))
    pretrend_p = float(pt["p"][1])
    trend_added = bool(pretrend_p < ALPHA)
    cols = [np.ones(ok.sum()), post[ok]] + ([time[ok]] if trend_added else [])
    r = newey_west(y[ok], np.column_stack(cols), lags=lags)
    b, se = float(r["beta"][1]), float(r["se"][1])
    crit = float(stats.t.ppf(0.975, r["df"]))
    return {**base, "b": b, "se": se, "ci_lo": b - crit * se, "ci_hi": b + crit * se, "p": float(r["p"][1]),
            "predicted_sign": bool(b < 0), "trend_added": trend_added, "pretrend_p": pretrend_p,
            "pretrend_slope": float(pt["beta"][1]), "df": int(r["df"])}


def series_records(sf: pd.Series, austin: pd.Series, start: str = B_START, end: str | None = None) -> list[dict]:
    """[{quarter, sf, austin}] from `start` to the last quarter; missing quarters as None."""
    idx = sf.index.union(austin.index)
    full = pd.period_range(pd.Period(start, freq="Q"), pd.Period(end, freq="Q") if end else idx.max(), freq="Q")
    a, b = sf.reindex(full), austin.reindex(full)
    num = lambda x: None if pd.isna(x) else float(x)
    return [{"quarter": str(p), "sf": num(a[p]), "austin": num(b[p])} for p in full]


def metro_codes(qcew: pd.DataFrame, naics: str = B_NAICS) -> list[str]:
    """CBSA codes (5 characters) of metro areas in the QCEW file: area codes 'C' + 4 digits (not combined areas 'CS...')."""
    a = qcew.loc[qcew["industry_code"].astype(str) == naics, "area_fips"].astype(str).unique()
    return sorted(c[1:] + "0" for c in a if len(c) == 5 and c[0] == "C" and c[1:].isdigit())


def placebo_metros(qcew: pd.DataFrame, crosswalk: pd.DataFrame | None = None, n: int = PLACEBO_METROS, start: str = B_START,
                   end: str | None = None) -> list[str]:
    """The n metros with the most NAICS 5415 jobs in 2019 (mean of the quarters) among those with a complete series start..end."""
    new_codes = set(crosswalk["new_area_fips"]) if crosswalk is not None and len(crosswalk) else set()
    old_codes = set(crosswalk["old_area_fips"]) if crosswalk is not None and len(crosswalk) else set()
    rows = []
    for cbsa in metro_codes(qcew):
        code = "C" + cbsa[:4]
        if code in old_codes and code not in new_codes:
            continue  # an old code is read through its new code
        s = quarterly_series(qcew, cbsa, crosswalk)
        if s.empty:
            continue
        last = pd.Period(end, freq="Q") if end else s.index.max()
        full = pd.period_range(pd.Period(start, freq="Q"), last, freq="Q")
        r = s.reindex(full)
        if r.isna().any():
            continue
        rows.append((cbsa, float(r[[p for p in full if p.year == 2019]].mean())))
    rows.sort(key=lambda x: -x[1])
    return [c for c, _ in rows[:n]]


def placebo_b(qcew: pd.DataFrame, b_sfa: float | None, crosswalk: pd.DataFrame | None = None, end: str | None = None,
              pair=(SF_CBSA, AUSTIN_CBSA), n: int = PLACEBO_METROS) -> dict:
    """The primary b (same pre-trend rule) for every pair among the placebo metros; SF-Austin's rank by |b| and the share of pairs
    with |b| at least as large (SF-Austin itself left out of the distribution)."""
    metros = placebo_metros(qcew, crosswalk, n=n, end=end)
    series = {c: quarterly_series(qcew, c, crosswalk) for c in metros}
    bs, rows = [], []
    for i, j in combinations(sorted(metros), 2):
        if {i, j} == set(pair):
            continue
        r = test_b(series[i], series[j], end=end)
        if r["b"] is None:
            continue
        bs.append(r["b"])
        rows.append({"pair": f"{i}-{j}", "b": r["b"], "p": r["p"], "trend_added": r["trend_added"]})
    arr = np.abs(np.array(bs, float))
    out = {"metros": metros, "n_metros": len(metros), "n_pairs": len(bs),
           "sf_in_metros": pair[0] in metros, "austin_in_metros": pair[1] in metros,
           "share_p_below_005": float(np.mean([r["p"] < ALPHA for r in rows])) if rows else None,
           "share_trend_added": float(np.mean([r["trend_added"] for r in rows])) if rows else None,
           "b_quantiles": {str(q): float(np.quantile(bs, q)) for q in (0.025, 0.25, 0.5, 0.75, 0.975)} if bs else None,
           "rank_of_sf_austin": None, "share_abs_b_at_least": None, "pairs": rows}
    if b_sfa is not None and len(arr):
        out["rank_of_sf_austin"] = int(1 + (arr > abs(b_sfa)).sum())
        out["share_abs_b_at_least"] = float((arr >= abs(b_sfa)).mean())
    return out


def secondary_b(qcew: pd.DataFrame, crosswalk: pd.DataFrame | None = None, end: str | None = None) -> dict:
    """Same model without 2020Q1 (pandemic shock); establishments instead of employment."""
    sf, au = (quarterly_series(qcew, c, crosswalk) for c in (SF_CBSA, AUSTIN_CBSA))
    sfe, aue = (quarterly_series(qcew, c, crosswalk, metric="establishments") for c in (SF_CBSA, AUSTIN_CBSA))
    keys = ("b", "se", "ci_lo", "ci_hi", "p", "predicted_sign", "trend_added", "pretrend_p", "n_pre", "n_post")
    pick = lambda r: {k: r.get(k) for k in keys}
    return {"without_2020Q1": pick(test_b(sf, au, end=end, exclude=("2020Q1",))),
            "establishments": pick(test_b(sfe, aue, end=end))}


# ======================================================================================== run
def _clean(x):
    """JSON-safe: numpy -> python, NaN/inf -> None."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else float(x)
    return x


def run_a(eurostat: pd.DataFrame) -> dict:
    return {"primary": test_a(eurostat), "secondary": secondary_a(eurostat), "placebo": placebo_a(eurostat)}


def last_published_quarter(*series: pd.Series) -> str:
    """Last quarter in which any of the series has a value. QCEW files carry placeholder rows for quarters not yet published
    (all levels 0, disclosure code '-'); those are missing, so they must not set the end of the sample (amendment 2026-11-16)."""
    last = [s.dropna().index.max() for s in series if s.notna().any()]
    if not last:
        raise ValueError("no published quarter in either series")
    return str(max(last))


def run_b(qcew: pd.DataFrame, crosswalk: pd.DataFrame | None = None) -> dict:
    sf, au = (quarterly_series(qcew, c, crosswalk) for c in (SF_CBSA, AUSTIN_CBSA))
    end = last_published_quarter(sf, au)
    primary = test_b(sf, au, end=end)
    primary["series"] = series_records(sf, au, end=end)
    primary["last_quarter"] = end
    raw = qcew[qcew["area_fips"].astype(str).isin(qcew_area_codes(SF_CBSA, crosswalk) + qcew_area_codes(AUSTIN_CBSA, crosswalk))
               & (qcew["industry_code"].astype(str) == B_NAICS)]
    raw = raw[_period(raw["year"], raw["qtr"]) >= pd.Period(B_START, freq="Q")]
    primary["disclosure_codes"] = {f"{a} {y}Q{q}": c for a, y, q, c in
                                   zip(raw["area_fips"], raw["year"], raw["qtr"], raw["disclosure_code"].fillna("").astype(str)) if c}
    return {"primary": primary, "secondary": secondary_b(qcew, crosswalk, end=end),
            "placebo": placebo_b(qcew, primary["b"], crosswalk, end=end)}


def run() -> dict:
    from collectors.common import RAW
    from analysis.viz_theme import ROOT
    e_path, q_path, x_path = RAW / "eurostat_isoc_sks_itspt.csv", RAW / "bls_qcew_areas_it_industries.csv", ROOT / "config" / "qcew_code_crosswalk.csv"
    out = {"inputs_sha256": file_hashes([e_path, q_path, x_path])}
    eurostat = pd.read_csv(e_path, dtype={"geo": str, "unit": str, "flag": str, "time": str}, keep_default_na=False, na_values=[""])
    out["A"] = run_a(eurostat)
    qcew = pd.read_csv(q_path, dtype=str, keep_default_na=False, na_values=[""])
    crosswalk = pd.read_csv(x_path, dtype=str) if x_path.exists() else None
    out["B"] = run_b(qcew, crosswalk)
    return _clean(out)


def main() -> None:
    from analysis.viz_theme import ROOT
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    res = run()
    path = ROOT / "reports" / "hypotheses_b_results.json"
    path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    show = {k: {kk: ({x: y for x, y in vv.items()
                      if x not in ("series", "values", "pairs", "disclosure_codes", "flagged_cells") and not (x == "p" and isinstance(y, dict))}
                     if isinstance(vv, dict) else vv) for kk, vv in v.items()} for k, v in res.items() if k != "inputs_sha256"}
    print(json.dumps(show, indent=2))
    print(f"written {path}")


if __name__ == "__main__":
    main()
