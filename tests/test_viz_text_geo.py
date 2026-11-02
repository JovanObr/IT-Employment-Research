"""Chapter 4-5 figures and explanations (Stream B): synthetic data only, no network, no real files."""
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from analysis import geo
from analysis import hn_text as ht
from analysis import viz_text_geo as v
from analysis.viz_theme import explanation_markdown, sl_num, sl_pct
from hn_synth import make_hn

NAMES = ["4_teme_povrsina", "4_teme_mali_grafi", "4_teme_toplotna", "4_daljava_ui", "5_zemljevid", "5_regije"]
LABELS = [f"T{i + 1}: {k}" for i, k in enumerate(v.TOPIC_SL)]


# ---------------------------------------------------------------------------------------- synthetic data
def make_topics(start="2015-01", end="2026-06", grow=7, shrink=6, k=10):
    """Monthly topic shares summing to 1: topic `grow` rises over time, topic `shrink` falls."""
    months = pd.period_range(start, end, freq="M").strftime("%Y-%m")
    n = len(months)
    base = np.ones((n, k))
    base[:, grow] = np.linspace(0.05, 4.0, n)
    base[:, shrink] = np.linspace(3.0, 0.2, n)
    base += np.random.default_rng(0).uniform(0, 0.1, base.shape)
    base /= base.sum(axis=1, keepdims=True)
    return pd.DataFrame([{"month": m, "topic": LABELS[j], "share": base[i, j]} for i, m in enumerate(months) for j in range(k)])


def make_flags(remote_end=0.55, ai_end=0.6, start="2015-01", end="2026-06"):
    m = pd.period_range(start, end, freq="M").strftime("%Y-%m")
    n = len(m)
    remote = np.where(np.arange(n) < 63, 0.25, 0.8)
    remote[-36:] = remote_end
    ai = np.linspace(0.1, ai_end, n)
    return pd.concat([pd.DataFrame({"month": m, "flag": "remote", "share": remote, "n_posts": 500}),
                      pd.DataFrame({"month": m, "flag": "ai_ml", "share": ai, "n_posts": 500})], ignore_index=True)


def make_change_points():
    return pd.DataFrame({"flag": ["remote", "remote", "remote", "ai_ml", "ai_ml"],
                         "start": ["2015-01", "2020-04", "2023-07", "2015-01", "2023-02"],
                         "end": ["2020-03", "2023-06", "2026-06", "2023-01", "2026-06"],
                         "months": [63, 39, 36, 97, 41], "mean_share": [0.25, 0.8, 0.55, 0.2, 0.5]})


def make_geo(shift=0.0):
    """Lower-48 metros (some withheld), one Alaska metro and one without a centroid."""
    rows = [
        ("16980", "Chicago-Naperville-Elgin, IL-IN-WI Metro Area", 41.8, -87.9, 70000, 70000, np.nan, np.nan, False, 3000, 20.0, True),
        ("19100", "Dallas-Fort Worth-Arlington, TX Metro Area", 32.8, -97.0, 50000, 50000, 74000, 48.0, True, 2500, 60.0, True),
        ("19820", "Detroit-Warren-Dearborn, MI Metro Area", 42.7, -83.2, 40000, 40000, 31000, -22.0, True, 1800, -5.0, True),
        ("14460", "Boston-Cambridge-Newton, MA-NH Metro Area", 42.5, -71.1, 60000, 60000, 57000, -5.0, True, 3500, 12.0, True),
        ("31080", "Los Angeles-Long Beach-Anaheim, CA Metro Area", 34.0, -118.2, 55000, 55000, 52000, -6.0, True, 4000, 30.0, True),
        ("19740", "Denver-Aurora-Lakewood, CO Metro Area", 39.7, -104.9, 35000, 35000, 45000, 30.0, True, 2000, 40.0, True),
        ("12060", "Atlanta-Sandy Springs-Alpharetta, GA Metro Area", 33.8, -84.4, np.nan, np.nan, np.nan, 999.0, False, 2400, np.nan, False),
        ("10180", "Abilene, TX Metro Area", 32.5, -99.7, 229, 229, 317, 38.3, True, 45, 31.0, True),
        ("11260", "Anchorage, AK Metro Area", 61.2, -149.9, 900, 900, 950, 5.0, True, 80, 3.0, True),
        ("99999", "Nowhere, ZZ Metro Area", np.nan, np.nan, 100, 100, 120, 20.0, True, 10, 5.0, True),
    ]
    cols = ["cbsa_code", "metro_name", "lat", "lon", "size_jobs", "emp_it_2019", "emp_it_2024", "it_growth_pct", "usable",
            "estabs_it_2019", "estab_growth_pct", "usable_estab"]
    g = pd.DataFrame(rows, columns=cols)
    g["wfh_share_pct_acs2019"] = 5.0
    g.loc[g["usable"], "it_growth_pct"] += shift
    return g


