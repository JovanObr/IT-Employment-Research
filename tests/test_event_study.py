"""Event study on synthetic prices with a KNOWN effect: no network, no Yahoo."""
import numpy as np
import pandas as pd
import pytest

from analysis import event_study as es

DAYS = pd.bdate_range("2019-01-01", "2023-12-29")


def make_returns(n_stocks=3, effect=0.03, event_idx=(), seed=0, beta=1.2):
    """Market + stocks with beta `beta`; `effect` is added to a stock's return on each of its event days."""
    rng = np.random.default_rng(seed)
    rm = rng.normal(0.0004, 0.01, len(DAYS))
    data = {"^IXIC": rm}
    for k in range(n_stocks):
        r = 0.0002 + beta * rm + rng.normal(0, 0.015, len(DAYS))
        for i in event_idx:
            r[i + k * 0] += effect
        data[f"S{k}"] = r
    return pd.DataFrame(data, index=pd.DatetimeIndex(DAYS, name="date"))


def make_events(rets, idx_list, tickers):
    rows = [{"event_id": j, "cik": 100 + int(t[1:]), "ticker": t, "date": rets.index[i]} for j, (i, t) in enumerate(
        (i, t) for t in tickers for i in idx_list)]
    return pd.DataFrame(rows)


def test_model_recovers_beta_and_flags_too_little_history():
    r = make_returns(1, effect=0.0)
    fit = es.market_model(r["S0"].to_numpy(), r["^IXIC"].to_numpy(), 600)
    assert fit[1] == pytest.approx(1.2, abs=0.12) and fit[3] == 221
    assert es.market_model(r["S0"].to_numpy(), r["^IXIC"].to_numpy(), 100) is None          # fewer than 250 days of history


def test_injected_abnormal_return_shows_up_in_the_announcement_window_only():
    idx = list(range(400, 1200, 25))                                       # 32 events per stock, far apart
    r = make_returns(3, effect=0.03, event_idx=idx)
    ev = make_events(r, idx, ["S0", "S1", "S2"])
    cars, lost = es.run_event_study(ev, r)
    assert len(cars) == len(ev) and sum(lost.values()) == 0
    s = es.summary_table(cars, n_boot=300).set_index("window")
    assert s.loc["ann_0_1", "mean_pct"] == pytest.approx(3.0, abs=0.7)      # +3 % on day 0 (day +1 is noise)
    assert s.loc["ann_0_1", "t"] > 5 and s.loc["ann_0_1", "patell_z"] > 5
    assert abs(s.loc["pre_5_2", "mean_pct"]) < 1.0 and abs(s.loc["post_2_5", "mean_pct"]) < 1.5
    assert s.loc["ann_0_1", "ci_lo_pct"] < s.loc["ann_0_1", "mean_pct"] < s.loc["ann_0_1", "ci_hi_pct"]


def test_no_effect_gives_no_signal():
    idx = list(range(400, 1200, 25))
    r = make_returns(3, effect=0.0, event_idx=idx, seed=3)
    cars, _ = es.run_event_study(make_events(r, idx, ["S0", "S1", "S2"]), r)
    s = es.summarize(cars, n_boot=300)
    assert s["ci_lo_pct"] < 0 < s["ci_hi_pct"]


def test_weekend_event_moves_to_the_next_trading_day():
    days = DAYS
    saturday = pd.Timestamp("2021-03-06")
    assert saturday.weekday() == 5
    pos = es.event_position(saturday, days)
    assert days[pos] == pd.Timestamp("2021-03-08")
    assert es.event_position(pd.Timestamp("2030-01-01"), days) is None


