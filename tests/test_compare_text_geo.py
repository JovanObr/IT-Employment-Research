"""Notebook 09, Stream B comparisons (analysis/compare_text_geo.py) and the junior_v2 rule (analysis/hn_text.py).
Synthetic data only, no network, no real files."""
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from analysis import compare_text_geo as c
from analysis import geo
from analysis import hn_text as ht
from analysis.viz_theme import explanation_markdown
from collectors import indeed_remote

NAMES = ["9b_daljava_primerjava", "9b_ui_primerjava", "9b_regije_primerjava"]


# ---------------------------------------------------------------------------------------- synthetic data
def make_flags(remote_2019=0.3, remote_end=0.55, ai_end=0.6, n_start=600, n_end=300, junior=None, start="2015-01", end="2026-06"):
    m = pd.period_range(start, end, freq="M")
    n = len(m)
    yr = np.array([p.year for p in m])
    remote = np.where(yr < 2020, remote_2019, 0.8)
    remote[yr >= 2024] = remote_end
    ai = np.linspace(0.1, ai_end, n)
    posts = np.linspace(n_start, n_end, n).round()
    parts = [pd.DataFrame({"month": m.strftime("%Y-%m"), "flag": "remote", "share": remote, "n_posts": posts}),
             pd.DataFrame({"month": m.strftime("%Y-%m"), "flag": "ai_ml", "share": ai, "n_posts": posts})]
    if junior is not None:
        jr = np.where(m.to_timestamp() <= pd.Timestamp("2022-11-01"), junior[0], junior[1])
        parts.append(pd.DataFrame({"month": m.strftime("%Y-%m"), "flag": "junior_v2", "share": jr, "n_posts": posts}))
    return pd.concat(parts, ignore_index=True)


def make_indeed(base=2.6, end=8.7, peak="2022-02"):
    m = pd.period_range("2019-01", "2026-09", freq="M")
    rows = []
    for sector, mult in (("all", 1.0), ("techsoftware", 3.0)):
        for p in m:
            v = base if p.year == 2019 else end
            if p.strftime("%Y-%m") == peak:
                v = end * 1.3
            rows.append({"month": p.strftime("%Y-%m"), "sector": sector, "remote_share_pct": v * mult, "n_days": 30})
    return pd.DataFrame(rows)


def make_geo(shift=0.0, hide=("33460", "12060")):
    """Every metro named in the studies plus one other; Austin grows, Boston shrinks; `hide` are withheld."""
    growth = {"12420": 40.0, "14460": -18.0, "42660": 15.0, "41860": -2.0, "41940": -3.0, "35620": 4.5, "47900": -4.0,
              "31080": -12.0, "33460": 5.0, "12060": 9.0, "19100": 48.0, "19740": 32.0, "33100": 33.0, "36740": 34.0,
              "41740": -10.0, "28140": 7.0, "41180": 2.0, "41620": 22.0, "10180": 38.0}
    rows = []
    for code, gr in growth.items():
        name = c.STUDY_METROS.set_index("cbsa_code")["name"].get(code, "Abilene")
        usable = code not in hide
        rows.append({"cbsa_code": code, "metro_name": f"{name}-Other, XX Metro Area", "lat": 35.0, "lon": -95.0, "size_jobs": 1000.0,
                     "emp_it_2019": 1000.0 if usable else np.nan, "emp_it_2024": 1100.0 if usable else np.nan,
                     "it_growth_pct": gr + shift if usable else np.nan, "usable": usable, "estabs_it_2019": 50.0,
                     "estab_growth_pct": 10.0, "usable_estab": True, "wfh_share_pct_acs2019": 5.0})
    return pd.DataFrame(rows)


def check(parts):
    assert set(parts) == {"kaj", "zakaj", "pomen", "omejitve"}
    for k, text in parts.items():
        assert isinstance(text, str) and len(text.strip()) > 40, k
        low = text.lower()
        assert not re.search(r"\bnan\b", low) and "none" not in low, k
    explanation_markdown(parts)