def check(parts):
    assert set(parts) == {"kaj", "zakaj", "pomen", "omejitve"}
    for k, text in parts.items():
        assert isinstance(text, str) and len(text.strip()) > 40, k
        low = text.lower()
        assert not re.search(r"\bnan\b", low) and "none" not in low and "nan %" not in low, k
    explanation_markdown(parts)


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)*", text or ""))


def all_hover(fig) -> str:
    out = []
    for tr in fig.data:
        for attr in ("hovertemplate", "text", "y"):
            val = getattr(tr, attr, None)
            if val is None:
                continue
            out += [str(x) for x in (val if isinstance(val, (list, tuple, np.ndarray)) else [val])]
    return " ".join(out)


# ---------------------------------------------------------------------------------------- D1 / D2 writers
def test_flag_aggregates_have_no_text_and_leave_junior_out(tmp_path):
    posts, _ = make_hn(posts_per_month=20, start="2019-01", end="2023-12")
    posts["month"] = pd.to_datetime(posts["thread_month"]).dt.to_period("M").dt.to_timestamp()
    p1, p2 = ht.write_flag_aggregates(posts, tmp_path)
    f, cp = pd.read_csv(p1), pd.read_csv(p2)
    assert list(f.columns) == ["month", "flag", "share", "n_posts"] and set(f["flag"]) == {"remote", "ai_ml"}
    assert list(cp.columns) == ["flag", "start", "end", "months", "mean_share"]
    assert f["share"].between(0, 1).all() and (f["n_posts"] == 20).all() and f["month"].str.fullmatch(r"\d{4}-\d{2}").all()
    for flag, seg in cp.groupby("flag"):                       # segments tile the whole period
        assert seg["months"].sum() == f[f["flag"] == flag].shape[0]
    rem = cp[cp["flag"] == "remote"]
    assert "2020-04" in rem["start"].tolist()                    # the planted remote step is found


def test_map_data_keeps_every_metro_with_string_codes():
    g = make_geo().drop(columns=["wfh_share_pct_acs2019"])
    g["cbsa_code"] = g["cbsa_code"].str.lstrip("0")
    out = geo.map_data(g)
    assert list(out.columns) == geo.MAP_COLUMNS and len(out) == len(g)
    assert out["cbsa_code"].str.len().eq(5).all() and out["lat"].isna().sum() == 1


# ---------------------------------------------------------------------------------------- entry point
def write_inputs(processed):
    make_topics().to_csv(processed / "hn_topics_monthly.csv", index=False)
    make_flags().to_csv(processed / "hn_flags_monthly.csv", index=False)
    make_change_points().to_csv(processed / "hn_change_points.csv", index=False)
    geo.map_data(make_geo()).to_csv(processed / "metro_map_data.csv", index=False)


def test_build_chapter_4_5_returns_the_fixed_names_with_figures_and_texts(data_dir):
    write_inputs(data_dir / "processed")
    out = v.build_chapter_4_5()
    assert list(out) == NAMES
    for name, (fig, parts) in out.items():
        assert isinstance(fig, go.Figure), name
        check(parts)


def test_build_chapter_4_5_raises_a_clear_error_when_a_file_is_missing(data_dir):
    write_inputs(data_dir / "processed")
    (data_dir / "processed" / "metro_map_data.csv").unlink()
    with pytest.raises(FileNotFoundError, match="analysis.geo mapdata"):
        v.build_chapter_4_5()