def test_events_without_prices_history_or_room_are_counted_not_silently_dropped():
    r = make_returns(1, effect=0.0)
    ev = pd.DataFrame([{"event_id": 0, "cik": 1, "ticker": "NOPE", "date": r.index[500]},        # no prices
                       {"event_id": 1, "cik": 2, "ticker": "S0", "date": r.index[100]},          # too little history
                       {"event_id": 2, "cik": 2, "ticker": "S0", "date": r.index[len(r) - 3]},   # window runs past the data
                       {"event_id": 3, "cik": 2, "ticker": "S0", "date": pd.Timestamp("2031-01-01")},
                       {"event_id": 4, "cik": 2, "ticker": "S0", "date": r.index[700]}])
    cars, lost = es.run_event_study(ev, r)
    assert list(cars["event_id"]) == [4]
    assert lost == {"no_prices": 1, "after_last_day": 1, "too_little_history_or_window": 2}


def test_drop_clustered_keeps_first_event_of_a_burst():
    e = pd.DataFrame({"cik": [1, 1, 1, 2], "ticker": "A", "date": pd.to_datetime(["2022-01-10", "2022-01-25", "2022-03-01", "2022-01-12"])})
    out = es.drop_clustered(e, 30)
    assert sorted(zip(out["cik"], out["date"].dt.strftime("%m-%d"))) == [(1, "01-10"), (1, "03-01"), (2, "01-12")]


def test_build_events_matches_names_and_normalises_tickers():
    lay = pd.DataFrame({"company": ["Alpha", "Alpha", "Beta", "Gamma"], "date": pd.to_datetime(["2022-05-02", "2022-05-02", "2022-06-01", "2022-07-01"])})
    mt = pd.DataFrame({"layoffs_company": ["Alpha", "Beta", "Gamma"], "cik": [1, 2, 3], "ticker": ["BRK.B", None, "G"]})
    ev = es.build_events(lay, mt)
    assert list(ev["ticker"]) == ["BRK-B", "G"] and list(ev["event_id"]) == [0, 1]       # Beta has no ticker; duplicate Alpha row dropped


def test_summary_resamples_days_not_events():
    # 40 events on only 4 distinct days with day-specific shocks: the interval must be wider than a per-event interval
    rng = np.random.default_rng(0)
    days = pd.to_datetime(["2022-01-03", "2022-02-01", "2022-03-01", "2022-04-01"])
    d = pd.DataFrame({"event_day": np.repeat(days, 10), "n_est": 220})
    d["car_ann_0_1"] = np.repeat([0.05, -0.04, 0.03, -0.02], 10) + rng.normal(0, 0.002, 40)
    d["t_ann_0_1"] = d["car_ann_0_1"] / 0.02
    s = es.summarize(d, n_boot=500)
    naive_se = 100 * d["car_ann_0_1"].std(ddof=1) / np.sqrt(40)
    assert (s["ci_hi_pct"] - s["ci_lo_pct"]) / 3.92 > 1.5 * naive_se


def test_placebo_false_positive_rate_is_near_five_percent_under_the_null():
    idx = list(range(400, 1200, 25))
    r = make_returns(3, effect=0.0, event_idx=[], seed=5)
    ev = make_events(r, idx, ["S0", "S1", "S2"])
    cars, _ = es.run_event_study(ev, r)
    pl = es.placebo_test(cars[["event_id", "ticker", "date"]], r, n_rep=60, seed=1)
    assert abs(pl["mean_of_means_pct"]) < 0.5 and pl["false_positive_rate"] < 0.2


def test_size_uses_only_balance_sheets_that_were_public_before_the_event():
    # Q4 2021 ends 31 Dec; with a 45-day filing lag it is public from 14 Feb. Q1 2022 ends 31 Mar and is public from 15 May.
    fin = pd.DataFrame({"cik": [1, 1], "concept": "assets", "kind": "instant", "period": ["CY2021Q4I", "CY2022Q1I"], "value": [100.0, 400.0]})
    ev = pd.DataFrame({"event_id": [0, 1, 2, 3], "cik": 1, "ticker": "A",
                       "date": pd.to_datetime(["2022-02-01", "2022-03-01", "2022-05-01", "2022-06-15"])})
    out = es.attach_size(ev, fin).set_index("event_id")["log_assets"]
    assert np.isnan(out[0])                                                       # nothing public yet
    assert out[1] == pytest.approx(np.log(100)) and out[2] == pytest.approx(np.log(100))
    assert out[3] == pytest.approx(np.log(400))


