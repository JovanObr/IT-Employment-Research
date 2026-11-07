"""Notebook 09, Stream A part: figures, Slovenian explanations and verdict rows on synthetic inputs (no files)."""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis import compare_viz as cv
from analysis import comparisons as cp
from test_comparisons import _panel

NB = Path(__file__).resolve().parent.parent / "notebooks" / "09_primerjava_SL.ipynb"


def challenger(scale=1.0):
    t = pd.DataFrame(cp.CHALLENGER)[["period", "challenger"]]
    t["tracker_us"] = t["challenger"] * scale
    t.loc[t["period"] == "2022Q1", "tracker_us"] = 7762
    t["share_with_number"] = 0.6
    t["ratio_us_to_challenger"] = t["tracker_us"] / t["challenger"]
    t["tracker_us_announcements"], t["tracker_all_countries"] = 100, t["tracker_us"] * 1.5
    return t


def stock(diff=-1.4, lo=-3.8, hi=1.3):
    by_big = pd.DataFrame({"share_big": ["do 10 %", "nad 10 %", "ni podatka"], "n": [226, 152, 233], "mean_pct": [-0.5, -0.5 + diff, 0.2],
                           "median_pct": [-0.3, -1.4, 0.1], "ci_lo_pct": [-1.7, -4.0, -0.5], "ci_hi_pct": [0.7, 0.3, 1.0]})
    by_group = pd.DataFrame({"share_group": list(cv.SHARE_ORDER), "n": [100, 120, 100, 50, 230], "mean_pct": [-0.4, -0.6, -2.0, -1.8, 0.2],
                             "median_pct": [0.0] * 5, "ci_lo_pct": [-1.9, -2.6, -4.4, -6.6, -0.5], "ci_hi_pct": [0.8, 1.4, 0.3, 2.9, 1.0]})
    return {"by_big": by_big, "by_group": by_group, "events": pd.DataFrame({"x": range(611)}), "n_known": 378,
            "diff_big_minus_small": {"diff_pct": diff, "ci_lo_pct": lo, "ci_hi_pct": hi}}


def headcount(cut_rho=0.02, cut_lo=-0.15, cut_hi=0.19, or_lo=0.9):
    q = pd.DataFrame({"quartile": ["Q1 lowest", "Q2", "Q3", "Q4 highest"], "companies": 60, "laid_off": [5, 8, 12, 17],
                      "rate": [0.08, 0.13, 0.2, 0.28]})
    c = pd.DataFrame({"quartile": ["Q1 najmanj", "Q2", "Q3", "Q4 največ"], "companies": 47, "median_hire_growth_pct": [-17, 9, 30, 77],
                      "median_change_22_23_pct": [-4.0, -0.8, 1.4, -3.3], "share_cut_5pct": [0.46, 0.29, 0.30, 0.42]})
    lg = pd.DataFrame({"term": ["hire_growth", "log_assets_start"], "odds_ratio": [1.38, 2.6], "ci_lo": [or_lo, 1.8], "ci_hi": [2.35, 4.2]})
    return {"n": 240, "n_layoff": 42, "quartiles": q, "cut_quartiles": c, "logit": lg,
            "cut": {"n": 190, "spearman": cut_rho, "ci_lo": cut_lo, "ci_hi": cut_hi},
            "cut_vs_hire": {"cutters": 100, "median_cut_pct": -8.6, "median_prior_growth_pct": 13.4, "share_still_above_2019": 0.54}}


def data():
    return {"challenger": challenger(), "stock": stock(), "within": cp.within_firm_model(_panel(), cv.WITHIN_SPEC), "headcount": headcount()}


def _check_parts(parts):
    assert set(parts) == {"kaj", "zakaj", "pomen", "omejitve"}
    for k, v in parts.items():
        assert v.strip() and "nan" not in v.lower().split() and "None" not in v, k


def test_build_comparisons_a_returns_figure_explanation_and_verdict_for_each():
    out = cv.build_comparisons_a(data())
    assert set(out) == {"9a_challenger", "9a_borza_delez", "9a_znotraj", "9a_zaposlovanje"}
    for name, (fig, parts, verdict) in out.items():
        assert len(fig.data) >= 1
        _check_parts(parts)
        assert set(verdict) == set(cv.VERDICT_KEYS) and verdict["ocena"] in cv.VERDICTS


def test_optional_parts_are_left_out_when_their_data_is_missing():
    d = data()
    d.pop("stock"); d.pop("headcount")
    assert set(cv.build_comparisons_a(d)) == {"9a_challenger", "9a_znotraj"}


def test_challenger_periods_are_categories_in_time_order():
    fig = cv.fig_challenger(challenger())
    right = [t for t in fig.data if t.xaxis == "x2"][0]
    assert list(right.x) == ["1. četrtletje 2022", "november 2022", "1. četrtletje 2023"]
    assert fig.layout.xaxis2.type == "category"