def test_loader_reads_usable_flags_as_booleans_and_codes_as_strings(data_dir):
    write_inputs(data_dir / "processed")
    g = v.load_map_data()
    assert g["usable"].dtype == bool and g["cbsa_code"].str.len().eq(5).all()
    assert g.loc[g["cbsa_code"] == "16980", "usable"].item() is False or not g.loc[g["cbsa_code"] == "16980", "usable"].item()


# ---------------------------------------------------------------------------------------- chapter 4 figures
def test_stacked_area_has_one_stacked_trace_per_topic_with_names_in_hover():
    t = make_topics()
    t0 = t.copy()
    fig = v.fig_topics_stacked_area(t)
    assert len(fig.data) == 10 and all(tr.stackgroup == "one" for tr in fig.data)
    assert all(v.topic_name(lab) in tr.hovertemplate for lab, tr in zip(LABELS, fig.data))
    assert len(fig.layout.shapes) == 2                                    # fed + ChatGPT
    pd.testing.assert_frame_equal(t, t0)


def test_topic_names_are_translated_and_unknown_labels_survive():
    assert v.topic_name("T10: open source") == "odprta koda"
    assert v.topic_name("T11: something new") == "something new"


def test_small_multiples_share_the_y_axis_and_mark_chatgpt_in_every_panel():
    t = make_topics()
    t0 = t.copy()
    fig = v.fig_topics_small_multiples(t, ncols=5)
    assert len(fig.data) == 20                                            # thin + thick per topic
    assert len(fig.layout.shapes) == 10
    axes = [k for k in fig.layout if k.startswith("yaxis")]
    targets = {fig.layout[k].matches for k in axes} - {None}
    assert len(axes) == 10 and len(targets) == 1                         # every panel follows one y axis
    assert sum(fig.layout[k].matches is None for k in axes) == 1
    titles = [a.text for a in fig.layout.annotations]
    assert all(any(v.topic_name(lab)[:20] in s for s in titles) for lab in LABELS)
    pd.testing.assert_frame_equal(t, t0)


def test_heatmap_orders_rows_by_change_and_prints_values():
    t = make_topics(grow=7, shrink=6)
    fig = v.fig_topic_year_heatmap(t)
    h = fig.data[0]
    assert h.y[0] == v.topic_name(LABELS[7]) and h.y[-1] == v.topic_name(LABELS[6])
    assert h.texttemplate == "%{text}" and np.array(h.z).shape == (10, 12)
    assert "%{y}" in h.hovertemplate


def test_remote_ai_levels_draws_lines_and_flat_steps():
    f, cp = make_flags(), make_change_points()
    f0, cp0 = f.copy(), cp.copy()
    fig = v.fig_remote_ai_levels(f, cp)
    assert len(fig.data) == 4 and len(fig.layout.shapes) == 3            # covid, fed, ChatGPT
    steps = fig.data[1]
    y = [x for x in steps.y if x is not None]
    assert y[0] == y[1] == pytest.approx(25.0)                          # flat steps at the segment mean
    assert len(v.fig_remote_ai_levels(f).data) == 2                    # change points optional
    pd.testing.assert_frame_equal(f, f0); pd.testing.assert_frame_equal(cp, cp0)


def test_chapter_4_figures_survive_nan():
    t = make_topics()
    t.loc[5, "share"] = np.nan
    f = make_flags()
    f.loc[3, "share"] = np.nan
    v.fig_topics_stacked_area(t); v.fig_topics_small_multiples(t); v.fig_topic_year_heatmap(t)
    v.fig_remote_ai_levels(f, make_change_points())
    check(v.explain_topics_stacked_area(t)); check(v.explain_remote_ai_levels(f, make_change_points()))


