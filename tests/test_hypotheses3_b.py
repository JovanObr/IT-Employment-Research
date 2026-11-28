"""Round 3, hypothesis G: synthetic tests (written and run before the real data are read) and the data helpers."""
import numpy as np
import pandas as pd
import pytest

from analysis import hypotheses3_b as g


def _jvs(values: dict, nace: str = "J", flags: dict | None = None) -> pd.DataFrame:
    rows = []
    for geo, series in values.items():
        for t, v in series.items():
            rows.append({"freq": "Q", "s_adj": "NSA", "nace_r2": nace, "sizeclas": "TOTAL", "indic_em": "JVR", "geo": geo,
                         "time": t, "value": v, "flag": (flags or {}).get((geo, t), "")})
    return pd.DataFrame(rows)


def _irt(paths: dict) -> pd.DataFrame:
    rows = [{"freq": "M", "int_rt": "IRT_M3", "geo": geo, "time": m, "value": v, "flag": ""}
            for geo, s in paths.items() for m, v in s.items()]
    return pd.DataFrame(rows)


def test_quarterly_rate_needs_three_months_and_euro_countries_take_ea():
    months = [f"2021-{k:02d}" for k in range(1, 7)]
    irt = _irt({"EA": dict(zip(months, [0, 0, 0, 1, 1, 1])), "CZ": dict(zip(months[:5], [1, 2, 3, 4, 5]))})
    qr = g.quarterly_rates(irt)
    assert qr.loc[pd.Period("2021Q1"), "CZ"] == 2
    assert np.isnan(qr.loc[pd.Period("2021Q2"), "CZ"])                 # only 2 months
    paths = g.rate_paths(qr, countries=("CZ", "AT", "BG"))
    assert paths.loc[pd.Period("2021Q2"), "AT"] == 1 and paths.loc[pd.Period("2021Q2"), "BG"] == 1


def test_exposure_is_lagged_year_on_year_change():
    q = pd.period_range("2020Q1", "2022Q4", freq="Q")
    paths = pd.DataFrame({"CZ": np.arange(len(q), dtype=float)}, index=q)
    x = g.yoy_exposure(paths, lag=1)
    assert np.isnan(x.iloc[4, 0]) and x.iloc[5, 0] == 4.0               # r(t-1) - r(t-5) needs 5 earlier quarters


def test_build_panel_outcome_and_flags():
    q = [f"{y}-Q{k}" for y in range(2017, 2025) for k in range(1, 5)]
    jvs = _jvs({"CZ": {t: float(i) for i, t in enumerate(q)}, "SI": {t: 2.0 for t in q}}, flags={("SI", "2019-Q2"): "u"})
    months = [f"{y}-{m:02d}" for y in range(2016, 2025) for m in range(1, 13)]
    irt = _irt({"EA": {m: 0.0 for m in months}, "CZ": {m: float(i) for i, m in enumerate(months)}})
    p = g.build_panel(jvs, irt, countries=("CZ", "SI"))
    assert len(p) == 48 and set(p["country"]) == {"CZ", "SI"}
    assert (p.loc[p["country"] == "CZ", "y"] == 4.0).all()               # level rises 1 a quarter: yoy change 4
    assert (p.loc[p["country"] == "CZ", "x"] == 12.0).all()              # rate rises 1 a month: yoy change 12
    assert (p.loc[p["country"] == "SI", "x"] == 0.0).all()
    assert g.low_quality_countries(jvs) == ["SI"]


def test_twfe_matches_dummy_regression():
    rng = np.random.default_rng(0)
    x = g.synthetic_exposure(0)
    p = g.simulate_panel(x, b=-0.3, rng=rng)
    r = g.TWFE(p).fit(p["x"].to_numpy(), p["y"].to_numpy())
    D = pd.get_dummies(p[["country"]].astype(str)).astype(float).join(pd.get_dummies(p["quarter"].astype(str), drop_first=True).astype(float))
    X = np.column_stack([p["x"].to_numpy(), D.to_numpy()])
    beta = np.linalg.lstsq(X, p["y"].to_numpy(), rcond=None)[0]
    assert r["b"] == pytest.approx(beta[0], abs=1e-9)