def check_verdict(v):
    assert set(v) == set(c.VERDICT_KEYS)
    assert all(str(v[k]).strip() for k in c.VERDICT_KEYS)
    assert v["ocena"] in c.VERDICTS
    assert "nan" not in v["nas_rezultat"].lower() and "none" not in v["nas_rezultat"].lower()


def numbers(text):
    return set(re.findall(r"\d+(?:[.,]\d+)*", text))


def write_inputs(processed, flags=None):
    (flags if flags is not None else make_flags()).to_csv(processed / "hn_flags_monthly.csv", index=False)
    make_indeed().to_csv(processed / "indeed_remote_monthly.csv", index=False)
    geo.map_data(make_geo()).to_csv(processed / "metro_map_data.csv", index=False)


# ---------------------------------------------------------------------------------------- entry point
def test_build_comparisons_b_names_and_tuple_shape(data_dir):
    write_inputs(data_dir / "processed")
    out = c.build_comparisons_b()
    assert list(out) == NAMES
    for name, item in out.items():
        assert isinstance(item, tuple) and len(item) == 3
        fig, parts, verdict = item
        assert isinstance(fig, go.Figure), name
        check(parts)
        check_verdict(verdict)


def test_youth_comparison_appears_only_with_junior_v2(data_dir):
    write_inputs(data_dir / "processed", make_flags(junior=(0.08, 0.05)))
    out = c.build_comparisons_b()
    assert list(out) == NAMES[:2] + ["9b_mladi"] + NAMES[2:]
    check(out["9b_mladi"][1])
    check_verdict(out["9b_mladi"][2])


@pytest.mark.parametrize("missing,hint", [("indeed_remote_monthly.csv", "compare_text_geo aggregates"),
                                          ("hn_flags_monthly.csv", "hn_text flags"),
                                          ("metro_map_data.csv", "geo mapdata")])
def test_missing_aggregate_raises_a_clear_error(data_dir, missing, hint):
    write_inputs(data_dir / "processed")
    (data_dir / "processed" / missing).unlink()
    with pytest.raises(FileNotFoundError, match=hint):
        c.build_comparisons_b()


def test_build_figures_names_match_data_sources():
    from analysis import data_sources as ds
    figs = c.build_figures(make_flags(junior=(0.08, 0.05)), make_indeed(), make_geo())
    assert set(figs) <= set(ds.FIGURE_SOURCES)


# ---------------------------------------------------------------------------------------- remote
def test_remote_numbers_follow_the_data():
    a = c.explain_remote_compare(make_flags(remote_2019=0.3, remote_end=0.55), make_indeed())["pomen"]
    b = c.explain_remote_compare(make_flags(remote_2019=0.2, remote_end=0.7), make_indeed())["pomen"]
    assert "30 %" in a and "55 %" in a and "20 %" in b and "70 %" in b
    assert numbers(a) != numbers(b)
    assert "Hansen" in a and "3-krat" in a and "Indeed" in a


def test_remote_wording_and_verdict_flip_with_the_data():
    up = make_flags(remote_2019=0.1, remote_end=0.5)               # 5x: as big as the study's, peak close to Indeed's
    down = make_flags(remote_2019=0.6, remote_end=0.3)
    assert "isto smer" in c.explain_remote_compare(up, make_indeed())["pomen"]
    assert "nasprotno smer" in c.explain_remote_compare(down, make_indeed())["pomen"]
    assert c.verdict_remote_compare(down, make_indeed())["ocena"] == "se razlikuje"
    mid = make_flags(remote_2019=0.3, remote_end=0.5)
    assert c.verdict_remote_compare(mid, make_indeed())["ocena"] == "delno"


def test_remote_without_indeed_still_explains():
    check(c.explain_remote_compare(make_flags(), None))
    check_verdict(c.verdict_remote_compare(make_flags(), None))
    assert isinstance(c.fig_remote_compare(make_flags(), None), go.Figure)


