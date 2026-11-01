"""Explanations: four parts, numbers computed from the data, wording that follows the numbers."""
import numpy as np
import pandas as pd
import pytest

from analysis import causes as cs
from analysis import company_models as cm
from analysis import story_text as tx
from analysis import viz
from analysis.viz_theme import explanation_markdown, sl_num, sl_pct
from test_company_models import synthetic_panel
from test_viz import make_macro, make_quartiles, make_tests, make_weekly


def check(parts):
    assert set(parts) == {"kaj", "zakaj", "pomen", "omejitve"}
    for k, v in parts.items():
        assert isinstance(v, str) and len(v) > 40, k
        assert "nan" not in v.lower().split() and "None" not in v and "nan %" not in v, k
    explanation_markdown(parts)                                          # renders without raising


def test_change_word_follows_the_numbers():
    assert tx._change(21.3, 21.6) == "skoraj nespremenjeno"
    assert tx._change(1.0, 15.4) == "naraslo" and tx._change(10.0, 4.0) == "padlo" and tx._change(0.0, 3.0) == "naraslo"


def test_timeline_text_uses_the_computed_event_study_numbers():
    w, m = make_weekly(), make_macro()
    e = tx.explain_timeline(w, m)
    check(e)
    st = cs.event_study(w, cs.FED_HIKE)
    assert sl_num(st["before_mean"]) in e["pomen"] and sl_num(st["after_mean"]) in e["pomen"]
    assert "ChatGPT" in e["kaj"]


def test_calendar_text_names_the_busiest_year_and_week():
    w = make_weekly()
    e = tx.explain_layoff_calendar(w)
    check(e)
    iso = w.index.isocalendar()
    top = int(w.groupby(iso["year"].to_numpy()).sum().idxmax())
    assert str(top) in e["pomen"] and sl_num(w.max(), 0) in e["pomen"]


def test_event_window_wording_flips_with_the_data():
    flat = make_weekly()                                                   # step in May 2022: nothing at ChatGPT
    e = tx.explain_event_windows(flat)
    check(e)
    assert "skoraj nespremenjeno" in e["pomen"] and "po prvem zvišanju" in e["pomen"]
    jump = flat.copy()
    jump[jump.index >= "2022-11-28"] += 40                                 # a real jump at ChatGPT
    assert "naraslo" in tx.explain_event_windows(jump)["pomen"]


def test_leadlag_text_mentions_p_values_and_handles_no_significance():
    e = tx.explain_leadlag(make_tests())
    check(e)
    assert "p = " in e["pomen"]
    t = make_tests()
    for r in t.values():
        r["p_value"] = 0.5
    e2 = tx.explain_leadlag(t)
    assert "jasne povezave ni" in e2["pomen"] and "naključnih premikov" not in e2["pomen"]


def test_overbuild_text_has_the_quartile_shares():
    q = make_quartiles()
    e = tx.explain_overbuild(q)
    check(e)
    assert sl_pct(4 / 85) in e["pomen"] and sl_pct(19 / 84) in e["pomen"] and "narašča iz skupine v skupino" in e["pomen"]


def test_size_text_uses_first_and_last_decile():
    p = synthetic_panel(150)
    e = tx.explain_size_deciles(p)
    check(e)
    d = p.dropna(subset=["log_assets"])
    g = pd.qcut(d["log_assets"], 10, labels=False)
    assert sl_pct(d[g == 9]["y_next2q"].mean(), 1) in e["pomen"]


def test_model_texts_report_the_test_set_sizes_and_numbers():
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    e = tx.explain_model_comparison(sc)
    check(e)
    te = sc["test"]
    assert str(int(te["y_next2q"].sum())) in e["omejitve"]
    assert sl_num(viz.model_comparison_table(sc).iloc[2]["pr_auc"], 2) in e["pomen"]
    check(tx.explain_size_group_lift(sc["stratified"]))


def test_build_explanations_has_the_same_names_as_the_figures():
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    story = {"weekly": make_weekly(), "macro": make_macro(), "tests": make_tests(), "flags": None,
             "quartiles": make_quartiles(), "panel": synthetic_panel(150), "size_control": sc}
    ex = tx.build_explanations(story)
    assert set(ex) == set(viz.build_figures(story))
    for parts in ex.values():
        check(parts)


def test_timeline_does_not_claim_a_market_drop_that_is_not_in_the_data():
    w = make_weekly()
    m = make_macro()                                                       # NASDAQ only rises
    e = tx.explain_timeline(w, m)
    assert "ni bistveno padel" in e["pomen"] and "izgubil" not in e["pomen"] and "skupnem valu" in e["pomen"]
    m2 = m.copy()
    m2.loc["2022-01-01":"2022-12-01", "nasdaq"] = m2["nasdaq"].iloc[0] * 0.5       # a real fall inside the window
    e2 = tx.explain_timeline(w, m2)
    assert "izgubil" in e2["pomen"] and "v istem obdobju" in e2["pomen"]


