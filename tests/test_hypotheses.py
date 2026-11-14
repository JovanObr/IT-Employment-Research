"""Milestone 3 tests C and D: a planted effect must be found, a null must not be (synthetic data only)."""
import numpy as np
import pandas as pd

from analysis import hypotheses as hy


def test_holm_matches_the_textbook_example():
    out = hy.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.005}).set_index("hypothesis")
    assert np.isclose(out.loc["d", "p_holm"], 0.02) and np.isclose(out.loc["a", "p_holm"], 0.03)
    assert np.isclose(out.loc["c", "p_holm"], 0.06) and np.isclose(out.loc["b", "p_holm"], 0.06)
    assert list(out["reject"]) == [True, True, False, False]


def test_holm_is_monotone_and_capped():
    out = hy.holm({"a": 0.5, "b": 0.6})
    assert (out["p_holm"].diff().dropna() >= 0).all() and out["p_holm"].max() <= 1


def test_mde_shrinks_with_sample_size():
    assert hy.mde(1, 400, 400) < hy.mde(1, 100, 100)
    assert np.isclose(hy.mde(1, 100, 100), 2.8 * np.sqrt(0.02), atol=0.01)


def _heads(n=400, effect=-0.15, seed=0):
    rng = np.random.default_rng(seed)
    ann = rng.random(n) < 0.25
    e21 = rng.lognormal(6, 1, n)
    e23 = e21 * np.exp(rng.normal(0.02, 0.2, n) + effect * ann)
    h = pd.concat([pd.DataFrame({"cik": range(n), "period_year": y, "employees": e}) for y, e in ((2021, e21), (2023, e23))])
    uni = pd.DataFrame({"cik": range(n), "is_tech": True, "sic": "7372"})
    return h, uni, set(np.flatnonzero(ann))


def test_c_finds_a_planted_headcount_cut_and_not_a_null():
    h, uni, ann = _heads()
    r = hy.test_c(hy.headcount_sample(h, uni, ann), n_boot=500)
    assert r["p"] < 0.01 and r["predicted_sign"] and r["ci_hi"] < 0
    h0, uni0, ann0 = _heads(effect=0.0, seed=1)
    d0 = hy.headcount_sample(h0, uni0, ann0)
    assert hy.test_c(d0, n_boot=200)["p"] > 0.05
    fp = hy.placebo_c(d0, n_rep=300)["false_positive_rate"]
    assert 0.0 <= fp <= 0.1


def test_headcount_sample_drops_parsing_jumps_and_non_tech():
    h = pd.DataFrame({"cik": [1, 1, 2, 2, 3, 3], "period_year": [2021, 2023] * 3, "employees": [100, 90, 100, 5000, 100, 80]})
    uni = pd.DataFrame({"cik": [1, 2, 3], "is_tech": [True, True, False], "sic": ["7372", "7372", "2834"]})
    d = hy.headcount_sample(h, uni, {1})
    assert list(d["cik"]) == [1] and d["announced"].tolist() == [1]


def test_announced_ciks_uses_the_exposure_window():
    lay = pd.DataFrame({"company": ["A", "B", "C"], "date": ["2022-05-01", "2021-12-31", "2024-01-02"]})
    m = pd.DataFrame({"layoffs_company": ["A", "B", "C"], "cik": [1, 2, 3]})
    assert hy.announced_ciks(lay, m) == {1}


def test_secondary_c_recovers_the_effect_with_size_control():
    h, uni, ann = _heads(n=600)
    d = hy.headcount_sample(h, uni, ann)
    d["log_assets"] = np.random.default_rng(2).normal(size=len(d))
    r = hy.secondary_c(d)
    assert r["ci_hi"] < 0 and r["p"] < 0.01


def test_ols_hc3_matches_plain_ols_coefficients():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(300), rng.normal(size=300)])
    y = X @ [1.0, 2.0] + rng.normal(size=300)
    b, se = hy.ols_hc3(y, X)
    assert np.allclose(b, np.linalg.lstsq(X, y, rcond=None)[0]) and (se > 0).all()


def _cars(n=600, effect=-0.03, seed=0):
    rng = np.random.default_rng(seed)
    rep = (rng.random(n) < 0.6).astype(int)
    days = pd.bdate_range("2021-01-04", periods=n)
    return pd.DataFrame({"cik": range(n), "ticker": [f"T{i}" for i in range(n)], "date": days, "event_day": days, "repeat": rep,
                         "car_ann_0_1": rng.normal(0, 0.05, n) + effect * rep, "t_ann_0_1": 0.0, "n_est": 200})


def test_d_finds_a_planted_repeat_penalty_and_not_a_null():
    r = hy.test_d(_cars(), n_perm=2000)
    assert r["p"] < 0.01 and r["predicted_sign"] and r["diff_pct"] < -2
    assert hy.test_d(_cars(effect=0.0, seed=3), n_perm=2000)["p"] > 0.05


def test_perm_diff_p_is_never_zero():
    diff, p = hy.perm_diff(np.r_[np.zeros(50), np.ones(50)], np.r_[np.zeros(50, int), np.ones(50, int)], n_perm=200)
    assert diff == 1 and 0 < p <= 1 / 201 + 1e-12


def test_label_repeat_counts_any_earlier_tracker_row():
    cars = pd.DataFrame({"cik": [1, 1, 2], "date": pd.to_datetime(["2022-01-10", "2022-06-01", "2022-03-01"])})
    lay = pd.DataFrame({"company": ["A", "A", "B", "A"], "date": ["2022-01-10", "2022-06-01", "2022-03-01", "2021-12-20"]})
    m = pd.DataFrame({"layoffs_company": ["A", "B"], "cik": [1, 2]})
    assert hy.label_repeat(cars, lay, m)["repeat"].tolist() == [1, 1, 0]    # A's earlier 2021 row makes both A events repeats


def test_file_hashes_marks_missing_files(tmp_path):
    f = tmp_path / "x.csv"; f.write_text("a")
    h = hy.file_hashes([f, tmp_path / "nope.csv"])
    assert len(h[str(f).replace("\\", "/")]) == 64 and h[str(tmp_path / "nope.csv").replace("\\", "/")] == "missing"
