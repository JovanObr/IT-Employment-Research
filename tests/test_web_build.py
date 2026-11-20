"""Presentation website: front matter, screens, figures, glossary, time budget and the self-contained build (temporary web folders)."""
import json
from pathlib import Path

import plotly.graph_objects as go
import pytest

from analysis import web_build as wb
from analysis import web_theme

SOURCES = {"1_x": ["f.csv"], "2_y": ["f.csv"]}


def site(tmp_path, chapters, glossary_a="obrestna mera: Cena denarja.\n", glossary_b="", figures=("1_x",)):
    web = tmp_path / "web"
    for name, text in chapters.items():
        (web / "chapters" / name).mkdir(parents=True)
        (web / "chapters" / name / "chapter.md").write_text(text, encoding="utf-8")
    (web / "glossary").mkdir(parents=True)
    (web / "glossary" / "a.yml").write_text(glossary_a, encoding="utf-8")
    (web / "glossary" / "b.yml").write_text(glossary_b, encoding="utf-8")
    (web / "figures" / "a").mkdir(parents=True)
    for f in figures:
        (web / "figures" / "a" / f"{f}.json").write_text(go.Figure(go.Bar(x=[1, 2], y=[3, 4])).to_json(), encoding="utf-8")
    (web / "background").mkdir()
    (web / "background" / "a.md").write_text("## Ozadje\n\n**Vprašanje?** Odgovor.", encoding="utf-8")
    (web / "assets").mkdir()
    for f in ("theme.css", "app.js"):
        (web / "assets" / f).write_text((wb.WEB / "assets" / f).read_text(encoding="utf-8"), encoding="utf-8")
    (web / "intro.md").write_text("---\ntitle: Naslov\nsubtitle: Pod\nauthors: A in B\n---\nUvod.", encoding="utf-8")
    return web


def ch(minutes=2, owner="A", body="Besedilo o [[obrestna mera|obrestni meri]].\n\n{{figure: 1_x}}\n\n{{govor: Rečem to.}}\n\n---\n\nDrugi zaslon."):
    return f"---\ntitle: T\nquestion: Q: z dvopičjem\nminutes: {minutes}\nowner: {owner}\n---\n{body}"


def test_front_matter_and_screens():
    meta, body = wb.split_front_matter(ch())
    assert meta == {"title": "T", "question": "Q: z dvopičjem", "minutes": "2", "owner": "A"}
    assert len(wb.split_screens(body)) == 2


def test_a_correct_site_has_no_errors(tmp_path):
    r = wb.check(site(tmp_path, {"01_a": ch(), "02_b": ch(3)}), sources=SOURCES)
    assert r.errors == [] and r.minutes == 5


def test_time_budget_warns_above_15_and_fails_above_20(tmp_path):
    w = wb.check(site(tmp_path / "w", {"01_a": ch(8), "02_b": ch(8)}), sources=SOURCES)
    assert w.errors == [] and any("16" in x for x in w.warnings)
    e = wb.check(site(tmp_path / "e", {"01_a": ch(11), "02_b": ch(10)}), sources=SOURCES)
    assert any("time budget" in x for x in e.errors)


def test_missing_front_matter_bad_owner_and_two_figures_on_one_screen(tmp_path):
    bad = "---\ntitle: T\nminutes: 1\nowner: C\n---\n{{figure: 1_x}}\n\n{{figure: 2_y}}"
    r = wb.check(site(tmp_path, {"01_a": bad}, figures=("1_x", "2_y")), sources=SOURCES)
    text = " ".join(r.errors)
    assert "question" in text and "owner must be A or B" in text and "more than one figure" in text


def test_unknown_term_figure_without_sources_and_duplicate_glossary_term(tmp_path):
    body = "O [[neznan izraz]].\n\n{{figure: 9_z}}"
    r = wb.check(site(tmp_path, {"01_a": ch(body=body)}, glossary_b="obrestna mera: Še enkrat.\n"), sources=SOURCES)
    text = " ".join(r.errors)
    assert "neznan izraz" in text and "9_z" in text and "both a.yml and b.yml" in text


def test_missing_figure_json_is_a_warning_unless_strict(tmp_path):
    web = site(tmp_path, {"01_a": ch(body="{{figure: 2_y}}")})
    assert wb.check(web, sources=SOURCES).errors == [] and wb.check(web, sources=SOURCES).warnings
    assert any("2_y" in e for e in wb.check(web, sources=SOURCES, strict=True).errors)


