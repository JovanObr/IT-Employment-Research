"""Notebook 08 (Slovenian story): structure checks that need no data. It is executed on real data by its author."""
import ast
import json
from pathlib import Path

NB = Path(__file__).resolve().parent.parent / "notebooks" / "08_zgodba_SL.ipynb"
KNOWN = {"1_casovnica", "1_koledar", "2_datumi", "2_zamiki", "2_rast", "3_velikost", "3_podjetja", "3_modeli", "3_skupine",
         "4_teme_povrsina", "4_teme_mali_grafi", "4_teme_toplotna", "4_daljava_ui", "5_zemljevid", "5_regije",
         "6_pot", "6_porazdelitev", "6_skupine"}


def cells():
    return json.loads(NB.read_text(encoding="utf-8"))["cells"]


def test_every_code_cell_is_valid_python():
    for c in cells():
        if c["cell_type"] == "code":
            ast.parse("".join(c["source"]))


def test_chapters_and_reading_guide_are_present_in_slovenian():
    md = "\n".join("".join(c["source"]) for c in cells() if c["cell_type"] == "markdown")
    for heading in ("## 1. Kdaj", "## 2. Zakaj", "## 3. Katera", "## 4. Kaj iščejo", "## 5. Kje", "## 6. Kaj naredi borza", "## Povzetek", "## Viri"):
        assert heading in md, heading
    for part in ("Kaj vidimo?", "Zakaj smo to naredili?", "Kaj to pomeni?", "Česa ne vemo?"):
        assert part in md


def test_every_figure_name_used_exists_and_chapters_1_to_3_and_6_are_all_shown():
    import re
    code = "\n".join("".join(c["source"]) for c in cells() if c["cell_type"] == "code")
    used = set(re.findall(r'show\("([0-9a-z_]+)"\)', code)) | set(re.findall(r'"([456]_[a-z_]+)"', code))
    assert used <= KNOWN, used - KNOWN
    assert {"1_casovnica", "1_koledar", "2_datumi", "2_zamiki", "2_rast", "3_velikost", "3_podjetja", "3_modeli", "3_skupine"} <= used


def test_setup_uses_the_shared_pipeline_and_a_renderer_that_survives_html_export():
    setup = next("".join(c["source"]) for c in cells() if c["cell_type"] == "code" and "prepare_story_data" in "".join(c["source"]))
    assert "viz.prepare_story_data()" in setup and "build_explanations" in setup and "notebook_connected" in setup
    assert "explanation_markdown" in setup and "build_chapter_4_5" in setup


def test_summary_cell_uses_the_computed_summary():
    code = "\n".join("".join(c["source"]) for c in cells() if c["cell_type"] == "code")
    assert "tx.build_summary(story)" in code and "zakljucki" in code and "odprto" in code
