"""Every figure says where its data comes from ("Viri podatkov"), and every file it names is real: either recorded in the
committed data/manifest.json or a derived file whose inputs are. No data files are read, only the manifest."""
import ast
import inspect
import json
import re
from pathlib import Path

import pytest

from analysis import data_sources as ds

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "notebooks" / "08_zgodba_SL.ipynb"


def figure_names_in(module) -> set[str]:
    """Figure names returned by a module's build_figures (read from the source, so no data is needed)."""
    return set(re.findall(r'"([1-9][a-z]?_[a-z_]+)":', inspect.getsource(module.build_figures)))


def test_committed_manifest_covers_every_figure():
    assert ds.problems() == []


def test_every_figure_the_story_can_show_has_sources():
    import importlib
    from analysis import compare_viz, viz, viz_text_geo
    names = figure_names_in(viz) | figure_names_in(viz_text_geo) | figure_names_in(compare_viz)
    try:                                                          # Stream B's comparisons, once they exist
        names |= figure_names_in(importlib.import_module("analysis.compare_text_geo"))
    except ModuleNotFoundError:
        pass
    assert len(names) >= 24
    assert names <= set(ds.FIGURE_SOURCES), names - set(ds.FIGURE_SOURCES)
    assert set(ds.FIGURE_SOURCES) <= names, set(ds.FIGURE_SOURCES) - names          # no stale entries either


def test_every_derived_file_has_a_builder_that_exists():
    for f, (cmd, _) in ds.DERIVED.items():
        for target in re.findall(r"python (?:-m )?([\w.]+)", cmd):
            path = ROOT / (target if target.endswith(".py") else target.replace(".", "/") + ".py")
            assert path.exists(), f"{f}: {cmd} -> {path} not found"


def test_line_names_original_source_exact_files_and_intermediate():
    text = ds.sources_markdown("3_velikost")
    assert text.startswith("**Viri podatkov:**")
    assert "SEC EDGAR" in text and "Layoffs.fyi" in text
    for f in ds.DERIVED["data/processed/company_panel.csv"][1]:
        assert f"`{f}`" in text
    assert "`data/processed/company_panel.csv`" in text and "python -m analysis.company_panel" in text


def test_files_from_the_same_source_are_grouped_once():
    text = ds.sources_markdown("6_skupine")
    assert text.count("SEC EDGAR") == 1
    assert "`data/raw/sec_company_matches.csv`, `data/raw/sec_financials_quarterly.csv`" in text
    assert "Graf bere" not in text                                                   # reads only original files


def test_unknown_figure_raises():
    with pytest.raises(KeyError, match="FIGURE_SOURCES"):
        ds.sources_markdown("9_nov_graf")


def test_windows_paths_in_manifest_are_normalised():
    assert ds.norm("data\\raw\\x.csv") == "data/raw/x.csv" == ds.norm("./data/raw/x.csv")
    m = ds.load_manifest()
    assert "data/raw/fred_series.csv" in m and all("\\" not in k for k in m)


def test_problems_catches_a_file_that_is_not_in_the_manifest():
    manifest = {"data/raw/a.csv": {}}
    labels = {"data/raw/a.csv": "vir A"}
    derived = {"data/processed/d.csv": ("python x.py", ["data/raw/a.csv", "data/raw/missing.csv"])}
    figs = {"ok": ["data/raw/a.csv"], "bad": ["data/processed/d.csv"], "empty": []}
    issues = ds.problems(manifest, figs, derived, labels)
    assert any("bad" in i and "missing.csv" in i for i in issues)
    assert any("empty" in i for i in issues)
    assert not any(i.startswith("ok:") for i in issues)


def test_problems_catches_a_missing_label_and_a_cycle():
    issues = ds.problems({"data/raw/a.csv": {}}, {"f": ["data/raw/a.csv"]}, {}, {})
    assert issues == ["f: data/raw/a.csv has no entry in SOURCE_LABELS"]
    with pytest.raises(ValueError, match="cycle"):
        ds.originals(["p/a.csv"], {"p/a.csv": ("", ["p/b.csv"]), "p/b.csv": ("", ["p/a.csv"])})


def test_licensed_or_local_only_data_is_still_named():
    """Yahoo prices are not committed, but a graph built from them must still say so."""
    assert "`data/raw/prices_daily.csv`" in ds.sources_markdown("6_pot")
    assert "Yahoo Finance" in ds.sources_markdown("6_pot")


def test_notebook_shows_the_source_line_under_every_figure():
    cells = json.loads(NB.read_text(encoding="utf-8"))["cells"]
    setup = next("".join(c["source"]) for c in cells if c["cell_type"] == "code" and "def show(" in "".join(c["source"]))
    ast.parse(setup)
    assert "from analysis.data_sources import sources_markdown" in setup
    show = setup[setup.index("def show("):setup.index("def show_chapter(")]
    assert "sources_markdown(name)" in show