def test_planted_effect_found_and_null_not_found():
    x = g.synthetic_exposure(0)
    found = g.calibrate(x, n_sim=30, b=-1.0, n_boot=199, n_perm=199, seed=3, phi=0.7)
    assert found["wild"] >= 0.8 and found["share_negative"] == 1.0
    null = g.calibrate(x, n_sim=80, b=0.0, n_boot=199, n_perm=199, seed=4, phi=0.7)
    assert null["wild"] <= 0.12


def test_common_shock_with_rates_is_absorbed_by_quarter_effects():
    """Every country gets a shock that moves with the average rate rise; with b = 0 the test must not find it."""
    x = g.synthetic_exposure(0)
    c = g.calibrate(x, n_sim=80, b=0.0, n_boot=199, n_perm=199, seed=5, phi=0.7, common=3.0)
    assert c["wild"] <= 0.12
    assert 0.3 <= c["share_negative"] <= 0.7


def test_cluster_robust_t_overrejects_with_few_countries_carrying_the_variation():
    """Kept so the reason the CR1 p is not the primary stays documented."""
    x = g.synthetic_exposure(0)
    c = g.calibrate(x, n_sim=100, b=0.0, n_boot=49, n_perm=49, seed=6, phi=0.5)
    assert c["cr1"] > 0.10


def test_reassigned_exposure_keeps_the_set_of_paths():
    x = g.synthetic_exposure(0)
    p = g.simulate_panel(x, rng=np.random.default_rng(1))
    rng = np.random.default_rng(2)
    X = g.perm_matrix(p, 5, rng)
    for j in range(5):
        xw = p.assign(x=X[:, j]).pivot(index="quarter", columns="country", values="x")
        orig = p.pivot(index="quarter", columns="country", values="x")
        assert sorted(map(tuple, xw.T.round(9).to_numpy())) == sorted(map(tuple, orig.T.round(9).to_numpy()))


def test_wild_bootstrap_p_is_in_unit_interval_and_small_for_strong_effect():
    x = g.synthetic_exposure(0)
    p = g.simulate_panel(x, b=-1.0, phi=0.5, rng=np.random.default_rng(9))
    m = g.TWFE(p)
    pw = g.wild_cluster_p(m, p["x"].to_numpy(), p["y"].to_numpy(), n_boot=499, seed=1)
    assert 0 < pw < 0.05


def _fake_files(b: float = 0.0, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Files laid out like the Eurostat CSVs (all columns as strings): monthly rates from the synthetic paths, vacancy levels
    2014-2024 with country levels, a common quarter pattern and `b` times the lagged year-on-year rate change built in."""
    rng = np.random.default_rng(seed)
    rates = g.synthetic_rates(seed, start="2013Q1")
    irt = _irt({c: {f"{q.year}-{3 * (q.quarter - 1) + k:02d}": float(v) for q, v in rates[c].items() for k in (1, 2, 3)}
                for c in rates.columns})
    x = g.yoy_exposure(g.rate_paths(rates)).fillna(0.0)
    q = x.index[x.index >= pd.Period("2014Q1")]
    vals = {}
    for c in g.EU27:
        lev = 3 + rng.normal(0, 0.5) + np.sin(np.arange(len(q))) * 0.3 + rng.normal(0, 0.2, len(q)) + b * np.cumsum(x.loc[q, c].to_numpy()) / 4
        vals[c] = {f"{t.year}-Q{t.quarter}": float(v) for t, v in zip(q, lev)}
    jvs = pd.concat([_jvs(vals, "J"), _jvs(vals, "B-S")]).astype(str)
    return jvs, irt.astype(str)


def test_run_g_end_to_end_on_fake_files():
    jvs, irt = _fake_files()
    r = g.run_g(jvs, irt, n_boot=49, n_perm=49, n_placebo=4, power_sims=10, power_boot=19)
    p = r["primary"]
    assert p["n"] == 27 * 24 and p["countries"] == 27 and p["rows_dropped"] == 0
    assert 0 < p["p"] <= 1 and set(p["countries_own_rate"]) == set(g.OWN_RATE)
    assert set(r["secondary"]["leave_one_out"]) == set(g.OWN_RATE)
    assert r["secondary"]["all_industries_BS"]["countries"] == 27
    assert len(r["series"]) == 28 and 0 <= r["placebo"]["share_p_below_005"] <= 1
