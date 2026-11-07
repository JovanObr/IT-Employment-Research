"""Like-for-like checks against published studies (analysis/comparisons.py), on synthetic data."""
import numpy as np
import pandas as pd

from analysis import comparisons as cp


def test_two_way_demean_removes_firm_and_quarter_means():
    rng = np.random.default_rng(0)
    d = pd.DataFrame({"cik": np.repeat(range(20), 8), "qi": np.tile(range(8), 20)}).sample(frac=0.9, random_state=1)
    d["x"] = d["cik"] * 2.0 + d["qi"] * 0.5 + rng.normal(size=len(d))
    z = cp.two_way_demean(d, ["x"], "cik", "qi")
    assert np.abs(z["x"].groupby(d["cik"]).mean()).max() < 1e-6 and np.abs(z["x"].groupby(d["qi"]).mean()).max() < 1e-6


def test_ols_cluster_recovers_the_slope():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 2))
    y = X @ np.array([0.5, -0.2]) + rng.normal(scale=0.5, size=2000)
    b, se = cp.ols_cluster(X, y, np.repeat(range(200), 10))
    assert np.allclose(b, [0.5, -0.2], atol=0.05) and (se > 0).all() and (se < 0.05).all()


def _panel(n_firms=300, n_q=16, seed=0):
    """Big firms lay off more (between firms); within a firm, a revenue fall raises the chance (within firms)."""
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({"cik": np.repeat(range(n_firms), n_q), "qi": np.tile(range(n_q), n_firms)})
    size = rng.normal(size=n_firms)
    d["log_assets"] = size[d["cik"]] + rng.normal(scale=0.05, size=len(d))
    d["rev_yoy"] = rng.normal(size=len(d))
    for c in ("rev_qoq", "op_margin", "cash_assets"):
        d[c] = rng.normal(size=len(d))
    d["net_loss"] = (rng.random(len(d)) < 0.3).astype(float)
    p = np.clip(0.05 + 0.04 * d["log_assets"] - 0.04 * d["rev_yoy"], 0, 1)
    d["y_next2q"] = (rng.random(len(d)) < p).astype(int)
    return d


def test_within_firm_model_finds_the_within_effect_and_reports_both_models():
    out = cp.within_firm_model(_panel())
    assert set(out["model"]) == {"med podjetji (FE četrtletja)", "znotraj podjetja (FE podjetja + četrtletja)"}
    fe = out[out["model"].str.startswith("znotraj")].set_index("feature")
    assert fe.loc["rev_yoy", "pp_effect"] < -2 and fe.loc["rev_yoy", "ci_hi"] < 0
    between = out[out["model"].str.startswith("med")].set_index("feature")
    assert between.loc["log_assets", "pp_effect"] > 2 and between.loc["log_assets", "ci_lo"] > 0
    assert (out["firms_with_variation"] <= out["firms"]).all()


def test_rev_decline_is_built_and_kept_as_zero_one():
    out = cp.within_firm_model(_panel(), ("rev_decline", "log_assets"))
    fe = out[out["model"].str.startswith("znotraj")].set_index("feature")
    assert fe.loc["rev_decline", "pp_effect"] > 0                       # a fall in revenue raises the chance


def _layoffs():
    return pd.DataFrame({"company": ["A", "A", "B", "C", "D"], "date": pd.to_datetime(["2023-01-10", "2023-01-10", "2023-02-01", "2023-03-01", "2023-03-05"]),
                         "percentage_laid_off": [0.05, 0.25, None, 0.08, 0.3], "total_laid_off": [100, 50, None, 30, 400],
                         "country": ["United States", "United States", "Canada", "United States", "United States"]})


def _matches():
    return pd.DataFrame({"layoffs_company": ["A", "B", "C", "D"], "cik": [1, 2, 3, 4]})


def test_event_layoff_size_takes_the_largest_share_and_sums_people():
    s = cp.event_layoff_size(_layoffs(), _matches()).set_index("cik")
    assert s.loc[1, "share"] == 0.25 and s.loc[1, "people"] == 150
    assert np.isnan(s.loc[2, "share"]) and np.isnan(s.loc[2, "people"])


