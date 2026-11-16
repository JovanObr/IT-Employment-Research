"""Milestone 3 tests A and B: a planted effect must be found, a null must not be (synthetic data only, no network)."""
import json

import numpy as np
import pandas as pd
import pytest

from analysis import hypotheses_b as hb

QUARTERS = pd.period_range("2019Q1", "2025Q4", freq="Q")


# ---------------------------------------------------------------------------------------- A
def _eurostat(si_change=None, seed=0, drop=None, sd=0.3):
    """Long Eurostat-like table (unit PC_EMP + a THS_PER decoy) for EU-27 + EU27_2020, years 2019..2024."""
    rng = np.random.default_rng(seed)
    rows = []
    for c in hb.EU27 + ("EU27_2020",):
        base = rng.uniform(3, 7)
        ch = rng.normal(0.5, sd)
        if c == "SI" and si_change is not None:
            ch = si_change
        for y in range(2019, 2025):
            v = base + ch * max(0, y - 2021) / 3 + (0.1 if y < 2021 else 0)
            if drop == (c, y):
                continue
            rows.append({"freq": "A", "unit": "PC_EMP", "geo": c, "time": str(y), "value": v, "flag": "e" if (c, y) == ("SI", 2024) else ""})
            rows.append({"freq": "A", "unit": "THS_PER", "geo": c, "time": str(y), "value": 1000.0, "flag": ""})
    return pd.DataFrame(rows)


A_KEYS = {"x_si", "mean_others", "sd_others", "t", "p", "predicted_sign", "rank", "n_countries", "values"}


def test_a_finds_a_planted_outlier():
    r = hb.test_a(_eurostat(si_change=2.5))
    assert A_KEYS <= set(r)
    assert r["p"] < 0.01 and r["t"] > 0 and r["predicted_sign"] and r["rank"] == 1
    assert r["n_countries"] == 27 and set(r["values"]) == set(hb.EU27) and np.isclose(r["values"]["SI"], 2.5)
    assert 0 < r["p"] <= 1


def test_a_country_from_the_same_distribution_is_not_found():
    ps = [hb.test_a(_eurostat(seed=s))["p"] for s in range(40)]
    assert np.mean(np.array(ps) < 0.05) <= 0.15
    assert all(0 < p <= 1 for p in ps)


def test_a_formula_matches_the_registration():
    v = pd.Series(np.arange(27, dtype=float), index=list(hb.EU27))
    r = hb.pi_test(v, "SI")
    others = v.drop("SI")
    t = (v["SI"] - others.mean()) / (others.std(ddof=1) * np.sqrt(1 + 1 / 26))
    assert np.isclose(r["t"], t) and r["df"] == 25


def test_a_missing_country_raises():
    with pytest.raises(ValueError, match="EL 2024"):
        hb.test_a(_eurostat(drop=("EL", 2024)))


def test_a_rank_secondary_and_placebo():
    e = _eurostat(si_change=2.5)
    s = hb.secondary_a(e)
    assert s["rank"] == 1 and np.isclose(s["rank_p"], 1 / 27)
    assert s["long_2019_2024"]["crosses_break"] and "warning" in s["long_2019_2024"]
    assert "country_minus_eu27" in s["vs_eu27"] and 0 < s["shapiro_p_others"] <= 1
    assert "SI 2024: e" in s["flagged_cells"]
    pl = hb.placebo_a(e)
    assert pl["n"] == 26 and "SI" not in pl["p"] and 0 <= pl["share_p_below_005"] <= 1
    rates = [hb.placebo_a(_eurostat(seed=s))["share_p_below_005"] for s in range(20)]
    assert np.mean(rates) < 0.12  # about 5 % if calibrated


# ---------------------------------------------------------------------------------------- B helpers
def _series(log_values, idx=QUARTERS):
    return pd.Series(np.exp(np.asarray(log_values, float)), index=idx)


def _ar(rng, n, rho=0.3, sd=0.02):
    e = np.zeros(n)
    e[0] = rng.normal(0, sd)
    for i in range(1, n):
        e[i] = rho * e[i - 1] + rng.normal(0, sd)
    return e


