"""A4 tests: macro parsers and the three causes analyses on synthetic data. No network."""
import json

import numpy as np
import pandas as pd
import pytest
import requests

from analysis import causes as cs
from collectors import macro


# ----------------------------------------------------------------------------- collectors/macro.py
def test_parse_fred_new_and_old_headers_and_missing_dots():
    new = b"observation_date,FEDFUNDS\n2022-01-01,0.08\n2022-02-01,.\n2022-03-01,0.20\n"
    old = b"DATE,NASDAQCOM\n2022-01-03,15000.5\n2022-01-04,.\n"
    a = macro.parse_fred(new, "FEDFUNDS")
    assert a["value"].tolist() == [0.08, 0.20] and list(a.columns) == ["series_id", "date", "value"]
    b = macro.parse_fred(old, "NASDAQCOM")
    assert b["value"].tolist() == [15000.5] and b["series_id"].iloc[0] == "NASDAQCOM"


def test_collect_fred_rejects_html_error_page(monkeypatch):
    def fake(url, params=None, **kw):
        return b"<html>error</html>" if params["id"] == "DFF" else f"observation_date,{params['id']}\n2022-01-01,1\n".encode()
    monkeypatch.setattr(macro, "fetch", fake)
    df = macro.collect_fred(2020)
    assert set(df["series_id"]) == {"FEDFUNDS", "NASDAQCOM"}


JOLTS_REPLY = {"status": "REQUEST_SUCCEEDED", "message": [], "Results": {"series": [
    {"seriesID": "JTS510000000000000LDL", "data": [
        {"year": "2023", "period": "M01", "value": "42"}, {"year": "2023", "period": "M13", "value": "40"},
        {"year": "2022", "period": "M12", "value": "-"}]},
    {"seriesID": "JTS510000000000000QUL", "data": []}]}}


def test_parse_jolts_skips_annual_and_non_numeric(caplog):
    df = macro.parse_jolts(JOLTS_REPLY, macro.JOLTS_SERIES)
    assert len(df) == 2 and df["date"].min() == pd.Timestamp("2022-12-01")
    assert df.loc[df["date"] == "2023-01-01", "value"].iloc[0] == 42
    assert np.isnan(df.loc[df["date"] == "2022-12-01", "value"].iloc[0])
    assert "no data for JTS510000000000000QUL" in caplog.text


def test_jolts_series_ids_follow_the_documented_pattern():
    for sid in macro.JOLTS_SERIES:
        assert len(sid) == 21 and sid.startswith("JTS") and sid[-3:-1] in {"JO", "HI", "LD", "QU"} and sid[-1] in "LR"


def test_collect_jolts_uses_one_request_per_ten_years(monkeypatch):
    calls = []
    monkeypatch.setattr(macro, "fetch", lambda url, **kw: calls.append(kw["json_body"]) or json.dumps(JOLTS_REPLY).encode())
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    df = macro.collect_jolts(2015, 2026)
    assert [(c["startyear"], c["endyear"]) for c in calls] == [("2015", "2024"), ("2025", "2026")]
    assert "registrationkey" not in calls[0] and df["series_id"].nunique() == 1


def test_macro_source_registered():
    assert "macro" in macro.SOURCES


# ----------------------------------------------------------------------------- H1
def test_xcorr_positive_lag_means_x_leads():
    rng = np.random.default_rng(0)
    x = rng.normal(size=120)
    y = np.roll(x, 3) + 0.1 * rng.normal(size=120)                        # y_t = x_{t-3}: x comes first
    r = cs.lead_lag_test(pd.Series(x), pd.Series(y), max_lag=6)
    assert r["best_lag"] == 3 and r["best_corr"] > 0.9 and r["p_value"] < 0.05


def test_lead_lag_independent_noise_is_not_significant():
    rng = np.random.default_rng(1)
    def ar1(n):
        e, v = rng.normal(size=n), np.zeros(n)
        for t in range(1, n):
            v[t] = 0.9 * v[t - 1] + e[t]
        return pd.Series(v)
    r = cs.lead_lag_test(ar1(80), ar1(80), max_lag=12)
    assert r["p_value"] > 0.05 and len(r["table"]) == 25 and r["n_months"] == 80


def test_p_value_cannot_be_smaller_than_the_number_of_shifts_allows():
    x = pd.Series(np.sin(np.arange(76) / 6.0))
    r = cs.lead_lag_test(x, x * 2.0, max_lag=12)                        # identical shape: as significant as it gets
    assert r["n_shifts"] == 76 - 2 * 12 - 1
    assert r["p_value"] == pytest.approx(1 / (r["n_shifts"] + 1))
    assert r["p_value"] > 0.015                                         # never reported as 0.000


