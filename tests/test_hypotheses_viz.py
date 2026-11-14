"""Notebook 10: verdict rule, figures and Slovenian explanations for the four registered hypotheses (synthetic results only)."""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import hypotheses_viz as hv

NB = Path(__file__).resolve().parent.parent / "notebooks" / "10_hipoteze_SL.ipynb"


def res_c(p=0.35, sign=True):
    return {"primary": {"n_announced": 102, "n_not": 321, "median_announced": 0.044, "median_not": 0.074, "diff_median": -0.03,
                        "ci_lo": -0.087, "ci_hi": 0.029, "p": p, "predicted_sign": sign, "mde_log": 0.12},
            "secondary_ols": {"n": 414, "coef_announced": -0.08, "ci_lo": -0.17, "ci_hi": 0.01, "p": 0.075},
            "secondary_2022_2023": {"diff_median": -0.07, "ci_lo": -0.097, "ci_hi": -0.02, "p": 2e-5}, "placebo": {"false_positive_rate": 0.045}}


def res_d(p=0.126, sign=False):
    return {"primary": {"n_repeat": 383, "n_first": 228, "mean_repeat_pct": -0.14, "mean_first_pct": -1.31, "diff_pct": 1.16, "p": p,
                        "predicted_sign": sign, "mde_pct": 2.1},
            "secondary": {"mannwhitney_p_raw": 0.009}, "placebo": {"false_positive_rate": 0.04}}


def res_a(p=0.01, sign=True):
    vals = {c: 0.3 + 0.1 * i / 26 for i, c in enumerate(hv.EU_SL)}
    vals["SI"] = 1.2
    return {"primary": {"x_si": 1.2, "mean_others": 0.35, "sd_others": 0.3, "t": 2.8, "p": p, "predicted_sign": sign, "rank": 1, "n_countries": 27,
                        "values": vals}, "placebo": {"share_p_below_005": 0.04}}


def res_b(p=0.02, sign=True, trend=False):
    q = [f"{y}Q{k}" for y in range(2019, 2025) for k in range(1, 5)]
    sf = [100.0 - (5 if i >= 13 else 0) for i in range(len(q))]
    return {"primary": {"b": -0.06, "se": 0.02, "ci_lo": -0.1, "ci_hi": -0.02, "p": p, "predicted_sign": sign, "trend_added": trend,
                        "pretrend_p": 0.3, "n_pre": 13, "n_post": 11,
                        "series": [{"quarter": a, "sf": s, "austin": 50.0} for a, s in zip(q, sf)]},
            "placebo": {"n_pairs": 435, "rank_of_sf_austin": 12, "share_abs_b_at_least": 0.03}}


def all_res(**kw):
    return {"A": res_a(), "B": res_b(), "C": res_c(), "D": res_d(), **kw}


def test_no_verdict_until_all_four_exist():
    v = hv.verdicts({"A": None, "B": None, "C": res_c(), "D": res_d()}).set_index("hipoteza")
    assert v.loc["A", "sklep"] == "čaka na rezultat" and v.loc["C", "sklep"] == "ni potrjena"    # p 0.35 >= 0.05: Holm cannot help
    v2 = hv.verdicts({"A": None, "B": None, "C": res_c(p=0.01), "D": res_d()}).set_index("hipoteza")
    assert v2.loc["C", "sklep"] == "čaka na vse štiri teste"
    assert v["p_holm"].isna().all()


def test_verdict_needs_holm_and_the_predicted_sign():
    v = hv.verdicts(all_res()).set_index("hipoteza")
    # p = 0.01, 0.02, 0.35, 0.126 -> Holm 0.04, 0.06, 0.35, 0.252
    assert np.isclose(v.loc["A", "p_holm"], 0.04) and v.loc["A", "sklep"] == "potrjena"
    assert np.isclose(v.loc["B", "p_holm"], 0.06) and v.loc["B", "sklep"] == "ni potrjena"
    assert v.loc["C", "sklep"] == "ni potrjena" and v.loc["D", "sklep"] == "ni potrjena"
    wrong_sign = hv.verdicts(all_res(A=res_a(p=0.001, sign=False))).set_index("hipoteza")
    assert wrong_sign.loc["A", "sklep"] == "ni potrjena" and wrong_sign.loc["A", "smer"] == "nasprotna od napovedi"