def test_indeed_monthly_aggregate_from_daily_rows():
    raw = pd.DataFrame({"date": ["2019-01-01", "2019-01-02", "2019-02-01", "2019-01-01"], "country": "US",
                        "sector": ["all", "all", "all", "retail"], "remote_share_pct": [2.0, 4.0, 5.0, 1.0]})
    out = c.indeed_remote_monthly(raw)
    assert out[["month", "sector"]].values.tolist() == [["2019-01", "all"], ["2019-02", "all"]]
    assert out["remote_share_pct"].tolist() == [3.0, 5.0] and out["n_days"].tolist() == [2, 1]


def test_indeed_collector_parses_both_layouts():
    country = "date,jobcountry,remote_share_postings\n2019-01-01,US,2.5\n2019-01-01,DE,1.0\n"
    sector = "date,jobcountry,normtitlecategory_consistent,remote_share_postings\n2019-01-01,US,techsoftware,8.0\n"
    a, b = indeed_remote.parse(country), indeed_remote.parse(sector.encode())
    assert a.to_dict("records") == [{"date": "2019-01-01", "country": "US", "sector": "all", "remote_share_pct": 2.5}]
    assert b["sector"].tolist() == ["techsoftware"]
    with pytest.raises(ValueError):
        indeed_remote.parse("a,b\n1,2\n")


# ---------------------------------------------------------------------------------------- AI
def test_ai_numbers_and_verdict_follow_the_data():
    falling = make_flags(n_start=600, n_end=300, ai_end=0.6)
    rising = make_flags(n_start=300, n_end=600, ai_end=0.6)
    a, b = c.explain_ai_compare(falling)["pomen"], c.explain_ai_compare(rising)["pomen"]
    assert numbers(a) != numbers(b) and "+59 %" in a and "Bernard" in a
    assert "isto sliko" in a and "isto sliko" not in b
    assert c.verdict_ai_compare(falling)["ocena"] == "se ujema"
    assert c.verdict_ai_compare(rising)["ocena"] == "delno"
    flat_ai = make_flags(n_start=300, n_end=600, ai_end=0.1)
    flat_ai.loc[flat_ai["flag"] == "ai_ml", "share"] = np.linspace(0.3, 0.05, (flat_ai["flag"] == "ai_ml").sum())
    assert c.verdict_ai_compare(flat_ai)["ocena"] == "se razlikuje"


def test_ai_falls_back_to_first_and_last_months_without_2020_or_2025():
    f = make_flags(start="2021-01", end="2023-12")
    check(c.explain_ai_compare(f))
    check_verdict(c.verdict_ai_compare(f))


# ---------------------------------------------------------------------------------------- youth
def test_youth_wording_and_verdict_flip():
    down, up = make_flags(junior=(0.08, 0.05)), make_flags(junior=(0.05, 0.08))
    assert "padel" in c.explain_youth(down)["pomen"] and "narasel" in c.explain_youth(up)["pomen"]
    assert c.verdict_youth(down)["ocena"] == "se ujema" and c.verdict_youth(up)["ocena"] == "se razlikuje"
    assert "19 %" in c.explain_youth(down)["pomen"]


# ---------------------------------------------------------------------------------------- geography
def test_bernard_pairs_skip_unknown_orders_and_withheld_metros():
    t = c.metro_compare_table(make_geo())
    bp = c.bernard_pairs(t)
    # Austin vs Boston, Seattle, San Francisco are checkable; Austin vs Minneapolis is withheld; Boston vs ">40 %" is unknown
    assert (bp["concordant"], bp["discordant"], bp["skipped"]) == (3, 0, 1)