def test_monthly_layoffs_complete_months_and_zeros():
    ev = pd.DataFrame({"date": pd.to_datetime(["2020-03-11", "2020-04-05", "2020-04-20", "2020-06-02", "2020-07-09"]),
                       "region": ["US", "US", "US", "US", "Europe"], "total_laid_off": [10, 5, 7, 3, 99]})
    m = cs.monthly_layoffs(ev)
    assert list(m.index.strftime("%Y-%m")) == ["2020-04", "2020-05", "2020-06"]   # March and July (first/last) are partial
    assert m["events"].tolist() == [2, 0, 1] and m["laid_off"].tolist() == [12, 0, 3]


def test_weekly_layoffs_monday_weeks_and_complete_only():
    ev = pd.DataFrame({"date": pd.to_datetime(["2022-03-02", "2022-03-09", "2022-03-10", "2022-03-30", "2022-04-20"]),
                       "region": "US", "total_laid_off": 1})
    w = cs.weekly_layoffs(ev)
    assert w.index[0] == pd.Timestamp("2022-03-07") and all(d.weekday() == 0 for d in w.index)
    assert w.loc["2022-03-07"] == 2 and w.loc["2022-03-14"] == 0 and w.index[-1] == pd.Timestamp("2022-04-11")


# ----------------------------------------------------------------------------- H2
def _weekly(step_at, n=200, low=1.0, high=6.0):
    idx = pd.date_range("2020-06-01", periods=n, freq="7D")
    return pd.Series(np.where(np.arange(n) < step_at, low, high), index=idx, name="events")


def test_event_study_step_function():
    s = _weekly(100)
    r = cs.event_study(s, s.index[100] + pd.Timedelta(days=3))            # a Thursday inside the step week
    assert r["before_mean"] == 1.0 and r["after_mean"] == 6.0 and r["diff"] == 5.0 and r["ratio"] == 6.0
    assert r["rank_share"] == 1.0                                         # nothing in the sample jumps more
    assert r["largest_jump_date"] == s.index[100]
    far = cs.event_study(s, s.index[60])
    assert far["diff"] == 0.0 and far["rank_share"] < 0.7


def test_event_study_rejects_dates_near_the_edge():
    s = _weekly(100)
    with pytest.raises(ValueError):
        cs.event_study(s, s.index[5])


def test_monthly_event_window():
    idx = pd.date_range("2021-01-01", periods=24, freq="MS")
    s = pd.Series(np.where(idx < "2022-03-01", 1.0, 3.0), index=idx)
    r = cs.monthly_event_window(s, "2022-03-16", k=6)
    assert r["before"] == 1.0 and r["after"] == 3.0 and r["n_before"] == 6 and r["n_after"] == 6


def test_rate_context():
    days = pd.date_range("2022-01-01", "2023-06-01", freq="D")
    fred = pd.concat([pd.DataFrame({"series_id": "DFF", "date": days, "value": np.linspace(0.1, 5.0, len(days))}),
                      pd.DataFrame({"series_id": "NASDAQCOM", "date": days, "value": np.linspace(100, 80, len(days))})])
    c = cs.rate_context(fred, "2022-03-16")
    assert c["fed_funds_day_before"] < c["fed_funds_26w_later"] and c["nasdaq_change_pct"] < 0


# ----------------------------------------------------------------------------- H3
def _world(n=600, seed=0, planted=True):
    """Tech companies with 2019 and 2021 quarterly revenue/operating income; layoffs depend on overbuild and size."""
    rng = np.random.default_rng(seed)
    fin_rows, rev_rows, uni, matches, ev = [], [], [], [], []
    for c in range(1, n + 1):
        size = rng.normal()
        boom = rng.normal(0.2, 0.2)
        cost_g = boom + rng.normal(0, 0.2)
        r19, cost19 = 100.0, 90.0
        r21, cost21 = r19 * np.exp(boom), cost19 * np.exp(cost_g)
        for y, r, cst in ((2019, r19, cost19), (2021, r21, cost21)):
            for q in (1, 2, 3, 4):
                per = f"CY{y}Q{q}" if q < 4 else f"CY{y}Q4"
                rev_rows.append({"cik": c, "period": per, "revenue": r / 4, "tag": "Revenues",
                                 "kind": "quarter" if q < 4 else "derived_q4"})
                fin_rows.append({"cik": c, "period": per, "concept": "operating_income", "value": (r - cst) / 4,
                                 "kind": "quarter" if q < 4 else "derived_q4", "tag": "x"})
        fin_rows.append({"cik": c, "period": "CY2019Q4I", "concept": "assets", "value": float(np.exp(5 + size)),
                         "kind": "instant", "tag": "Assets"})
        uni.append({"cik": c, "name": f"Co{c}", "sic": "7372" if c % 2 else "3674", "is_tech": True})
        matches.append({"layoffs_company": f"Co{c}", "cik": c})
        z = -2.0 + (1.5 * (cost_g - boom) / 0.28 if planted else 0.0) * 0.6 + 0.5 * size
        if rng.random() < 1 / (1 + np.exp(-z)):
            ev.append({"company": f"Co{c}", "date": pd.Timestamp("2023-02-10")})
    return (pd.DataFrame(fin_rows), pd.DataFrame(rev_rows), pd.DataFrame(uni), pd.DataFrame(matches),
            pd.DataFrame(ev))