def _qcew(metros: dict, idx=QUARTERS, disclosed=(), estabs=None):
    """QCEW-like rows: metros = {area_fips: quarterly employment array}."""
    rows = []
    for code, emp in metros.items():
        for k, p in enumerate(idx):
            hidden = (code, str(p)) in disclosed
            e = 0 if hidden else int(round(emp[k]))
            rows.append({"area_fips": code, "year": str(p.year), "qtr": str(p.quarter), "industry_code": "5415",
                         "disclosure_code": "N" if hidden else "", "qtrly_estabs": str(estabs[code][k] if estabs else 100 + k),
                         "month1_emplvl": str(e), "month2_emplvl": str(e), "month3_emplvl": str(e)})
            rows.append({**rows[-1], "industry_code": "10", "month1_emplvl": "1", "month2_emplvl": "1", "month3_emplvl": "1"})
    return pd.DataFrame(rows)


B_KEYS = {"b", "se", "ci_lo", "ci_hi", "p", "predicted_sign", "trend_added", "pretrend_p", "n_pre", "n_post"}


# ---------------------------------------------------------------------------------------- B: Newey-West
def test_newey_west_lag_zero_is_white_hc0_with_df_factor():
    rng = np.random.default_rng(3)
    n = 40
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    y = 1 + 0.5 * X[:, 1] + rng.normal(size=n) * (1 + np.abs(X[:, 1]))
    r = hb.newey_west(y, X, lags=0)
    beta = np.linalg.solve(X.T @ X, X.T @ y)
    u = y - X @ beta
    inv = np.linalg.inv(X.T @ X)
    hc0 = inv @ (X * u[:, None] ** 2).T @ X @ inv * n / (n - 2)
    assert np.allclose(r["se"], np.sqrt(np.diag(hc0)))


# Reference computed once (2026-11-16) with statsmodels 0.15.0, numpy 2.5.4 (statsmodels is not a dependency) on _nw_case():
# sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": True}, use_t=True)
NW_REF = {
    "params": [0.10382800607584608, -0.052257893812731264, 0.00044443093001786263],
    "bse": [0.007167419659498321, 0.015631241167861475, 0.0007591834186603685],
    "pvalues": [5.810208575359608e-14, 0.0025206291238465363, 0.5633214475157938],
}


def _nw_case():
    rng = np.random.default_rng(7)
    n = 29
    t = np.arange(n, dtype=float)
    post = (t >= 13).astype(float)
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.6 * e[i - 1] + rng.normal(0, 0.02)
    return 0.1 - 0.05 * post + 0.002 * t + e, np.column_stack([np.ones(n), post, t])


def test_newey_west_matches_statsmodels_reference():
    y, X = _nw_case()
    r = hb.newey_west(y, X, lags=4)
    assert np.allclose(r["beta"], NW_REF["params"], rtol=1e-8, atol=1e-12)
    assert np.allclose(r["se"], NW_REF["bse"], rtol=1e-6)
    assert np.allclose(r["p"], NW_REF["pvalues"], rtol=1e-6)


def test_newey_west_is_calibrated_in_a_long_series():
    rej = []
    for s in range(200):
        rng = np.random.default_rng(1000 + s)
        n = 400
        x = _ar(rng, n, rho=0.5, sd=1)
        y = _ar(rng, n, rho=0.5, sd=1)
        rej.append(hb.newey_west(y, np.column_stack([np.ones(n), x]), lags=4)["p"][1] < 0.05)
    assert 0.02 <= np.mean(rej) <= 0.10


def test_registered_short_design_false_positive_rate_is_measured():
    """The registered design (28 quarters, a step dummy, Newey-West 4 lags) over-rejects on pure noise: about 14 % for
    independent errors in this simulation, not 5 %. This is a property of the method, not a code error (the code matches
    statsmodels); the placebo across metro pairs is the empirical check. The test pins the size so a change is noticed."""
    rej = []
    for s in range(200):
        rng = np.random.default_rng(s)
        d = rng.normal(0, 0.02, len(QUARTERS))
        r = hb.test_b(_series(10 + d), _series(np.full(len(QUARTERS), 10.0)))
        rej.append(r["p"] < 0.05)
    assert 0.05 <= np.mean(rej) <= 0.25