def test_verdict_table_lists_all_four():
    md = hv.verdict_markdown(hv.verdicts(all_res()))
    assert all(f"**{k}**" in md for k in "ABCD") and "**potrjena**" in md


def test_explanations_are_complete_and_follow_the_numbers():
    v = hv.verdicts(all_res())
    for parts in (hv.explain_a(res_a(), v), hv.explain_b(res_b(), v), hv.explain_c(res_c(), v), hv.explain_d(res_d(), v)):
        assert set(parts) == {"kaj", "zakaj", "pomen", "omejitve"}
        assert all(t.strip() and "nan" not in t.lower().split() and "None" not in t for t in parts.values())
    assert "nasprotni smeri od napovedi" in hv.explain_d(res_d(), v)["pomen"]
    assert "napovedani smeri" in hv.explain_d(res_d(p=0.01, sign=True), v)["pomen"]
    assert "**potrjena**" in hv.explain_a(res_a(), v)["pomen"]
    assert "odmik od tega prejšnjega trenda" in hv.explain_b(res_b(trend=True), v)["pomen"]


def test_partial_results_say_c_and_d_cannot_pass_anyway():
    v = hv.verdicts({"A": None, "B": None, "C": res_c(), "D": res_d()})
    assert "ne glede na ostale teste" in hv.explain_c(res_c(), v)["pomen"]
    v2 = hv.verdicts({"A": None, "B": None, "C": res_c(p=0.01), "D": res_d()})
    assert "Končni sklep bo znan" in hv.explain_c(res_c(p=0.01), v2)["pomen"]


def test_figures_draw_from_the_results():
    a = hv.fig_a(res_a()["primary"])
    assert len(a.data[0].y) == 27 and "Slovenija" in a.data[0].y
    b = hv.fig_b(res_b()["primary"])
    assert len(b.data) == 3 and b.layout.xaxis2.type == "category"
    c = pd.DataFrame({"outcome": np.r_[np.full(20, -0.1), np.full(30, 0.05)], "announced": np.r_[np.ones(20, int), np.zeros(30, int)]})
    assert len(hv.fig_c(c, c).data) == 4 and len(hv.fig_c(c).data) == 2


def test_d_groups_and_figure():
    n = 200
    days = pd.bdate_range("2022-01-03", periods=n)
    cars = pd.DataFrame({"car_ann_0_1": np.r_[np.full(100, -0.02), np.zeros(100)] + np.random.default_rng(0).normal(0, 0.01, n),
                         "repeat": np.r_[np.zeros(100, int), np.ones(100, int)], "event_day": days})
    g = hv.d_groups(cars, n_boot=200)
    assert list(g["n"]) == [100, 100] and g["mean_pct"].iloc[0] < g["mean_pct"].iloc[1]
    assert (g["lo_pct"] <= g["mean_pct"]).all() and len(hv.fig_d(g).data) == 1


def test_build_hypotheses_skips_what_is_missing():
    c = pd.DataFrame({"outcome": [0.1, -0.1, 0.0, 0.2], "announced": [1, 1, 0, 0]})
    out = hv.build_hypotheses({"A": None, "B": None, "C": res_c(), "D": res_d()}, {"c21": c})
    assert set(out) == {"10c_zaposleni"}
    full = hv.build_hypotheses(all_res(), {"c21": c, "d": pd.DataFrame({"group": ["a", "b"], "n": [1, 1], "mean_pct": [0, 0], "lo_pct": [0, 0], "hi_pct": [0, 0]})})
    assert set(full) == {"10a_slovenija", "10b_sf_austin", "10c_zaposleni", "10d_borza"}


def test_notebook_10_structure():
    cells = json.loads(NB.read_text(encoding="utf-8"))["cells"]
    code = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
    md = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "markdown")
    for c in cells:
        if c["cell_type"] == "code":
            ast.parse("".join(c["source"]))
    assert "hv.load_results()" in code and "verdict_markdown" in code and "sources_markdown(name)" in code
    for h in ("## Povzetek", "## A.", "## B.", "## C.", "## D.", "## Kaj smo izvedeli mimogrede", "## Viri"):
        assert h in md, h
