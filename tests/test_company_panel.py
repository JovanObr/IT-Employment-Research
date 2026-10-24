"""A3 panel tests: lag, look-ahead, gaps, label windows. Synthetic data only."""
import numpy as np
import pandas as pd
import pytest

from analysis import company_panel as cp


def test_qindex_roundtrip_and_instant_suffix():
    assert cp.qindex("CY2022Q3") == cp.qindex("CY2022Q3I") == 2022 * 4 + 2
    assert cp.qlabel(cp.qindex("CY2022Q1")) == "2022Q1"
    assert cp.qindex("CY2022Q4") - cp.qindex("CY2022Q3") == 1
    with pytest.raises(ValueError):
        cp.qindex("CY2022")


def _q(rows):
    return pd.DataFrame(rows).assign(**{c: np.nan for c in cp.FLOWS + cp.INSTANTS if c not in rows[0]})


def test_growth_uses_quarter_index_not_row_order():
    # cik 1 has revenue in 2020Q1, 2021Q1 (4 quarters later) and 2021Q3 (gap: 2021Q2 missing)
    q = _q([{"cik": 1, "qi": cp.qindex("CY2020Q1"), "revenue": 100.0},
            {"cik": 1, "qi": cp.qindex("CY2021Q1"), "revenue": 150.0},
            {"cik": 1, "qi": cp.qindex("CY2021Q3"), "revenue": 180.0}])
    f = cp.add_features(q).set_index("qi")
    assert f.loc[cp.qindex("CY2021Q1"), "rev_yoy"] == pytest.approx(0.5)
    assert np.isnan(f.loc[cp.qindex("CY2021Q1"), "rev_qoq"])        # 2020Q4 missing
    assert np.isnan(f.loc[cp.qindex("CY2021Q3"), "rev_qoq"])        # 2021Q2 missing, no comparison across the gap
    assert np.isnan(f.loc[cp.qindex("CY2021Q3"), "rev_yoy"])        # 2020Q3 missing


def test_ratios_undefined_for_nonpositive_denominators():
    q = _q([{"cik": 1, "qi": 8000, "revenue": 0.0, "gross_profit": 5.0, "assets": -1.0, "cash": 2.0, "net_income": -3.0}])
    f = cp.add_features(q).iloc[0]
    assert np.isnan(f["gross_margin"]) and np.isnan(f["cash_assets"]) and np.isnan(f["log_assets"])
    assert f["net_loss"] == 1.0


def test_net_loss_missing_stays_missing():
    f = cp.add_features(_q([{"cik": 1, "qi": 8000, "revenue": 1.0}])).iloc[0]
    assert np.isnan(f["net_loss"])


def test_lag_moves_features_forward_and_drops_rows_without_revenue():
    q = cp.add_features(_q([{"cik": 1, "qi": 8000, "revenue": 10.0},
                            {"cik": 1, "qi": 8001, "revenue": np.nan, "net_income": -1.0}]))
    out = cp.lag_features(q, lag=1)
    assert out["qi"].tolist() == [8001]                      # the filing quarter 8000 is used in row quarter 8001
    assert out["revenue_lagged"].tolist() == [10.0]


def _date_in(qi, day=15):
    return pd.Timestamp(year=qi // 4, month=3 * (qi % 4) + 1, day=day)


def test_label_window_is_strictly_future():
    base = pd.DataFrame({"cik": [1] * 6, "qi": range(8000, 8006)})
    ev = pd.DataFrame({"cik": [1], "date": [_date_in(8003)]})          # one event, in quarter 8003
    out = cp.add_labels(base, ev, first_full=7990, last_full=8100).set_index("qi")["y_next2q"]
    assert out.loc[8001] == 1 and out.loc[8002] == 1          # event is 2 and 1 quarters ahead
    assert out.loc[8003] == 0                                 # the event quarter itself is NOT in its own window
    assert out.loc[8000] == 0 and out.loc[8004] == 0


def test_one_positive_per_window_even_with_many_events():
    d = pd.Timestamp(year=8002 // 4, month=3 * (8002 % 4) + 1, day=5)
    ev = pd.DataFrame({"cik": [1, 1, 1], "date": [d, d + pd.Timedelta(days=20), d + pd.Timedelta(days=40)]})
    out = cp.add_labels(pd.DataFrame({"cik": [1], "qi": [8001]}), ev, 7990, 8100)
    assert out["y_next2q"].tolist() == [1]


def test_rows_outside_tracker_window_are_dropped():
    base = pd.DataFrame({"cik": [1] * 6, "qi": [7989, 7990, 7991, 8009, 8010, 8011]})
    ev = pd.DataFrame({"cik": pd.Series([], dtype=int), "date": pd.to_datetime([])})
    out = cp.add_labels(base, ev, first_full=7991, last_full=8011)
    # row t needs t+1 >= 7991 (t >= 7990) and t+2 <= 8011 (t <= 8009)
    assert out["qi"].tolist() == [7990, 7991, 8009]


def test_tracker_window_excludes_first_and_last_partial_quarter():
    ev = pd.DataFrame({"date": pd.to_datetime(["2020-03-11", "2021-06-01", "2026-08-20"])})
    first, last = cp.tracker_window(ev)
    assert cp.qlabel(first) == "2020Q2" and cp.qlabel(last) == "2026Q2"


def test_build_panel_end_to_end_no_leak():
    # one tech company with 12 quarters of data from 2019Q1; layoff in 2021Q3; tracker spans 2019Q4 .. 2023Q2
    periods = [f"CY{y}Q{q}" for y in (2019, 2020, 2021) for q in (1, 2, 3, 4)]
    revenue = pd.DataFrame({"cik": 1, "period": periods, "revenue": [100.0 + 10 * i for i in range(12)],
                            "tag": "Revenues", "kind": "quarter"})
    fin = pd.DataFrame({"cik": [1] * 12, "period": periods, "concept": "net_income", "value": -1.0,
                        "kind": "quarter", "tag": "x"})
    uni = pd.DataFrame({"cik": [1, 2], "name": ["Soft", "Bank"], "sic": ["7372", "6022"], "ticker": ["S", "B"],
                        "is_tech": [True, False]})
    matches = pd.DataFrame({"layoffs_company": ["Soft Inc"], "cik": [1]})
    events = pd.DataFrame({"company": ["Soft Inc", "Other", "Other"],
                           "date": pd.to_datetime(["2021-08-10", "2019-10-02", "2023-05-02"])})
    panel = cp.build_panel(fin, revenue, uni, matches, events)
    assert set(panel["cik"]) == {1}                                    # the bank is not in the tech universe
    pos = panel[panel["y_next2q"] == 1]["quarter"].tolist()
    assert pos == ["2021Q1", "2021Q2"]                                 # windows t+1..t+2 that contain 2021Q3
    assert "2021Q3" not in pos
    # tracker: first event 2019Q4, last 2023Q2 -> fully observed 2020Q1 .. 2023Q1; rows need t+1 >= 2020Q1 and t+2 <= 2023Q1,
    # and features exist only from 2019Q2 (filing quarter 2019Q1 + lag) up to 2022Q1 (filing quarter 2021Q4 + lag)
    assert panel["quarter"].iloc[0] == "2019Q4" and panel["quarter"].iloc[-1] == "2022Q1"