# ---------------------------------------------------------------------------------------- B: test_b
def test_b_finds_a_planted_drop_with_the_right_sign():
    rng = np.random.default_rng(11)
    post = np.array([p >= pd.Period("2022Q2", freq="Q") for p in QUARTERS], float)
    d = -0.10 * post + _ar(rng, len(QUARTERS), rho=0.3, sd=0.01)
    r = hb.test_b(_series(10 + d), _series(np.full(len(QUARTERS), 10.0)))
    assert B_KEYS <= set(r) and r["p"] < 0.01 and r["b"] < 0 and r["predicted_sign"] and r["ci_hi"] < 0
    assert r["n_pre"] == 13 and r["n_post"] == 15 and 0 < r["p"] <= 1


def test_b_no_break_mostly_not_found():
    ps = []
    for s in range(200):
        rng = np.random.default_rng(500 + s)
        d = np.cumsum(rng.normal(0, 0.01, len(QUARTERS)))
        ps.append(hb.test_b(_series(10 + d), _series(np.full(len(QUARTERS), 10.0)))["p"])
    assert np.mean(np.array(ps) > 0.05) > 0.5  # "most seeds"; the exact rate is reported, see the size test above
    assert all(0 < p <= 1 for p in ps)


def test_b_trend_added_exactly_when_pretrend_is_significant():
    n = len(QUARTERS)
    rng = np.random.default_rng(2)
    trend = 10 + 0.01 * np.arange(n) + rng.normal(0, 0.002, n)
    r = hb.test_b(_series(trend), _series(np.full(n, 10.0)))
    assert r["pretrend_p"] < 0.05 and r["trend_added"]
    flat = 10 + rng.normal(0, 0.02, n)
    r0 = hb.test_b(_series(flat), _series(np.full(n, 10.0)))
    assert r0["trend_added"] == (r0["pretrend_p"] < 0.05)
    for s in range(30):
        g = np.random.default_rng(s)
        rr = hb.test_b(_series(10 + np.cumsum(g.normal(0, 0.01, n))), _series(np.full(n, 10.0)))
        assert rr["trend_added"] == (rr["pretrend_p"] < 0.05)
    # with a trend added, a pure trend gives b about 0
    assert abs(r["b"]) < 0.01


def test_b_without_trend_b_is_the_difference_in_means():
    n = len(QUARTERS)
    rng = np.random.default_rng(4)
    d = rng.normal(0, 0.02, n)
    r = hb.test_b(_series(10 + d), _series(np.full(n, 10.0)))
    if not r["trend_added"]:
        post = np.array([p >= pd.Period("2022Q2", freq="Q") for p in QUARTERS])
        assert np.isclose(r["b"], d[post].mean() - d[~post].mean())


# ---------------------------------------------------------------------------------------- B: data handling
def test_quarterly_series_keeps_disclosed_quarters_missing():
    n = len(QUARTERS)
    q = _qcew({"C4186": np.full(n, 5000.0), "C1242": np.full(n, 3000.0)}, disclosed={("C4186", "2020Q3")})
    s = hb.quarterly_series(q, "41860")
    assert pd.isna(s[pd.Period("2020Q3", freq="Q")]) and (s.dropna() == 5000).all() and len(s) == n
    r = hb.test_b(s, hb.quarterly_series(q, "12420"))
    assert r["n_missing"] == 1 and r["n_pre"] == 12
    rec = hb.series_records(s, hb.quarterly_series(q, "12420"))
    assert rec[6] == {"quarter": "2020Q3", "sf": None, "austin": 3000.0}


def test_quarterly_series_dash_code_and_zero_are_missing_and_monthly_mean_used():
    q = _qcew({"C4186": np.full(len(QUARTERS), 5000.0)})
    first = q.index[(q["industry_code"] == "5415")][0]
    q.loc[first, ["month1_emplvl", "month2_emplvl", "month3_emplvl"]] = ["90", "100", "110"]
    second = q.index[(q["industry_code"] == "5415")][1]
    q.loc[second, "disclosure_code"] = "-"
    s = hb.quarterly_series(q, "41860")
    assert s.iloc[0] == 100 and pd.isna(s.iloc[1])


