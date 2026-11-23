"""Round 2 tests A2 and F and the Slovenia check B1: a planted effect must be found, a null must not be (synthetic data only)."""
import numpy as np
import pandas as pd
import pytest

from analysis import hypotheses2_b as h
from analysis.hypotheses_b import EU27

YEARS = range(2015, 2026)


# ---------------------------------------------------------------------------------------- A2
def _eurostat(slope=0.0, sigma=0.05, sd_change=0.3, seed=0, si_change=None):
    """Eurostat-like long table (PC_EMP + THS_PER) for EU-27 and EU27_2020: level_c flat until 2021, then a change by 2024
    of `slope` * (level - 4) + noise; yearly noise sd `sigma`."""
    rng = np.random.default_rng(seed)
    rows = []
    for c in EU27 + ("EU27_2020",):
        level = rng.uniform(2.5, 7.5)
        ch = slope * (level - 4) + rng.normal(0.6, sd_change)
        if c == "SI" and si_change is not None:
            ch = si_change
        for y in YEARS:
            v = level + ch * min(max(0, y - 2021), 3) / 3 + rng.normal(0, sigma)
            rows.append({"freq": "A", "unit": "PC_EMP", "geo": c, "time": str(y), "value": v, "flag": "e" if (c, y) == ("SI", 2024) else ""})
            rows.append({"freq": "A", "unit": "THS_PER", "geo": c, "time": str(y), "value": 10 * v, "flag": ""})
    return pd.DataFrame(rows)


def test_a2_data_uses_2019_2020_start_and_2021_2024_change():
    e = _eurostat()
    d = h.a2_data(e)
    w = e[(e.unit == "PC_EMP") & (e.geo == "AT")].set_index("time")["value"]
    assert d.loc["AT", "start"] == pytest.approx((w["2019"] + w["2020"]) / 2)
    assert d.loc["AT", "change"] == pytest.approx(w["2024"] - w["2021"])
    assert d.loc["AT", "change_2025"] == pytest.approx(w["2025"] - w["2021"])
    assert len(d) == 27 and "EU27_2020" not in d.index


def test_a2_finds_planted_catch_up_with_the_right_sign():
    r = h.test_a2(h.a2_data(_eurostat(slope=-0.5, sd_change=0.2)), n_perm=2000, n_boot=500)
    assert r["p"] < 0.01 and r["b"] < 0 and r["predicted_sign"]
    assert r["ci_lo"] < -0.5 < r["ci_hi"] or r["ci_hi"] < 0


def test_a2_null_is_not_found():
    ps = [h.test_a2(h.a2_data(_eurostat(seed=s)), n_perm=500, n_boot=50)["p"] for s in range(20)]
    assert np.mean(np.array(ps) < 0.05) <= 0.15


def test_permutation_p_matches_ols_p_roughly_and_is_two_sided():
    rng = np.random.default_rng(1)
    x = rng.normal(size=40)
    y = 0.4 * x + rng.normal(size=40)
    p, null = h.perm_slope_p(x, y, 4000, rng)
    assert abs(p - h._ols_p(x, y)) < 0.02
    p_neg, _ = h.perm_slope_p(x, -y, 4000, np.random.default_rng(1))
    assert abs(p - p_neg) < 0.02


def test_placebo_registered_design_is_calibrated_and_naive_design_over_rejects():
    d = h.a2_data(_eurostat(sigma=0.05))
    r = h.placebo_a2(d, sigma=0.8, n_sim=150, n_perm=200)
    assert r["share_p_below_005"] <= 0.12
    assert r["share_p_below_005_naive"] > r["share_p_below_005"] + 0.1        # regression to the mean in the naive design
    assert r["mean_slope_naive"] < 0


def test_noise_sigma_recovers_the_noise():
    r = h.noise_sigma(_eurostat(sigma=0.2, seed=3))
    assert 0.12 < r["sigma"] < 0.28 and len(r["by_country"]) == 27


def test_slovenia_residual_and_rank_for_a_planted_outlier():
    d = h.a2_data(_eurostat(si_change=-2.0, sd_change=0.1))
    s = h.slovenia_a2(d)
    assert s["residual"] < -1.5 and s["rank_residual_full"] == 27 and s["pi_p"] < 0.01
    assert 1 <= s["start_rank"] <= 27


def test_secondary_a2_has_naive_spearman_relative_2025_and_without_si():
    e = _eurostat(slope=-0.5)
    sec = h.secondary_a2(h.a2_data(e), e, n_perm=200)
    assert set(sec) >= {"naive_start_2021", "spearman", "relative_change", "change_2021_2025", "without_slovenia", "flagged_cells"}
    assert sec["without_slovenia"]["n"] == 26 and "SI 2024: e" in sec["flagged_cells"]


def test_a2_missing_country_year_raises():
    e = _eurostat()
    e = e[~((e.geo == "MT") & (e.time == "2020") & (e.unit == "PC_EMP"))]
    with pytest.raises(ValueError, match="MT 2020"):
        h.a2_data(e)


def test_mde_r_for_27_countries():
    assert h.mde_r(27) == pytest.approx(0.52, abs=0.01)


# ---------------------------------------------------------------------------------------- F
@pytest.mark.parametrize("name,coast", [
    ("New York-Newark-Jersey City, NY-NJ-PA Metro Area", "east"),
    ("Philadelphia-Camden-Wilmington, PA-NJ-DE-MD Metro Area", "east"),
    ("Washington-Arlington-Alexandria, DC-VA-MD-WV Metro Area", "east"),
    ("Portland-Vancouver-Hillsboro, OR-WA Metro Area", "west"),
    ("Portland-South Portland, ME Metro Area", "east"),
    ("Lewiston, ID-WA Metro Area", None),
    ("Chattanooga, TN-GA Metro Area", None),
    ("Honolulu, HI Metro Area", None),
    ("Tampa-St. Petersburg-Clearwater, FL Metro Area", "east"),
    ("no comma", None),
])
def test_coast_by_first_state(name, coast):
    assert h.coast_of(name) == coast