def test_group_summary_leaves_small_groups_without_an_interval():
    d = pd.DataFrame({"g": ["a"] * 30 + ["b"] * 5, "event_day": pd.bdate_range("2022-01-03", periods=35), "n_est": 220})
    d["car_ann_0_1"] = np.random.default_rng(0).normal(0, 0.02, 35)
    d["t_ann_0_1"] = d["car_ann_0_1"] / 0.02
    g = es.group_summary(d, "g").set_index("g")
    assert not np.isnan(g.loc["a", "ci_lo_pct"]) and np.isnan(g.loc["b", "ci_lo_pct"]) and g.loc["b", "n"] == 5


# ----------------------------------------------------------------------------- robustness and paths
def test_winsorize_clips_extreme_moves_but_not_the_rest():
    v = np.r_[np.random.default_rng(0).normal(0, 0.02, 198), 5.0, -4.0]
    d = pd.DataFrame({"car_ann_0_1": v, "t_ann_0_1": v / 0.02, "n_est": 220})
    w = es.winsorize_cars(d, 0.01)
    assert w["car_ann_0_1"].max() < 0.2 and w["car_ann_0_1"].min() > -0.2 and (w["n_est"] == 220).all()
    assert np.median(w["car_ann_0_1"]) == pytest.approx(np.median(v))


def test_largest_moves_sorts_by_absolute_size():
    d = pd.DataFrame({"ticker": list("ABC"), "date": pd.Timestamp("2022-01-03"), "car_ann_0_1": [0.01, -0.40, 0.20], "beta": 1, "resid_sd": 0.02})
    assert list(es.largest_moves(d, k=2)["ticker"]) == ["B", "C"]


def test_group_difference_recovers_a_known_gap_and_its_interval():
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2022-01-03", periods=120)
    d = pd.DataFrame({"event_day": np.tile(days, 2), "g": ["small"] * 120 + ["big"] * 120, "n_est": 220})
    d["car_ann_0_1"] = np.r_[rng.normal(-0.01, 0.02, 120), rng.normal(0.005, 0.02, 120)]
    r = es.group_difference(d, "g", "small", "big", n_boot=500)
    assert r["diff_pct"] == pytest.approx(-1.5, abs=0.6) and r["ci_lo_pct"] < r["diff_pct"] < r["ci_hi_pct"] and r["ci_hi_pct"] < 0.5
    same = d.assign(g=np.tile(["a", "b"], 120))
    assert es.group_difference(same, "g", "a", "b", n_boot=500)["ci_lo_pct"] < 0 < es.group_difference(same, "g", "a", "b", n_boot=500)["ci_hi_pct"]


def test_average_path_jumps_on_the_event_day_and_not_before():
    idx = list(range(400, 1200, 25))
    r = make_returns(3, effect=0.03, event_idx=idx, seed=2)
    ev = make_events(r, idx, ["S0", "S1", "S2"])
    paths = es.ar_paths(ev, r)
    assert len(paths) == len(ev) and list(paths.columns[2:]) == list(range(-5, 11))
    p = es.path_summary(paths, n_boot=300, winsor=None).set_index("t")
    assert abs(p.loc[-1, "mean_pct"]) < 1.0 and p.loc[0, "mean_pct"] - p.loc[-1, "mean_pct"] == pytest.approx(3.0, abs=0.8)
    assert (p["lo_pct"] <= p["mean_pct"]).all() and (p["mean_pct"] <= p["hi_pct"]).all()