def test_quarterly_series_applies_the_crosswalk():
    idx_old = pd.period_range("2019Q1", "2022Q4", freq="Q")
    idx_new = pd.period_range("2023Q1", "2025Q4", freq="Q")
    q = pd.concat([_qcew({"C1746": np.full(len(idx_old), 800.0)}, idx=idx_old),
                   _qcew({"C1741": np.full(len(idx_new), 900.0)}, idx=idx_new)])
    cw = pd.DataFrame({"old_area_fips": ["C1746"], "new_area_fips": ["C1741"]})
    s = hb.quarterly_series(q, "17410", cw)
    assert len(s) == len(QUARTERS) and s.notna().all()
    assert "17460" not in hb.placebo_metros(q, cw, n=5) and "17410" in hb.placebo_metros(q, cw, n=5)


def _metros(n_metros=8, seed=0, sf_drop=0.0):
    rng = np.random.default_rng(seed)
    codes = ["C4186", "C1242"] + [f"C{1000 + 37 * i}" for i in range(n_metros - 2)]
    post = np.array([p >= pd.Period("2022Q2", freq="Q") for p in QUARTERS], float)
    out = {}
    for k, c in enumerate(codes):
        lv = np.log(1000 * (n_metros - k)) + np.cumsum(rng.normal(0, 0.01, len(QUARTERS)))
        if c == "C4186":
            lv = lv + sf_drop * post
        out[c] = np.exp(lv)
    return out


def test_placebo_b_ranks_and_shares():
    q = _qcew(_metros(sf_drop=-0.3), disclosed={("C1111", "2021Q1")})
    sf, au = hb.quarterly_series(q, "41860"), hb.quarterly_series(q, "12420")
    b = hb.test_b(sf, au)["b"]
    pl = hb.placebo_b(q, b, n=30)
    assert "11110" not in pl["metros"]  # incomplete series dropped
    assert pl["n_metros"] == 7 and pl["n_pairs"] == 7 * 6 // 2 - 1
    assert pl["sf_in_metros"] and pl["austin_in_metros"]
    assert 1 <= pl["rank_of_sf_austin"] <= pl["n_pairs"] + 1 and 0 <= pl["share_abs_b_at_least"] <= 1
    # the planted SF drop shows in every SF pair, so SF-Austin should be near the top
    assert pl["rank_of_sf_austin"] <= 7


def test_placebo_metros_picks_the_biggest_in_2019():
    q = _qcew(_metros())
    assert hb.placebo_metros(q, n=2) == ["41860", "12420"]


def test_secondary_b_keys():
    q = _qcew(_metros())
    s = hb.secondary_b(q)
    assert B_KEYS <= set(s["without_2020Q1"]) and B_KEYS <= set(s["establishments"])
    assert s["without_2020Q1"]["n_pre"] == 12


# ---------------------------------------------------------------------------------------- results file
def test_results_are_json_safe_with_the_registered_keys():
    e = _eurostat(si_change=1.0)
    q = _qcew(_metros())
    res = hb._clean({"inputs_sha256": {"x": "y"}, "A": hb.run_a(e), "B": hb.run_b(q)})
    txt = json.dumps(res, allow_nan=False)
    back = json.loads(txt)
    assert A_KEYS <= set(back["A"]["primary"]) and "share_p_below_005" in back["A"]["placebo"]
    assert B_KEYS | {"series"} <= set(back["B"]["primary"])
    assert {"n_pairs", "rank_of_sf_austin", "share_abs_b_at_least"} <= set(back["B"]["placebo"])
    assert back["B"]["primary"]["series"][0]["quarter"] == "2019Q1"
    assert isinstance(back["A"]["primary"]["predicted_sign"], bool)
    assert hb._clean({"a": float("nan"), "b": np.float64(1.5), "c": np.int64(2)}) == {"a": None, "b": 1.5, "c": 2}