def _geo(shift=0.0, n_west=40, n_east=100, n_other=120, seed=0, withheld=(3, 20)):
    rng = np.random.default_rng(seed)
    rows = []
    for coast, n, st, mu in (("west", n_west, "CA", shift), ("east", n_east, "NY", 0.0), ("other", n_other, "TX", 0.0)):
        for i in range(n):
            g = mu + rng.standard_t(3) * 25
            e19 = float(rng.integers(100, 5000))
            rows.append({"cbsa_code": f"{len(rows):05d}", "metro_name": f"M{i}, {st} Metro Area", "emp_it_2019": e19,
                         "emp_it_2024": e19 * (1 + g / 100), "it_growth_pct": g, "usable": "True",
                         "estab_growth_pct": g / 2, "usable_estab": "True"})
    for coast_i, k in zip(("CA", "NY"), withheld):
        for i in range(k):
            rows.append({"cbsa_code": f"9{len(rows):04d}", "metro_name": f"W{i}, {coast_i} Metro Area", "emp_it_2019": np.nan,
                         "emp_it_2024": np.nan, "it_growth_pct": np.nan, "usable": "False", "estab_growth_pct": 5.0, "usable_estab": "True"})
    return pd.DataFrame(rows)


def test_f_finds_a_planted_west_shortfall():
    r = h.test_f(h.f_data(_geo(shift=-30)), n_boot=500)
    assert r["p"] < 0.01 and r["diff_median"] < 0 and r["predicted_sign"] and r["ci_hi"] < 0
    assert r["n_west"] == 40 and r["n_east"] == 100 and r["n_withheld_west"] == 3 and r["n_withheld_east"] == 20


def test_f_null_is_not_found():
    ps = [h.test_f(h.f_data(_geo(seed=s)), n_boot=20)["p"] for s in range(30)]
    assert np.mean(np.array(ps) < 0.05) <= 0.15


def test_f_placebo_rate_near_five_percent():
    r = h.placebo_f(h.f_data(_geo()), 40, 100, n_rep=400)
    assert 0.01 <= r["share_p_below_005"] <= 0.10 and r["pool"] == 260


def test_f_weighted_growth_is_aggregate_growth():
    sub = pd.DataFrame({"emp_it_2019": [100.0, 900.0], "emp_it_2024": [200.0, 900.0]})
    assert h.weighted_growth(sub) == pytest.approx(10.0)


def test_f_secondary_sections():
    sec = h.secondary_f(h.f_data(_geo(shift=-30)), n_boot=100)
    assert sec["weighted"]["diff"] < 0 and sec["big_metros"]["n_west"] + sec["big_metros"]["n_east"] > 0
    assert sec["establishments"]["n_west"] == 43           # withheld-job metros still have establishment growth


def test_mde_for_registered_counts():
    assert h.mde_d(41, 97) == pytest.approx(0.535, abs=0.01)


# ---------------------------------------------------------------------------------------- B1, figures, results file
def test_slovenia_explore_ranks_changes_and_thousands():
    b1 = h.slovenia_explore(_eurostat(si_change=-2.0))
    assert b1["n"] == 27 and len(b1["series"]) == 11 and b1["break_year"] == 2021
    assert b1["change_2021_2024"]["rank_points"] == 27
    assert b1["series"][0]["min"] <= b1["series"][0]["max"]
    assert isinstance(b1["thousands"], list) and len(b1["thousands"]) == 11


def test_run_pieces_and_figures(tmp_path):
    e = _eurostat(slope=-0.3)
    a2 = {"primary": h.test_a2(h.a2_data(e), n_perm=200, n_boot=100), "slovenia": h.slovenia_a2(h.a2_data(e)),
          "secondary": h.secondary_a2(h.a2_data(e), e, n_perm=100),
          "placebo": h.placebo_a2(h.a2_data(e), 0.1, n_sim=5, n_perm=50),
          "values": {c: {k: float(v) for k, v in r.items()} for c, r in h.a2_data(e).iterrows()}}
    g = h.f_data(_geo(shift=-10))
    p = h.test_f(g, n_boot=100)
    u = g[g["usable"] & g["coast"].notna()]
    f = {"primary": p, "secondary": h.secondary_f(g, n_boot=50), "placebo": h.placebo_f(g, p["n_west"], p["n_east"], n_rep=20),
         "metros": [{"name": n, "coast": c, "growth": x, "jobs_2019": j}
                    for n, c, x, j in zip(u["metro_name"], u["coast"], u["it_growth_pct"], u["emp_it_2019"])]}
    res = {"A2": a2, "F": f, "B1": h.slovenia_explore(e)}
    for k in ("A2", "F"):
        assert {"p", "predicted_sign"} <= set(res[k]["primary"])
    figs = h.build_figures_b(res)
    assert set(figs) == {"11a2_dohitevanje", "11f_obali", "11x_slovenija_delez", "11x_slovenija_rang", "11x_slovenija_sprememba",
                         "11x_slovenija_stevilo"}
    for name, (fig, parts) in figs.items():
        assert fig.layout.title.text, name
        assert all(parts[k].strip() for k in ("kaj", "zakaj", "pomen", "omejitve")), name
        assert "ni potrjena" not in parts["pomen"] and "je potrjena" not in parts["pomen"]     # verdict comes after Holm (notebook 11)