def test_placebo_reports_both_false_positive_rates():
    idx = list(range(400, 1200, 40))
    r = make_returns(2, effect=0.0, seed=6)
    cars, _ = es.run_event_study(make_events(r, idx, ["S0", "S1"]), r)
    pl = es.placebo_test(cars[["event_id", "ticker", "date"]], r, n_rep=30, seed=2)
    assert {"patell_false_positive_rate", "sd_of_medians_pct", "false_positive_rate", "bootstrap_false_positive_rate"} <= set(pl)
    assert 0 <= pl["patell_false_positive_rate"] <= 1 and 0 <= pl["bootstrap_false_positive_rate"] <= 0.3


def test_extreme_daily_returns_lists_the_biggest_moves_and_skips_benchmarks():
    r = make_returns(2, effect=0.0, seed=7)
    r.iloc[300, r.columns.get_loc("S0")] = 15.0                         # a +1500 % glitch
    r.iloc[310, r.columns.get_loc("^IXIC")] = 9.0                       # benchmark moves are not reported
    ex = es.extreme_daily_returns(r, k=3)
    assert ex.iloc[0]["ticker"] == "S0" and ex.iloc[0]["ret_pct"] == pytest.approx(1500.0) and "^IXIC" not in set(ex["ticker"])
    assert list(ex.columns) == ["ticker", "date", "ret_pct"] and len(ex) == 3


def test_clean_returns_blanks_glitches_but_not_normal_days_or_benchmarks():
    r = make_returns(2, effect=0.0, seed=9)
    r.iloc[300, r.columns.get_loc("S0")] = 15.0
    r.iloc[301, r.columns.get_loc("S0")] = 1.5
    r.iloc[310, r.columns.get_loc("^IXIC")] = 2.0                         # benchmark left alone
    c, rep = es.clean_returns(r)
    assert np.isnan(c["S0"].iloc[300]) and np.isnan(c["S0"].iloc[301]) and c["^IXIC"].iloc[310] == 2.0
    assert c["S1"].equals(r["S1"]) and c["S0"].drop(c.index[[300, 301]]).equals(r["S0"].drop(r.index[[300, 301]]))
    assert list(rep["ticker"]) == ["S0"] and rep.iloc[0]["n_masked"] == 2 and rep.iloc[0]["largest_pct"] == pytest.approx(1500.0)
    assert r["S0"].iloc[300] == 15.0                                      # the input is not modified


def test_a_glitch_inside_the_fitting_window_no_longer_ruins_the_model():
    r = make_returns(1, effect=0.0, seed=10)
    r.iloc[700, r.columns.get_loc("S0")] = 50.0                           # +5000 % inside the 250..30 days before an event at 800
    raw_fit = es.market_model(r["S0"].to_numpy(), r["^IXIC"].to_numpy(), 800)
    c, _ = es.clean_returns(r)
    clean_fit = es.market_model(c["S0"].to_numpy(), c["^IXIC"].to_numpy(), 800)
    assert abs(raw_fit[1] - 1.2) > 0.3 and abs(clean_fit[1] - 1.2) < 0.15 and clean_fit[3] == 220
    assert clean_fit[2] < 0.1 * raw_fit[2] * 10 and clean_fit[2] < 0.03


def test_event_with_a_blanked_day_in_its_window_has_no_car_for_that_window():
    r = make_returns(1, effect=0.0, seed=11)
    r.iloc[801, r.columns.get_loc("S0")] = 9.0                            # day +1 of an event at 800
    c, _ = es.clean_returns(r)
    ev = pd.DataFrame([{"event_id": 0, "cik": 1, "ticker": "S0", "date": r.index[800]}])
    cars, _ = es.run_event_study(ev, c)
    assert np.isnan(cars.iloc[0]["car_ann_0_1"]) and np.isfinite(cars.iloc[0]["car_pre_1"])
    assert es.summarize(cars).get("n") == 0