def test_regions_numbers_wording_and_verdict_follow_the_data():
    g1 = make_geo()
    g2 = make_geo()
    g2.loc[g2["cbsa_code"] == "12420", "it_growth_pct"] = -30.0     # Austin now below Boston, Seattle, San Francisco
    for code in ("19100", "19740", "33100", "36740", "41620"):
        g2.loc[g2["cbsa_code"] == code, "it_growth_pct"] = -40.0   # rising stars now slower than superstars
    a, b = c.explain_regions_compare(g1)["pomen"], c.explain_regions_compare(g2)["pomen"]
    assert numbers(a) != numbers(b)
    assert "hitreje" in a and "počasneje" in b
    assert c.verdict_regions_compare(g1)["ocena"] == "se ujema"
    assert c.verdict_regions_compare(g2)["ocena"] == "se razlikuje"
    assert "Minneapolis" in a                                        # withheld metros are named


def test_regions_all_withheld_is_not_comparable():
    g = make_geo(hide=tuple(c.STUDY_METROS["cbsa_code"]))
    v = c.verdict_regions_compare(g)
    check_verdict(v)
    assert v["ocena"] == "ni primerljivo"
    check(c.explain_regions_compare(g))


def test_regions_figure_marks_withheld_and_bounds():
    fig = c.fig_regions_compare(make_geo())
    names = [tr.name for tr in fig.data]
    assert any("skrit" in n for n in names) and any("40" in n for n in names)
    hidden = next(tr for tr in fig.data if "skrit" in tr.name)
    assert len(hidden.y) == 2 and set(hidden.text) == {"podatek je skrit"}


# ---------------------------------------------------------------------------------------- figure smoke tests
@pytest.mark.parametrize("make", [
    lambda f, i, g: c.fig_remote_compare(f, i), lambda f, i, g: c.fig_ai_compare(f),
    lambda f, i, g: c.fig_youth(f), lambda f, i, g: c.fig_regions_compare(g)])
def test_figures_do_not_modify_inputs_and_survive_nan(make):
    f, i, g = make_flags(junior=(0.08, 0.05)), make_indeed(), make_geo()
    f.loc[f.index[5], "share"] = np.nan
    i.loc[i.index[3], "remote_share_pct"] = np.nan
    g.loc[g.index[0], "it_growth_pct"] = np.nan
    f0, i0, g0 = f.copy(), i.copy(), g.copy()
    assert isinstance(make(f, i, g), go.Figure)
    pd.testing.assert_frame_equal(f, f0)
    pd.testing.assert_frame_equal(i, i0)
    pd.testing.assert_frame_equal(g, g0)


def test_preview_command_writes_html(data_dir, monkeypatch, tmp_path):
    write_inputs(data_dir / "processed")
    import analysis.compare_text_geo as mod
    written = []
    monkeypatch.setattr(mod, "save_html", lambda fig, name: written.append(name) or tmp_path / f"{name}.html")
    monkeypatch.setattr("sys.argv", ["x", "preview"])
    mod.main()
    assert written == [f"preview_{n}" for n in NAMES]


# ---------------------------------------------------------------------------------------- D1: junior_v2
POSITIVE = [
    "We are hiring junior developers and interns.",
    "Hiring new grads for junior SWE",
    "Entry-level candidates welcome",
    "Software Engineer I | Remote | NYC",
    "0-2 years of experience is fine",
    "Bootcamp graduates welcome",
    "Graduate Financial Software Developer | Belfast",
    "Ideal for someone starting their career in tech",
    "We have roles from Jr. Developer to Staff.",
    "Summer internships available for students graduating in 2024",
    "You will mentor junior engineers. We also hire juniors!",
]
NEGATIVE = [
    "Note, I currently don't have openings for interns or recent college grads.",
    "Sorry, can't do internships or new grad hires!",
    "No juniors please.",
    "We are not hiring interns at this time.",
    "You will mentor junior engineers and lead design.",
    "Experience onboarding, mentoring and coaching more junior engineers",
    "Please, no remote, no recent bootcamp graduates, no recruiters.",
    "Senior Software Engineer II",
    "Graduate degree in CS preferred; our founders are graduates from MIT.",
    "Software Engineer I/II",
    "5+ years Python, 1+ years Go",
    "Data Engineer\nI am the CTO, write to me.",
]