def test_company_boom_table_variables_and_filters():
    fin, rev, uni, matches, ev = _world(n=3)
    # company 1 loses a quarter of 2021 -> dropped; company 2 laid off in 2021 -> kept in table but flagged
    rev = rev[~((rev["cik"] == 1) & (rev["period"] == "CY2021Q2"))]
    ev = pd.concat([ev, pd.DataFrame({"company": ["Co2", "Co3"], "date": pd.to_datetime(["2021-06-01", "2022-09-01"])})])
    d = cs.company_boom_table(fin, rev, uni, matches, ev).set_index("cik")
    assert 1 not in d.index and {2, 3} <= set(d.index)
    row = d.loc[3]
    assert row["boom_growth"] == pytest.approx(np.log(row["revenue_1"] / row["revenue_0"]))
    assert row["overbuild"] == pytest.approx(row["cost_growth"] - row["boom_growth"])
    assert d.loc[2, "layoff_before_outcome"] and not d.loc[3, "layoff_before_outcome"]
    assert d.loc[3, "y_layoff"] == 1


def test_overbuild_signal_is_found_and_null_is_not():
    fin, rev, uni, matches, ev = _world(n=700, planted=True)
    d = cs.company_boom_table(fin, rev, uni, matches, ev)
    d = d[~d["layoff_before_outcome"]]
    lg = cs.controlled_logit(d, ["overbuild"], n_boot=150).set_index("term")
    assert lg.loc["overbuild", "ci_lo"] > 1.0 and lg.loc["log_assets_start", "odds_ratio"] > 1.0
    auc = cs.univariate_auc(d, ["overbuild"], n_boot=150).iloc[0]
    assert auc["auc"] > 0.55 and auc["ci_lo"] <= auc["auc"] <= auc["ci_hi"]
    fin, rev, uni, matches, ev = _world(n=700, seed=5, planted=False)
    d0 = cs.company_boom_table(fin, rev, uni, matches, ev)
    lg0 = cs.controlled_logit(d0[~d0["layoff_before_outcome"]], ["overbuild"], n_boot=150).set_index("term")
    assert lg0.loc["overbuild", "ci_lo"] < 1.0 < lg0.loc["overbuild", "ci_hi"]


def test_quartile_table_covers_all_companies():
    fin, rev, uni, matches, ev = _world(n=200)
    d = cs.company_boom_table(fin, rev, uni, matches, ev)
    t = cs.quartile_table(d, "overbuild")
    assert t["companies"].sum() == len(d) and len(t) == 4


FLAT = (b"series_id        \tyear\tperiod\tvalue\tfootnote_codes\n"
        b"JTS510000000000000LDR    \t2022\tM03\t   1.4\t\n"
        b"JTS510000000000000LDR    \t2022\tM13\t   1.3\t\n"
        b"JTS510000000000000LDR    \t2010\tM01\t   2.0\t\n"
        b"JTS999999999999999LDR    \t2022\tM03\t   9.9\t\n")


def test_parse_jolts_flat_filters_series_period_and_year():
    df = macro.parse_jolts_flat(FLAT, macro.JOLTS_SERIES, start_year=2015)
    assert len(df) == 1 and df["series_id"].iloc[0] == "JTS510000000000000LDR"
    assert df["date"].iloc[0] == pd.Timestamp("2022-03-01") and df["value"].iloc[0] == 1.4


def test_collect_jolts_falls_back_to_flat_file_when_api_fails(monkeypatch):
    def fake(url, **kw):
        if "json_body" in kw:
            raise requests.ConnectionError("503")
        return FLAT
    monkeypatch.setattr(macro, "fetch", fake)
    df = macro.collect_jolts(2015, 2026)
    assert len(df) == 1 and df["series_id"].iloc[0].endswith("LDR")
