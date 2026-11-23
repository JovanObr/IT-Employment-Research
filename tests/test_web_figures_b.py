"""Stream B's website figures (chapters 5-6): built from synthetic aggregates, one message per chart, conclusion-first titles."""
import numpy as np
import pandas as pd

from analysis import web_figures_b as wb
from analysis import web_theme


def _flags():
    rows = []
    for y in range(2015, 2027):
        for m in range(1, 13 if y < 2026 else 11):
            remote = {2019: 0.3, 2022: 0.8}.get(y, 0.5)
            rows += [{"month": f"{y}-{m:02d}", "flag": "remote", "share": remote, "n_posts": 100},
                     {"month": f"{y}-{m:02d}", "flag": "ai_ml", "share": 0.15 if y < 2023 else 0.55, "n_posts": 100}]
    return pd.DataFrame(rows)


def _indeed():
    return pd.DataFrame([{"month": f"{y}-{m:02d}", "sector": s, "remote_share_pct": v, "n_days": 30}
                         for y in range(2019, 2027) for m in range(1, 10) for s, v in (("all", 5.0), ("techsoftware", 10.0 + y - 2019))])


def _geo():
    rows = []
    for i, c in enumerate(list(wb.RISING) + list(wb.SUPERSTARS)):
        rows.append({"cbsa_code": c, "it_growth_pct": 30.0 if c in wb.RISING else -2.0, "usable": "False" if c == "12060" else "True"})
    return pd.DataFrame(rows)


def _results():
    rng = np.random.default_rng(0)
    countries = ["AT", "BE", "SI", "DE", "FR"]
    values = {c: {"start": 3 + i, "change": 0.5 - 0.01 * i, "level_2021": 3.0 + i} for i, c in enumerate(countries)}
    series = [{"year": y, "si": 4.0 + (0.5 if y == 2021 else 0) - (0.6 if y == 2023 else 0), "eu27": 3.5 + 0.1 * (y - 2015),
               "min": 2.0, "max": 7.0, "q25": 3.0, "median": 4.0, "q75": 5.0} for y in range(2015, 2026)]
    metros = [{"name": f"M{i}, CA Metro Area", "coast": "west", "growth": float(rng.normal(0, 30)), "jobs_2019": 1000.0} for i in range(10)]
    metros += [{"name": f"N{i}, NY Metro Area", "coast": "east", "growth": float(rng.normal(10, 30)), "jobs_2019": 1000.0} for i in range(20)]
    return {"A2": {"values": values, "primary": {"b": -0.01, "intercept": 0.53, "r": -0.05, "p": 0.8, "ci_lo": -0.2, "ci_hi": 0.1,
                                                  "predicted_sign": True},
                   "slovenia": {"start": 5.0, "change": -0.5, "predicted_change": 0.6, "start_rank": 3}},
            "F": {"metros": metros, "primary": {"diff_median": -10.0, "p": 0.3, "n_west": 10, "n_east": 20, "median_west": 0.0,
                                                 "median_east": 10.0, "ci_lo": -25.0, "ci_hi": 5.0, "n_withheld_east": 3, "n_withheld_west": 1}},
            "B1": {"series": series, "break_year": 2021, "rank": {}, "change_2021_2024": {}, "earlier_rise": {},
                   "thousands": [{"year": y, "si": 40.0} for y in range(2015, 2026)]}}


def _data():
    return {"flags": wb.yearly_flags(_flags()), "indeed": wb.yearly_indeed(_indeed()), "metros": wb.study_metros(_geo()),
            "results": _results(), "last_month": "2026-10"}


def test_yearly_flags_weight_by_posts():
    f = pd.DataFrame([{"month": "2020-01", "flag": "remote", "share": 1.0, "n_posts": 1},
                      {"month": "2020-02", "flag": "remote", "share": 0.0, "n_posts": 3}])
    assert wb.yearly_flags(f).loc[2020, "remote"] == 0.25


def test_study_metros_keep_withheld_as_missing():
    m = wb.study_metros(_geo())
    assert np.isnan(m.loc[m["name"] == "Atlanta", "growth"].iloc[0])
    assert len(m) == len(wb.RISING) + len(wb.SUPERSTARS)


def test_all_figures_build_with_conclusion_titles_and_web_theme():
    figs = wb.build_web_figures(_data())
    assert set(figs) == {"5w_daljava", "5w_ui", "6w_regije", "6w_obali", "6w_slovenija", "6w_dohitevanje"}
    for name, fig in figs.items():
        assert fig.layout.title.text, name
        web_theme.apply(fig)                                   # the build's theme accepts every figure


def test_titles_follow_the_data():
    figs = wb.build_web_figures(_data())
    assert "2022" in figs["5w_daljava"].layout.title.text
    assert "več kot polovica" in figs["5w_ui"].layout.title.text
    assert "počasneje" in figs["6w_obali"].layout.title.text and "naključje" in figs["6w_obali"].layout.title.text
    assert figs["6w_slovenija"].layout.title.text.startswith("Slovenija je bila leta 2021 nad povprečjem EU")
    assert "skoraj ne vpliva" in figs["6w_dohitevanje"].layout.title.text
    assert "leto 2026: januar do oktober" in figs["5w_ui"].layout.title.text


def test_at_most_two_coloured_series():
    grey = {web_theme.ROLE["context"], web_theme.ROLE["muted"]}
    for name, fig in wb.build_web_figures(_data()).items():
        colours = set()
        for tr in fig.data:
            for c in (getattr(getattr(tr, "line", None), "color", None), getattr(getattr(tr, "marker", None), "color", None)):
                if isinstance(c, str):
                    colours.add(c)
                elif c is not None:
                    colours.update(x for x in c if isinstance(x, str))
        assert len(colours - grey) <= 2, (name, colours)


def test_facts_has_the_numbers_the_chapters_quote():
    f = wb.facts(_data())
    assert f["remote_hn"][2019] == 30.0 and f["remote_hn"][2022] == 80.0
    assert {"F", "A2", "B1"} <= set(f) and "Atlanta" in f["metros_withheld"]
