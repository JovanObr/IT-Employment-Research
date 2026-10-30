"""Chapter 1-3 figures: smoke and content tests on synthetic data (no files, no network)."""
import numpy as np
import pandas as pd
import pytest

from analysis import causes as cs
from analysis import company_models as cm
from analysis import viz
from test_company_models import synthetic_panel


def make_weekly():
    idx = pd.date_range("2020-04-06", "2026-09-21", freq="7D")
    v = np.where(idx < "2022-05-23", 1.0, 20.0) + np.random.default_rng(0).integers(0, 3, len(idx))
    return pd.Series(v, index=idx, name="events")


def make_macro():
    m = pd.date_range("2019-01-01", "2026-09-01", freq="MS")
    return pd.DataFrame({"fedfunds": np.interp(np.arange(len(m)), [0, 38, 50, len(m)], [2, 0.1, 5, 4]),
                         "nasdaq": np.linspace(7000, 22000, len(m))}, index=m)


def make_flags():
    m = pd.date_range("2019-01-01", "2026-09-01", freq="MS").strftime("%Y-%m")
    return pd.concat([pd.DataFrame({"month": m, "flag": "remote", "share": np.linspace(0.2, 0.7, len(m)), "n_posts": 500}),
                      pd.DataFrame({"month": m, "flag": "ai_ml", "share": np.linspace(0.1, 0.5, len(m)), "n_posts": 500})])


def make_tests():
    rng = np.random.default_rng(1)
    s = lambda: pd.Series(np.cumsum(rng.normal(size=80)))
    return {("fedfunds_chg12", "tracker events (3-month sum)"): cs.lead_lag_test(s(), s()),
            ("nasdaq_chg12", "JOLTS information layoff rate (%)"): cs.lead_lag_test(s(), s())}


def make_quartiles():
    q = pd.DataFrame({"quartile": ["Q1", "Q2", "Q3", "Q4"], "companies": [85, 84, 84, 84], "laid_off": [4, 8, 16, 19],
                      "rate": [4 / 85, 8 / 84, 16 / 84, 19 / 84]})
    return {"boom_growth": q, "cost_growth": q.iloc[::-1].reset_index(drop=True), "overbuild": q}


def test_timeline_scales_every_line_to_0_100_and_marks_the_two_dates():
    w, m, f = make_weekly(), make_macro(), make_flags()
    w0, m0 = w.copy(), m.copy()
    fig = viz.fig_timeline(w, m, f)
    assert len(fig.data) == 5 and len(fig.layout.shapes) == 2
    for tr in fig.data:
        assert 0 <= min(tr.y) and max(tr.y) <= 100.0000001 and max(tr.y) == pytest.approx(100)
    assert "%" in fig.data[1].customdata[0]                          # real value with unit in the hover text
    assert len(viz.fig_timeline(w, m).data) == 3                      # flags are optional
    pd.testing.assert_series_equal(w, w0); pd.testing.assert_frame_equal(m, m0)


def test_timeline_starts_at_the_requested_date():
    fig = viz.fig_timeline(make_weekly(), make_macro(), start="2022-01-01")
    assert all(pd.Timestamp(tr.x[0]) >= pd.Timestamp("2022-01-01") for tr in fig.data)


def test_calendar_has_one_row_per_year_and_gaps_stay_empty():
    fig = viz.fig_layoff_calendar(make_weekly())
    z = np.array(fig.data[0].z, dtype=float)
    assert z.shape[0] == len(fig.data[0].y) and set(fig.data[0].y) >= {"2021", "2022", "2025"}
    first_year = list(fig.data[0].y).index("2020")
    assert np.isnan(z[first_year, 0])                                  # 2020 starts in April: January weeks are empty


def test_event_windows_show_the_same_averages_as_the_event_study():
    w = make_weekly()
    fig = viz.fig_event_windows(w)
    assert len(fig.data) == 2 and len(fig.layout.shapes) == 2 + 4        # 2 event lines + before/after mean lines per panel
    st = cs.event_study(w, cs.EVENTS["fed"][0]) if hasattr(cs, "EVENTS") else cs.event_study(w, cs.FED_HIKE)
    texts = [a.text for a in fig.layout.annotations if "povprečno" in (a.text or "")]
    assert any(f"pred {viz.sl_num(st['before_mean'])}" in t for t in texts)


def test_leadlag_heatmap_has_a_row_per_pair_and_a_star_per_row():
    t = make_tests()
    fig = viz.fig_leadlag_heatmap(t)
    assert np.array(fig.data[0].z).shape == (2, 25) and len(fig.data[1].x) == 2
    assert all("p = " in y for y in fig.data[0].y)


def test_overbuild_quartiles_is_three_small_multiples_with_counts_in_hover():
    fig = viz.fig_overbuild_quartiles(make_quartiles())
    assert len(fig.data) == 3 and fig.data[0].customdata[3][1] == 19
    assert fig.data[0].text[3] == viz.sl_pct(19 / 84)


def test_size_deciles_match_the_data():
    p = synthetic_panel(150)
    fig = viz.fig_size_deciles(p)
    assert len(fig.data[0].x) == 10 and fig.data[0].customdata[:, 0].sum() == p["log_assets"].notna().sum()
    d = p.dropna(subset=["log_assets"])
    top = d[pd.qcut(d["log_assets"], 10, labels=False) == 9]["y_next2q"].mean() * 100
    assert fig.data[0].y[-1] == pytest.approx(top)


def test_model_figures_from_the_size_control_result():
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    t = viz.model_comparison_table(sc)
    assert list(t.columns) == ["label", "pr_auc", "ci_lo", "ci_hi"] and len(t) == 6 and t["ci_lo"].iloc[2] <= t["pr_auc"].iloc[2]
    fig = viz.fig_model_comparison(t)
    assert list(fig.data[0].x) == list(t["pr_auc"]) and fig.layout.shapes[0].x0 == t["pr_auc"].iloc[0]
    lift = viz.fig_size_group_lift(sc["stratified"])
    assert 1 <= len(lift.data) <= 4 and all(not np.isnan(v) for tr in lift.data for v in tr.y)


def test_every_figure_exports_to_html():
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    story = {"weekly": make_weekly(), "macro": make_macro(), "tests": make_tests(), "flags": make_flags(),
             "quartiles": make_quartiles(), "panel": synthetic_panel(150), "size_control": sc}
    figs = viz.build_figures(story)
    assert len(figs) == 8
    for name, fig in figs.items():
        assert "plotly" in fig.to_html(include_plotlyjs="cdn"), name