@pytest.mark.parametrize("text", POSITIVE)
def test_junior_v2_positive_sentences(text):
    assert ht.junior_v2(text) == 1, ht.junior_v2_matches(text)


@pytest.mark.parametrize("text", NEGATIVE)
def test_junior_v2_negative_sentences_and_negations(text):
    assert ht.junior_v2(text) == 0, ht.junior_v2_matches(text)


def test_junior_v2_leaves_the_old_flag_alone():
    from collectors.hn import features
    assert features("No junior developers please.")["junior"] == 1      # the old rule has no negation check (unchanged)
    assert ht.junior_v2("No junior developers please.") == 0
    df = pd.DataFrame({"text": ["junior role", "", None]})
    out = ht.add_junior_v2(df)
    assert out["junior_v2"].tolist() == [1, 0, 0] and "junior_v2" not in df


def test_stratified_sample_is_fresh_blind_and_weighted():
    texts = ["junior dev"] * 50 + ["mid-level backend role at a bank"] * 30 + ["we build databases"] * 300
    df = pd.DataFrame({"post_id": [str(i) for i in range(len(texts))], "thread_month": "2020-01-01", "text": texts})
    s = ht.make_stratified_sample(df, n=40)
    assert len(s) == 40 and set(s["stratum"]) == {"seniority", "other"}
    assert not {"junior", "junior_v2", "remote"} & set(s.columns) and (s["label_junior"] == "").all()
    w = s.groupby("stratum")["weight"].first()
    assert w["seniority"] == pytest.approx(80 / 20) and w["other"] == pytest.approx(300 / 20)
    assert (s["stratum"] == "seniority").sum() == 20
    assert ht.make_stratified_sample(df, n=40)["post_id"].tolist() == s["post_id"].tolist()     # reproducible


def test_validate_junior_v2_and_decision_rule():
    pos = ["We hire junior engineers"] * 18 + ["Hiring interns"] * 4
    neg = ["Senior staff role"] * 30 + ["Principal engineer"] * 2
    lab = pd.DataFrame({"post_id": [str(i) for i in range(len(pos) + len(neg) + 3)], "thread_month": "2020-01-01",
                        "text": pos + neg + ["Mentor junior engineers"] + ["early stage role"] * 2,
                        "stratum": "seniority", "weight": 1.0})
    lab["label_junior"] = ["1"] * len(pos) + ["0"] * len(neg) + ["0", "1", "1"]
    table, weighted, ok = ht.validate_junior_v2(lab)
    r = table.loc["junior_v2"]
    assert (r["true_pos"], r["false_pos"], r["false_neg"]) == (22, 0, 2)
    assert ok and weighted["recall_w"] == pytest.approx(22 / 24)
    assert not ht.junior_v2_decision({"precision": 0.79, "recall": 0.9, "recall_ci": (0.7, 0.95)})
    assert not ht.junior_v2_decision({"precision": 0.9, "recall": 0.55, "recall_ci": (0.30, 0.75)})
    assert ht.junior_v2_decision({"precision": 0.8, "recall": 0.5, "recall_ci": (0.35, 0.65)})


def test_flag_aggregates_with_junior_v2(tmp_path):
    from hn_synth import make_hn
    posts, text = make_hn(posts_per_month=20, start="2021-01", end="2023-12")
    posts["month"] = pd.to_datetime(posts["thread_month"]).dt.to_period("M").dt.to_timestamp()
    posts = ht.add_junior_v2(posts.merge(text, on="post_id")).drop(columns="text")
    p1, _ = ht.write_flag_aggregates(posts, tmp_path, with_junior_v2=True)
    f = pd.read_csv(p1)
    assert set(f["flag"]) == {"remote", "ai_ml", "junior_v2"} and "text" not in f.columns