# ---------------------------------------------------------------------------------------- chapter 5 figures
def test_map_draws_withheld_metros_as_grey_crosses_never_as_zero():
    g = make_geo()
    g0 = g.copy()
    fig = v.fig_metro_map(g)
    assert len(fig.data) == 5                                             # outline + (bubbles, crosses) x 2 metrics
    bubbles, crosses = fig.data[1], fig.data[2]
    assert crosses.marker.symbol == "x"
    assert all("podatek je skrit" in s for s in crosses.text)
    assert any("Chicago" in s for s in crosses.text) and any("Atlanta" in s for s in crosses.text)
    assert not any("Chicago" in s or "Atlanta" in s for s in bubbles.text)
    assert 999.0 not in list(bubbles.marker.color)                        # unusable value never coloured
    assert not any("Anchorage" in s or "Nowhere" in s for s in list(bubbles.text) + list(crosses.text))
    assert any("Dallas" in s for s in bubbles.text)
    pd.testing.assert_frame_equal(g, g0)


def test_map_colour_is_centred_on_zero_and_clipped_with_a_note():
    fig = v.fig_metro_map(make_geo())
    m = fig.data[1].marker
    assert m.cmin == -m.cmax and m.cmid == 0 and max(m.color) <= m.cmax
    assert "skrčene" in m.colorbar.title.text
    assert fig.layout.yaxis.scaleanchor == "x" and fig.layout.yaxis.scaleratio == pytest.approx(1.3)


def test_map_bubble_area_grows_with_jobs():
    fig = v.fig_metro_map(make_geo())
    b = fig.data[1]
    size = dict(zip([s.split("</b>")[0] for s in b.text], b.marker.size))
    assert size["<b>Dallas-Fort Worth-Arlington, TX"] > size["<b>Abilene, TX"]
    big, small = 50000, 229
    assert size["<b>Dallas-Fort Worth-Arlington, TX"] / size["<b>Abilene, TX"] == pytest.approx(np.sqrt(big / small), rel=0.05) or \
        size["<b>Abilene, TX"] == 5.0                                     # tiny bubbles have a minimum size


def test_map_dropdown_switches_metric_and_usable_flag():
    g = make_geo()
    fig = v.fig_metro_map(g)
    menu = fig.layout.updatemenus[0]
    assert len(menu.buttons) == 2
    vis_jobs, vis_est = menu.buttons[0].args[0]["visible"], menu.buttons[1].args[0]["visible"]
    assert vis_jobs == [True, True, True, False, False] and vis_est == [True, False, False, True, True]
    est_crosses = fig.data[4]
    assert any("Atlanta" in s for s in est_crosses.text) and not any("Chicago" in s for s in est_crosses.text)
    assert fig.data[3].visible is False
    fig2 = v.fig_metro_map(g, metric="estab_growth_pct")
    assert fig2.data[3].visible is True and fig2.layout.updatemenus[0].active == 1
    with pytest.raises(ValueError):
        v.fig_metro_map(g, metric="nope")


def test_map_survives_nan_sizes():
    g = make_geo()
    g.loc[g["cbsa_code"] == "19740", ["size_jobs", "emp_it_2019"]] = np.nan
    fig = v.fig_metro_map(g)
    denver = [s for s in fig.data[1].text if "Denver" in s][0]
    assert "podatek je skrit" in denver                                   # unknown 2019 jobs are written, not 0


def test_region_small_multiples_has_four_panels_and_medians():
    g = make_geo()
    fig = v.fig_region_small_multiples(g)
    assert len(fig.data) == 4 and {tr.name for tr in fig.data} == set(v.REGIONS)
    meds = [a.text for a in fig.layout.annotations if (a.text or "").startswith("mediana")]
    assert len(meds) == 4 and f"mediana {sl_num(-5.0, 1)} %" in meds    # Boston is the only usable northeast metro
    assert v._region("Boston-Cambridge-Newton, MA-NH Metro Area") == "severovzhod" and v._region("no comma") is None


# ---------------------------------------------------------------------------------------- titles carry only computed numbers
def test_titles_change_with_the_data_and_contain_only_computed_numbers():
    t1, t2 = make_topics(), make_topics(start="2017-01", end="2024-12")
    for fn in (v.fig_topics_stacked_area, v.fig_topic_year_heatmap):
        a, b = fn(t1).layout.title.text, fn(t2).layout.title.text
        assert a != b and numbers(a) <= {"10", "2015", "2026"} and numbers(b) <= {"10", "2017", "2024"}
    f2 = make_flags(start="2018-01", end="2025-12")
    assert numbers(v.fig_remote_ai_levels(f2).layout.title.text) <= {"2018", "2025"}
    g = make_geo()
    n_ok = len(v._map_parts(g, "it_growth_pct")["ok"])
    title = v.fig_metro_map(g).layout.title.text
    assert numbers(title) <= {"2019", "2024", str(n_ok)} and str(n_ok) in numbers(title)
    fewer = g[g["cbsa_code"] != "19100"]
    assert v.fig_metro_map(fewer).layout.title.text != title
    est_title = v.fig_metro_map(g).layout.updatemenus[0].buttons[1].args[1]["title.text"]
    assert str(len(v._map_parts(g, "estab_growth_pct")["ok"])) in numbers(est_title)


