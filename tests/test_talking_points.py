"""Spoken versions: every chapter present, about 30 seconds long, numbers from the data, wording that follows the numbers."""
import numpy as np
import pandas as pd

from analysis import company_models as cm
from analysis import talking_points as tp
from analysis.viz_theme import sl_num, sl_pct
from test_company_models import synthetic_panel
from test_story_text import _geo, _hn_flags
from test_viz import make_macro, make_quartiles, make_tests, make_weekly
from test_viz_stock import make_stock


def make_story(stock=True, hn=True, geo=True):
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    s = {"weekly": make_weekly(), "macro": make_macro(), "tests": make_tests(), "flags": None, "quartiles": make_quartiles(),
         "panel": synthetic_panel(150), "size_control": sc}
    if stock:
        s["stock"] = make_stock(0.03)
    if hn:
        s["hn"] = {"flags": _hn_flags()}
    if geo:
        s["geo"] = _geo()
    return s


def real_like(f):
    """Facts shaped like the real data, where size carries most of the model (the synthetic panel has no planted size effect)."""
    return dict(f, logit_nosize=0.3 * f["logit"])


def titles(points):
    return [t for t, _ in points]


def test_all_chapters_present_and_each_script_is_about_half_a_minute():
    pts = tp.render(real_like(tp.collect_facts(make_story())))
    assert titles(pts) == ["Uvod", "1. Kdaj", "2. Zakaj", "3. Katera podjetja", "4. Kaj iščejo delodajalci", "5. Kje", "6. Borza", "Zaključek"]
    for t, text in pts:
        n = len(text.split())
        assert 40 <= n <= 115, (t, n)                       # about 30 seconds at a relaxed speaking pace
        assert "nan" not in text.lower().split() and "None" not in text


def test_numbers_in_the_scripts_come_from_the_data():
    story = make_story()
    f = tp.collect_facts(story)
    pts = dict(tp.render(f))
    assert sl_num(f["hike_before"]) in pts["1. Kdaj"] and sl_num(f["hike_after"]) in pts["1. Kdaj"]
    assert sl_pct(f["remote_peak"]) in pts["4. Kaj iščejo delodajalci"] and f["remote_peak_month"] in pts["4. Kaj iščejo delodajalci"]
    assert str(f["geo_n"]) in pts["5. Kje"] and str(f["geo_hidden"]) in pts["5. Kje"]
    assert sl_num(abs(f["stock_mean"]), 1) in pts["6. Borza"]


def test_wording_follows_the_numbers():
    f = real_like(tp.collect_facts(make_story()))
    base = dict(tp.render(f))
    assert "ne ob ChatGPT" in base["1. Kdaj"]                                              # flat at ChatGPT in the synthetic data
    jump = dict(f, gpt_after=f["gpt_before"] * 3)
    assert "ne ob ChatGPT" not in dict(tp.render(jump))["1. Kdaj"] and "povečalo" in dict(tp.render(jump))["1. Kdaj"]
    assert "ni jasno več kot naključje" in dict(tp.render(dict(f, stock_lo=-1.0, stock_hi=0.5)))["6. Borza"]
    assert "statistično opazna" in dict(tp.render(dict(f, stock_lo=-1.5, stock_hi=-0.5)))["6. Borza"]
    assert "ni zanesljiva" in dict(tp.render(dict(f, gap=-1.0, gap_lo=-2.0, gap_hi=1.0)))["6. Borza"]
    assert "je zanesljiva" in dict(tp.render(dict(f, gap=-2.0, gap_lo=-3.0, gap_hi=-1.0)))["6. Borza"]
    assert "Največ pove velikost" in base["3. Katera podjetja"]
    assert "še vedno dosežejo" in dict(tp.render(dict(f, logit_nosize=f["logit"] * 0.9)))["3. Katera podjetja"] and "Velikost je pomembna" in dict(tp.render(dict(f, logit_nosize=f["logit"] * 0.9)))["3. Katera podjetja"]
    assert "ne moremo jasno povezati" in dict(tp.render(dict(f, ev_sig=False)))["2. Zakaj"]


def test_chapters_without_data_are_left_out_not_invented():
    pts = tp.render(tp.collect_facts(make_story(stock=False, hn=False, geo=False)))
    assert titles(pts) == ["Uvod", "1. Kdaj", "2. Zakaj", "3. Katera podjetja", "Zaključek"]
    assert "borza pa se ni jasno odzvala" in pts[-1][1]


def test_markdown_lists_word_counts():
    md = tp.to_markdown(tp.render(tp.collect_facts(make_story())))
    assert md.count("## ") == 8 and "besed)" in md