def test_challenger_verdict_and_text_follow_the_numbers():
    assert cv.verdict_challenger(challenger(1.05))["ocena"] == "se ujema"
    assert cv.verdict_challenger(challenger(3.0))["ocena"] == "delno"          # same peak year, levels far apart
    assert "blizu" in cv.explain_challenger(challenger(1.05))["pomen"]
    assert "V nobenem letu" in cv.explain_challenger(challenger(3.0))["pomen"]


def test_stock_share_wording_flips_with_significance_and_sign():
    weak = cv.explain_stock_share(stock())["pomen"]
    strong = cv.explain_stock_share(stock(-2.0, -3.5, -0.5))["pomen"]
    assert "lahko nastane tudi po naključju" in weak and "verjetno resnična" in strong
    assert cv.verdict_stock_share(stock())["ocena"] == "delno"
    assert cv.verdict_stock_share(stock(-2.0, -3.5, -0.5))["ocena"] == "se ujema"
    assert cv.verdict_stock_share(stock(1.0, -0.5, 2.5))["ocena"] == "se razlikuje"


def test_within_verdict_follows_the_revenue_effect():
    w = cp.within_firm_model(_panel(), cv.WITHIN_SPEC)                    # synthetic: a revenue fall raises the chance
    assert cv.verdict_within(w)["ocena"] == "se ujema" and "napove odpuščanje, kot v študiji" in cv.explain_within(w)["pomen"]
    flat = _panel(); flat["y_next2q"] = np.random.default_rng(1).random(len(flat)) < 0.05
    w0 = cp.within_firm_model(flat.assign(y_next2q=flat["y_next2q"].astype(int)), cv.WITHIN_SPEC)
    if w0[(w0["feature"] == "rev_decline") & w0["model"].str.startswith("znotraj")]["ci_lo"].iloc[0] <= 0:
        assert cv.verdict_within(w0)["ocena"] == "se razlikuje" and "ne napove" in cv.explain_within(w0)["pomen"]


def test_overhiring_wording_and_verdict_follow_both_outcomes():
    base = cv.explain_overhiring(headcount())["pomen"]
    assert "ni dovolj zanesljiva" in base and "ni povezano" in base
    both = headcount(-0.4, -0.55, -0.2, or_lo=1.2)
    assert "večjim kasnejšim krčenjem" in cv.explain_overhiring(both)["pomen"]
    assert cv.verdict_overhiring(both)["ocena"] == "se ujema"
    assert cv.verdict_overhiring(headcount())["ocena"] == "delno"               # cuts small: most still above 2019


def test_inputs_are_not_modified():
    d = data()
    before = d["challenger"].copy()
    cv.fig_challenger(d["challenger"]); cv.explain_challenger(d["challenger"])
    pd.testing.assert_frame_equal(before, d["challenger"])


def test_verdict_markdown_refuses_incomplete_rows():
    good = {"tema": "a", "studija": "b", "njihov_rezultat": "c", "nas_rezultat": "d", "ocena": "delno"}
    assert "**delno**" in cv.verdict_markdown([good])
    with pytest.raises(ValueError):
        cv.verdict_markdown([{**good, "ocena": "mogoče"}])
    with pytest.raises(ValueError):
        cv.verdict_markdown([{**good, "nas_rezultat": ""}])


def test_earlier_verdicts_are_computed():
    idx = pd.date_range("2021-06-07", "2023-06-26", freq="7D")
    weekly = pd.Series(np.where(idx < "2022-04-01", 1.0, 20.0), index=idx)
    rows = cv.verdicts_earlier({"mean_pct": -0.58, "ci_lo_pct": -1.3, "ci_hi_pct": 0.2}, weekly,
                               {"jolts": {"first Fed hike 2022-03-16": {"information": {"before": 1.17, "after": 1.15}}}})
    assert [r["tema"] for r in rows] == ["Odziv borze na napoved odpuščanj", "Kdaj se je začel val", "Uradna stopnja odpuščanj"]
    assert all(r["ocena"] == "se ujema" for r in rows)


def test_notebook_09_structure():
    cells = json.loads(NB.read_text(encoding="utf-8"))["cells"]
    code = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
    md = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "markdown")
    for c in cells:
        if c["cell_type"] == "code":
            ast.parse("".join(c["source"]))
    assert "cv.prepare_compare_data()" in code and "build_comparisons_b()" in code and "sources_markdown(name)" in code
    assert "verdict_markdown(verdicts)" in code and "notebook_connected" in code
    for h in ("## Povzetek", "## 1. Koliko ljudi", "## 2. Ali borza", "## 3. Ali padec", "## 4. Ali so odpuščala", "## 5.", "## Viri"):
        assert h in md, h