def test_calendar_concentration_follows_the_data():
    flat = pd.Series(5.0, index=pd.date_range("2021-01-04", periods=104, freq="7D"))
    assert "enakomerno" in tx.explain_layoff_calendar(flat)["pomen"]
    spiky = flat.copy()
    spiky.iloc[[10, 11]] = 500.0                                           # two huge weeks hold most of the total
    assert "kratkih valovih" in tx.explain_layoff_calendar(spiky)["pomen"]


def test_leadlag_closing_sentence_follows_the_p_values():
    t = make_tests()
    for r in t.values():
        r["p_value"] = 0.5
    assert "ne vidimo jasnega ujemanja" in tx.explain_leadlag(t)["pomen"]
    keys = list(t)
    t[keys[0]]["p_value"] = 0.02
    p = tx.explain_leadlag(t)["pomen"]
    assert "sledi obrestnim meram" in p and "s spremembo obrestne mere" in p


def test_overbuild_verdict_follows_the_pattern():
    q = make_quartiles()
    q["overbuild"] = q["overbuild"].assign(rate=[0.12, 0.14, 0.20, 0.09])      # not monotone
    assert "še ne pomeni, da so podjetja zaposlovala preveč" in tx.explain_overbuild(q)["pomen"]
    q["overbuild"] = q["overbuild"].assign(rate=[0.05, 0.10, 0.15, 0.20])      # monotone too
    assert "v skladu z razlago o prezaposlovanju" in tx.explain_overbuild(q)["pomen"]
    q["boom_growth"] = q["boom_growth"].assign(rate=[0.2, 0.1, 0.15, 0.05])
    q["overbuild"] = q["overbuild"].assign(rate=[0.2, 0.1, 0.15, 0.05])
    assert "ne gresta jasno z odpuščanji" in tx.explain_overbuild(q)["pomen"]


def test_model_verdict_follows_the_numbers():
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    t = viz.model_comparison_table(sc)
    e = tx.explain_model_comparison(sc)
    lg, lg0 = t.iloc[2]["pr_auc"], t.iloc[4]["pr_auc"]
    assert ("pride iz velikosti" in e["pomen"]) == (lg0 < 0.5 * lg)
    assert "od 2023 naprej" in e["omejitve"] or "naprej" in e["omejitve"]


def test_summary_follows_the_data_and_always_lists_what_is_open():
    from test_viz_stock import make_stock
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    story = {"weekly": make_weekly(), "macro": make_macro(), "tests": make_tests(), "flags": None, "quartiles": make_quartiles(),
             "panel": synthetic_panel(150), "size_control": sc}
    s = tx.build_summary(story)
    assert len(s["zakljucki"]) == 4 and len(s["odprto"]) == 4
    assert all(len(x) > 40 and "nan" not in x.lower().split() for x in s["zakljucki"] + s["odprto"])
    assert "spomladi 2022" in s["zakljucki"][0] and "skoraj nespremenjeno" in s["zakljucki"][0]        # ChatGPT: flat in the synthetic data
    story["stock"] = make_stock(0.03)
    s2 = tx.build_summary(story)
    assert len(s2["zakljucki"]) == 5 and s2["zakljucki"][-1].startswith("**Borza:**") and "zvišala" in s2["zakljucki"][-1]
    t = make_tests()
    for r in t.values():
        r["p_value"] = 0.6
    story["tests"] = t
    assert "ne moremo jasno povezati" in tx.build_summary(story)["zakljucki"][1]


def test_company_scatter_text_follows_the_quadrant_shares():
    from test_viz import make_boom_table
    t = make_boom_table(200)
    e = tx.explain_company_scatter(t)
    check(e)
    big = t["log_assets_start"] >= t["log_assets_start"].median()
    fast = t["boom_growth"] >= t["boom_growth"].median()
    assert sl_pct(t.loc[big & fast, "y_layoff"].mean()) in e["pomen"] and "pogosteje" in e["pomen"]
    flat = t.assign(y_layoff=np.tile([0, 1], 100))
    assert "približno enako pogosto" in tx.explain_company_scatter(flat)["pomen"]


def test_export_texts_contains_every_figure_and_the_summary():
    from test_viz import make_boom_table
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    story = {"weekly": make_weekly(), "macro": make_macro(), "tests": make_tests(), "flags": None, "quartiles": make_quartiles(),
             "panel": synthetic_panel(150), "size_control": sc, "boom_table": make_boom_table()}
    md = tx.export_texts(story)
    names = tx.build_explanations(story)
    assert all(f"## {n}" in md for n in names) and "## 3_podjetja" in md
    assert md.count("**Kaj vidimo?**") == len(names) and "## povzetek" in md and "Česa ne vemo" in md