def test_stock_by_share_compares_big_and_small_layoffs():
    rng = np.random.default_rng(0)
    n = 300
    share = rng.choice([0.03, 0.08, 0.15, 0.3, np.nan], size=n)
    days = pd.bdate_range("2022-01-03", periods=n)
    cars = pd.DataFrame({"event_id": range(n), "cik": range(n), "date": days, "event_day": days,
                         "car_ann_0_1": np.where(np.nan_to_num(share) > 0.1, -0.03, 0.0) + rng.normal(scale=0.01, size=n),
                         "t_ann_0_1": rng.normal(size=n), "n_est": 200})
    size = pd.DataFrame({"cik": range(n), "date": days, "share": share, "people": 10.0})
    out = cp.stock_by_share(cars, size, n_boot=200)
    assert set(out["by_group"]["share_group"]) == {"do 5 %", "5-10 %", "10-20 %", "nad 20 %", "ni podatka"}
    diff = out["diff_big_minus_small"]
    assert diff["diff_pct"] < -2 and diff["ci_hi_pct"] < 0 and out["spearman"] < 0 and out["spearman_p"] < 0.05


def test_headcount_table_blanks_parsing_jumps():
    heads = pd.DataFrame({"cik": [1] * 4 + [2] * 4, "period_year": [2019, 2021, 2022, 2023] * 2,
                          "employees": [100, 150, 160, 140, 100, 5000, 120, 110]})
    w = cp.headcount_table(heads).set_index("cik")
    assert np.isclose(w.loc[1, "hire_growth"], np.log(1.5)) and np.isclose(w.loc[1, "cut_22_23"], np.log(140 / 160))
    assert np.isnan(w.loc[2, "hire_growth"])                            # 100 -> 5000 is a 50x jump


def test_headcount_overhiring_links_fast_hiring_to_later_cuts():
    rng = np.random.default_rng(0)
    n = 200
    g = rng.normal(0.3, 0.3, n)
    heads = pd.concat([pd.DataFrame({"cik": range(n), "period_year": y, "employees": e}) for y, e in
                       ((2019, 1000.0), (2021, 1000 * np.exp(g)), (2022, 1000 * np.exp(g + 0.05)),
                        (2023, 1000 * np.exp(g + 0.05 - 0.3 * g + rng.normal(0, 0.02, n))))])
    boom = pd.DataFrame({"cik": range(n), "y_layoff": (g + rng.normal(0, 0.2, n) > 0.45).astype(int), "boom_growth": g + rng.normal(0, 0.1, n),
                         "log_assets_start": rng.normal(size=n), "sic2": "73"})
    out = cp.headcount_overhiring(heads, boom, n_boot=100)
    assert out["n"] == n and out["cut"]["spearman"] < -0.5 and out["cut"]["ci_hi"] < 0
    q = out["quartiles"]
    assert q["rate"].iloc[-1] > q["rate"].iloc[0]
    assert 0 <= out["cut_vs_hire"]["share_still_above_2019"] <= 1


def test_challenger_compare_counts_us_companies_only():
    ref = [{"period": "2023Q1", "start": "2023-01-01", "end": "2023-03-31", "challenger": 1000, "url": "u"}]
    t = cp.challenger_compare(_layoffs(), ref).iloc[0]
    assert t["tracker_us"] == 580 and t["tracker_all_countries"] == 580 and t["tracker_us_announcements"] == 4
    assert np.isclose(t["ratio_us_to_challenger"], 0.58) and np.isclose(t["share_with_number"], 1.0)


def test_challenger_reference_values_are_the_published_ones():
    v = {r["period"]: r["challenger"] for r in cp.CHALLENGER}
    assert v["2022"] == 97_171 and v["2023"] == 168_032 and v["2024"] == 133_988 and v["2025"] == 154_445
    assert all(r["url"].startswith("https://www.challengergray.com/") for r in cp.CHALLENGER)