def test_build_is_self_contained(tmp_path):
    web = site(tmp_path, {"01_a": ch(), "02_b": ch(body="{{figure: 2_y}}")})
    out = wb.build(web, out=tmp_path / "dist" / "index.html", sources_md=lambda n: f"**Viri podatkov:** vir za {n}.")
    doc = out.read_text(encoding="utf-8")
    import re
    tags = re.sub(r"<script[^>]*>.*?</script>", "", doc, flags=re.S)                         # the page without script bodies
    assert "<script src=" not in tags and "<link" not in tags and "src=\"http" not in tags   # nothing loaded from outside
    assert len(re.findall(r"<script", doc)) == len(re.findall(r"</script>", doc))             # no script ends early
    assert 'id="fig-1_x"' in doc and "Viri podatkov:" in doc and "vir za 1_x" in doc
    assert 'class="term"' in doc and "Cena denarja." in doc and "obrestni meri" in doc
    assert 'class="note"' in doc and "Rečem to." in doc and "{{" not in tags and "[[" not in tags    # all markup was converted
    assert "še manjka" in doc and "2_y" in doc                                                  # missing figure shown as a box
    assert "Za radovedne" in doc and "Odgovor." in doc and "Slovarček" in doc
    assert 'lang="sl"' in doc and "Naslov" in doc


def test_inline_text_cannot_end_a_script_early():
    assert wb._inline('{"t": "</SCRIPT><b>"}') == '{"t": "<\\/SCRIPT><b>"}'
    assert wb._inline("x = /<\\/div>/; a</b") == "x = /<\\/div>/; a</b"                         # other code untouched
    assert json.loads(wb._inline(json.dumps({"t": "a</script>"}))) == {"t": "a</script>"}


def test_web_theme_lets_the_page_decide_the_height():
    f = web_theme.apply(go.Figure(go.Scatter(x=[1], y=[1]), layout=dict(height=900, width=700, title="Naslov")))
    assert f.layout.height is None and f.layout.width is None and f.layout.autosize
    assert f.layout.title.x == 0 and f.layout.separators == ",."


def test_the_real_site_passes_its_checks():
    r = wb.check()
    assert r.errors == [], r.errors
    assert r.minutes <= wb.MAX_MINUTES


def test_big_number_and_takeaway_render_and_unknown_elements_fail(tmp_path):
    body = ("{{stevilka: 178.725 | ljudi so podjetja v ZDA napovedala odpustiti leta 2023}}\n\n"
            "{{poudarek: Val se je začel **po** zvišanju [[obrestna mera|obrestne mere]].}}\n\n---\n\n{{stevlka: 1 | tipkarska napaka}}")
    web = site(tmp_path, {"01_a": ch(body=body)})
    r = wb.check(web, sources=SOURCES)
    assert any("unknown element" in e and "stevlka" in e for e in r.errors)
    web2 = site(tmp_path / "ok", {"01_a": ch(body=body.split("\n\n---")[0])})
    assert wb.check(web2, sources=SOURCES).errors == []
    doc = wb.build(web2, out=tmp_path / "o.html", sources_md=lambda n: "").read_text(encoding="utf-8")
    assert '<span class="value">178.725</span>' in doc and 'class="takeaway"' in doc and "<strong>po</strong>" in doc and 'class="term"' in doc


def test_theme_helpers():
    import numpy as np
    f = go.Figure([go.Scatter(x=[1, 2, 3], y=[1, 2, 3], name="ZDA", line=dict(color="#4C78A8")),
                   go.Scatter(x=[1, 2, 3], y=[3, 2, None], name="EU", line=dict(color="#F58518"))])
    web_theme.direct_labels(f)
    texts = [a.text for a in f.layout.annotations]
    assert "<b>ZDA</b>" in texts and "<b>EU</b>" in texts and f.layout.showlegend is False
    assert [a.y for a in f.layout.annotations] == [3, 2]                      # last non-missing point
    web_theme.highlight(f, "ZDA")
    assert f.data[0].line.color == "#4C78A8" and f.data[1].line.color == web_theme.ROLE["muted"]
    web_theme.title(f, "Zaključek", "kaj graf kaže")
    assert f.layout.title.text.startswith("Zaključek<br>") and "kaj graf kaže" in f.layout.title.text
    web_theme.callout(f, 2, 2, "tukaj")
    assert f.layout.annotations[-1].showarrow and f.layout.annotations[-1].text == "tukaj"