# ---------------------------------------------------------------------------------------- explanations
def test_stacked_area_text_uses_computed_shares_and_follows_the_data():
    t = make_topics()
    e = v.explain_topics_stacked_area(t)
    check(e)
    w = v._topics_wide(t)
    up = v.topic_name(LABELS[7])
    assert up in e["pomen"] and sl_pct(w[up].iloc[-12:].mean(), 0) in e["pomen"] and "narasla" in e["pomen"]
    e2 = v.explain_topics_stacked_area(make_topics(grow=2, shrink=4))
    assert e2["pomen"] != e["pomen"] and v.topic_name(LABELS[2]) in e2["pomen"]


def test_small_multiples_text_counts_topics_and_handles_data_before_chatgpt():
    t = make_topics()
    e = v.explain_topics_small_multiples(t)
    check(e)
    assert "10 tem" in e["kaj"] and v.topic_name(LABELS[7]) in e["pomen"]
    early = v.explain_topics_small_multiples(make_topics(end="2021-12"))
    check(early)
    assert "ne moremo" in early["pomen"]


def test_heatmap_text_names_biggest_gain_and_loss_with_numbers():
    t = make_topics()
    e = v.explain_topic_year_heatmap(t)
    check(e)
    tab = v.topic_change_table(t)
    assert sl_pct(tab.iloc[0]["last"], 1) in e["pomen"] and sl_pct(tab.iloc[-1]["first"], 1) in e["pomen"]
    assert "2015-2017" in e["pomen"] and "2024-2026" in e["pomen"]


def test_remote_ai_text_wording_flips_when_the_data_flips():
    up = v.explain_remote_ai_levels(make_flags(remote_end=0.55), make_change_points())
    down = v.explain_remote_ai_levels(make_flags(remote_end=0.05), make_change_points())
    check(up); check(down)
    first_up, first_down = up["pomen"].split(". ")[0], down["pomen"].split(". ")[0]
    assert "narasel" in first_up and "padel" in first_down
    assert sl_pct(0.05, 0) in down["pomen"] and "4/2020" in up["pomen"]


def test_map_text_numbers_come_from_the_data_and_flip_with_it():
    g = make_geo()
    e = v.explain_metro_map(g)
    check(e)
    ok = v._map_parts(g, "it_growth_pct")["ok"]
    med = ok["it_growth_pct"].median()
    assert sl_num(abs(med), 1) in e["pomen"] and "zrasla" in e["pomen"] and str(len(ok)) in e["pomen"]
    assert "Dallas" in e["pomen"] and "Detroit" in e["pomen"] and "Chicago" in e["pomen"]
    neg = v.explain_metro_map(make_geo(shift=-100.0))
    check(neg)
    assert "padla" in neg["pomen"].split(";")[1]
    assert "NAICS 5415" in e["omejitve"] and "ni nič" in e["omejitve"]


def test_region_text_lists_every_region_median_and_flips():
    g = make_geo()
    e = v.explain_region_small_multiples(g)
    check(e)
    assert "na jugu" in e["pomen"] and sl_num(5.0, 1) in e["pomen"]
    g2 = g.copy()
    g2.loc[g2["metro_name"].str.contains("TX"), "it_growth_pct"] = -80.0
    assert "najnižja na jugu" in v.explain_region_small_multiples(g2)["pomen"]


def test_build_explanations_and_figures_share_the_names():
    args = (make_topics(), make_flags(), make_change_points(), make_geo())
    assert list(v.build_figures(*args)) == list(v.build_explanations(*args)) == NAMES
