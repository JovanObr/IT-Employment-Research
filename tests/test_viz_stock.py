"""Chapter 6 (stock reaction): figures and explanations on synthetic prices with a known effect."""
import numpy as np
import pandas as pd
import pytest

from analysis import company_models as cm
from analysis import event_study as es
from analysis import story_text as tx
from analysis import viz
from analysis.viz_theme import sl_num
from test_company_models import synthetic_panel
from test_event_study import make_events, make_returns
from test_viz import make_macro, make_quartiles, make_tests, make_weekly

IDX = list(range(400, 1200, 20))


def make_stock(effect, seed=0, pre_shift=0.0):
    r = make_returns(3, effect=effect, event_idx=IDX, seed=seed)
    if pre_shift:
        for i in IDX:
            r.iloc[i - 4:i - 1, 1:] += pre_shift            # a drift in days -4..-2 for all three stocks
    ev = make_events(r, IDX, ["S0", "S1", "S2"])
    cars, _ = es.run_event_study(ev, r)
    cars["year"] = cars["date"].dt.year
    sized = cars.assign(log_assets=np.random.default_rng(1).normal(size=len(cars)))
    sized = es.add_size_groups(sized)
    sized["size_group"] = sized["size_group"].astype(str)
    paths = es.ar_paths(cars[["event_id", "ticker", "date"]], r)
    return {"cars": cars, "summary": es.summarize(cars, n_boot=300), "path": es.path_summary(paths, n_boot=300, winsor=None),
            "by_size": es.group_summary(sized, "size_group", n_boot=200), "by_year": es.group_summary(cars, "year", n_boot=200),
            "diff": es.group_difference(sized, "size_group", "najmanjša tretjina", "največja tretjina", n_boot=300)}


def test_path_figure_has_band_line_and_announcement_window():
    st = make_stock(0.03)
    fig = viz.fig_car_path(st["path"])
    assert len(fig.data) == 2 and len(fig.layout.shapes) >= 2          # grey window (+ zero line)
    assert list(fig.data[1].x) == list(range(-5, 11))


def test_distribution_figure_marks_mean_and_median_and_counts_clipped_events():
    st = make_stock(0.03)
    cars = st["cars"].copy()
    cars.loc[cars.index[:3], "car_ann_0_1"] = 0.9                        # three absurd moves
    fig = viz.fig_car_distribution(cars, clip=20.0)
    assert len(fig.data) == 1 and sum(1 for s in fig.layout.shapes if s.type == "line") == 2
    assert any("3 objav je zunaj" in (a.text or "") for a in fig.layout.annotations)
    assert max(fig.data[0].x) <= 20.0


def test_group_figure_drops_tiny_groups_and_keeps_intervals():
    st = make_stock(0.03)
    by_year = pd.concat([st["by_year"], pd.DataFrame([{"year": 2099, "window": "ann_0_1", "n": 2, "mean_pct": -20.0, "ci_lo_pct": np.nan, "ci_hi_pct": np.nan}])])
    fig = viz.fig_car_groups(st["by_size"], by_year)
    assert len(fig.data) == 2 and "2099" not in list(fig.data[1].x) and len(fig.data[0].x) == 3


def test_path_text_flips_between_a_real_effect_and_none():
    real = tx.explain_car_path(make_stock(0.03)["path"], make_stock(0.03)["summary"])
    null = tx.explain_car_path(make_stock(0.0, seed=3)["path"], make_stock(0.0, seed=3)["summary"])
    assert "statistično opazna" in real["pomen"] and "zvišala" in real["pomen"]
    assert "več kot naključje" in null["pomen"]
    s = make_stock(0.0, seed=4, pre_shift=0.02)
    assert "Že v dneh pred objavo je viden premik" in tx.explain_car_path(s["path"], s["summary"])["pomen"]
    assert "ni pricurljala" in null["pomen"] or "dober znak" in null["pomen"]


def test_distribution_text_reports_the_quantiles_and_flags_outlier_driven_means():
    st = make_stock(0.0, seed=5)
    cars = st["cars"].copy()
    e = tx.explain_car_distribution(cars, st["summary"])
    q50 = float((100 * cars["car_ann_0_1"]).abs().quantile(0.5))
    assert sl_num(q50, 1) in e["pomen"] and "potegnejo posamezni skrajni primeri" not in e["pomen"]
    s2 = dict(st["summary"], mean_pct=-3.0, median_pct=-0.2)
    assert "potegnejo posamezni skrajni primeri" in tx.explain_car_distribution(cars, s2)["pomen"]


def test_group_text_handles_missing_difference_and_reports_it_when_given():
    st = make_stock(0.0, seed=6)
    no_diff = tx.explain_car_groups(st["by_size"], st["by_year"], None)
    assert "nismo posebej preizkusili" in no_diff["pomen"]
    with_diff = tx.explain_car_groups(st["by_size"], st["by_year"], st["diff"])
    assert "odstotne točke" in with_diff["pomen"] and ("statistično zanesljivo" in with_diff["pomen"] or "statistično opazno" in with_diff["pomen"])
    for e in (no_diff, with_diff):
        for k in ("kaj", "zakaj", "pomen", "omejitve"):
            assert len(e[k]) > 40 and "nan" not in e[k].lower().split()


def test_story_builders_add_chapter_6_only_when_stock_data_exist():
    sc = cm.run_size_control(synthetic_panel(150), n_boot=20)
    base = {"weekly": make_weekly(), "macro": make_macro(), "tests": make_tests(), "flags": None, "quartiles": make_quartiles(),
            "panel": synthetic_panel(150), "size_control": sc}
    assert not any(k.startswith("6_") for k in viz.build_figures(base))
    story = dict(base, stock=make_stock(0.03))
    figs, ex = viz.build_figures(story), tx.build_explanations(story)
    assert {"6_pot", "6_porazdelitev", "6_skupine"} <= set(figs) and set(figs) == set(ex)
    for name, fig in figs.items():
        assert "plotly" in fig.to_html(include_plotlyjs="cdn"), name


def test_distribution_labels_do_not_sit_on_top_of_each_other():
    st = make_stock(0.0, seed=8)
    fig = viz.fig_car_distribution(st["cars"])
    labels = [a for a in fig.layout.annotations if a.text and (a.text.startswith("povprečje") or a.text.startswith("mediana"))]
    assert len(labels) == 2
    a, b = sorted(labels, key=lambda a: a.x)
    assert a.xanchor == "right" and b.xanchor == "left" and a.y != b.y             # left label on the left, other on the right, different rows


def test_path_text_reports_how_well_the_test_is_calibrated():
    st = make_stock(0.0, seed=3)
    none = tx.explain_car_path(st["path"], st["summary"])["omejitve"]
    assert "naključnih dnevih" not in none
    good = tx.explain_car_path(st["path"], st["summary"], {"bootstrap_false_positive_rate": 0.05})["omejitve"]
    assert "5 %" in good and "dobro umerjen" in good
    liberal = tx.explain_car_path(st["path"], st["summary"], {"bootstrap_false_positive_rate": 0.08})["omejitve"]
    assert "8 %" in liberal and "sklepa ne spremeni" in liberal                  # this fake result spans zero
    real = make_stock(0.03)
    careful = tx.explain_car_path(real["path"], real["summary"], {"bootstrap_false_positive_rate": 0.09})["omejitve"]
    assert "jemati previdno" in careful                                         # a significant result with a liberal test
