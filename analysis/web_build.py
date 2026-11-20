"""Builds the presentation website (web/) into one self-contained file, web/dist/index.html. Rules: web/CONTRACT.md.

    python -m analysis.web_build            # build (missing figure JSON = warning, grey box on the page)
    python -m analysis.web_build --check    # checks only
    python -m analysis.web_build --check --strict   # missing figures are errors too (before the final freeze)
"""
from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MAX_MINUTES, CORE_MINUTES = 20.0, 15.0
REQUIRED = ("title", "question", "minutes", "owner")
FIG_RE = re.compile(r"^\{\{\s*figure:\s*([^}\s]+)\s*\}\}\s*$", re.M)
NOTE_RE = re.compile(r"\{\{\s*govor:\s*(.*?)\}\}", re.S)
TERM_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


@dataclass
class Chapter:
    folder: str
    meta: dict
    screens: list[str]
    path: Path


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    minutes: float = 0.0


# ---------------------------------------------------------------------------------------- reading
def split_front_matter(text: str) -> tuple[dict, str]:
    """`---` / key: value lines / `---` at the top of a file -> (dict, rest). Values stay strings."""
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text
    meta = {}
    for line in lines[1:end]:
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, "\n".join(lines[end + 1:])


def split_screens(body: str) -> list[str]:
    parts = re.split(r"^\s*---\s*$", body, flags=re.M)
    return [p.strip() for p in parts if p.strip()]


def load_chapters(web: Path = WEB) -> list[Chapter]:
    out = []
    for d in sorted(p for p in (web / "chapters").iterdir() if p.is_dir() and re.match(r"^\d\d_", p.name)) if (web / "chapters").exists() else []:
        f = d / "chapter.md"
        if not f.exists():
            continue
        meta, body = split_front_matter(f.read_text(encoding="utf-8"))
        out.append(Chapter(d.name, meta, split_screens(body), f))
    return out


def load_glossary(web: Path = WEB) -> tuple[dict[str, str], list[str]]:
    """Terms from web/glossary/*.yml (one `term: definition` per line). Returns (terms, duplicate-term errors)."""
    terms, owner, errors = {}, {}, []
    for f in sorted((web / "glossary").glob("*.yml")) if (web / "glossary").exists() else []:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if ":" not in line:
                errors.append(f"{f.name}:{n}: not 'term: definition'")
                continue
            k, v = line.split(":", 1)
            k = k.strip().lower()
            if k in terms:
                errors.append(f"glossary term '{k}' is in both {owner[k]} and {f.name}")
            terms[k], owner[k] = v.strip(), f.name
    return terms, errors


def load_figures(web: Path = WEB) -> dict[str, dict]:
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted((web / "figures").glob("*/*.json"))} if (web / "figures").exists() else {}


# ---------------------------------------------------------------------------------------- checks
def check(web: Path = WEB, sources: dict | None = None, strict: bool = False) -> Report:
    if sources is None:
        from analysis.data_sources import FIGURE_SOURCES as sources
    r = Report()
    chapters = load_chapters(web)
    terms, gerr = load_glossary(web)
    r.errors += gerr
    figs = load_figures(web)
    if not chapters:
        r.errors.append("no chapters in web/chapters/")
    for c in chapters:
        missing = [k for k in REQUIRED if not c.meta.get(k)]
        if missing:
            r.errors.append(f"{c.folder}: front matter is missing {missing}")
        try:
            r.minutes += float(str(c.meta.get("minutes", "0")).replace(",", "."))
        except ValueError:
            r.errors.append(f"{c.folder}: minutes is not a number")
        if c.meta.get("owner") and c.meta["owner"] not in ("A", "B"):
            r.errors.append(f"{c.folder}: owner must be A or B")
        if not c.screens:
            r.errors.append(f"{c.folder}: no screens")
        for i, s in enumerate(c.screens, 1):
            names = FIG_RE.findall(s)
            if len(names) > 1:
                r.errors.append(f"{c.folder} screen {i}: more than one figure {names}")
            for n in names:
                if n not in sources:
                    r.errors.append(f"{c.folder}: figure '{n}' has no FIGURE_SOURCES row in analysis/data_sources.py")
                if n not in figs:
                    (r.errors if strict else r.warnings).append(f"{c.folder}: figure '{n}' has no JSON in web/figures/ yet")
            for t, _ in TERM_RE.findall(s):
                if t.strip().lower() not in terms:
                    r.errors.append(f"{c.folder}: glossary term '{t.strip()}' is not in web/glossary/")
    if r.minutes > MAX_MINUTES:
        r.errors.append(f"time budget: {r.minutes:g} minutes > {MAX_MINUTES:g}")
    elif r.minutes > CORE_MINUTES:
        r.warnings.append(f"time budget: {r.minutes:g} minutes (above the {CORE_MINUTES:g}-minute core; reserve left {MAX_MINUTES - r.minutes:g})")
    return r


# ---------------------------------------------------------------------------------------- rendering
def _md(text: str) -> str:
    return markdown.markdown(text, extensions=["extra", "sane_lists"], output_format="html")


def render_text(text: str, terms: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """Markdown with figure lines, speaker notes and glossary terms -> (html, notes, figure names)."""
    notes = [n.strip() for n in NOTE_RE.findall(text)]
    text = NOTE_RE.sub("", text)
    names = FIG_RE.findall(text)
    text = FIG_RE.sub(lambda m: f'\n\n<div class="figure-slot" data-figure="{html.escape(m.group(1))}"></div>\n\n', text)

    def term(m):
        key, shown = m.group(1).strip(), (m.group(2) or m.group(1)).strip()
        d = terms.get(key.lower(), "")
        return f'<span class="term" tabindex="0" data-def="{html.escape(d, quote=True)}">{html.escape(shown)}</span>'

    return _md(TERM_RE.sub(term, text)), notes, names


def _figure_html(name: str, figs: dict, sources_line: str) -> str:
    if name not in figs:
        return f'<div class="figure missing">Graf <code>{html.escape(name)}</code> še manjka.</div>'
    return (f'<figure class="figure"><div class="plot" data-figure="{html.escape(name)}"></div>'
            f'<figcaption class="sources">{_md(sources_line)}</figcaption></figure>')


def data_section() -> str:
    """Every dataset in data/manifest.json, grouped by its original source (from analysis.data_sources)."""
    from analysis.data_sources import SOURCE_LABELS, load_manifest
    m = load_manifest()
    groups: dict[str, list[tuple[str, dict]]] = {}
    for f, rec in m.items():
        groups.setdefault(SOURCE_LABELS.get(f, rec.get("source", f)), []).append((f, rec))
    rows = []
    for label, items in sorted(groups.items()):
        files = "<br>".join(f"<code>{html.escape(f)}</code>" for f, _ in items)
        lic = html.escape(items[0][1].get("licence_or_terms", ""))
        got = html.escape(str(items[0][1].get("retrieved_at_utc", ""))[:10])
        rows.append(f"<tr><td>{html.escape(label)}</td><td>{files}</td><td>{got}</td><td class='small'>{lic}</td></tr>")
    return ("<table class='data-table'><thead><tr><th>Vir</th><th>Datoteke</th><th>Preneseno</th><th>Licenca in pogoji</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _inline(text: str) -> str:
    """Make text safe inside a <script> element. Only "</script" ends a script early in HTML; "<\\/script" means the same inside JS and
    JSON strings, and nothing else in the code is touched (plotly.min.js contains "</" in regular expressions)."""
    return re.sub(r"</(script)", r"<\\/\1", text, flags=re.I)


def build(web: Path = WEB, out: Path | None = None, sources_md=None) -> Path:
    from analysis import web_theme
    if sources_md is None:
        from analysis.data_sources import sources_markdown as sources_md
    out = out or web / "dist" / "index.html"
    chapters, (terms, _), figs = load_chapters(web), load_glossary(web), load_figures(web)
    intro_meta, intro_body = split_front_matter((web / "intro.md").read_text(encoding="utf-8")) if (web / "intro.md").exists() else ({}, "")
    used, toc, body = [], [], []
    body.append(f'<section class="chapter intro" id="uvod"><div class="screen title-screen">'
                f'<h1>{html.escape(intro_meta.get("title", ""))}</h1><p class="subtitle">{html.escape(intro_meta.get("subtitle", ""))}</p>'
                f'{render_text(intro_body, terms)[0]}<p class="authors">{html.escape(intro_meta.get("authors", ""))}</p></div></section>')
    for k, c in enumerate(chapters, 1):
        cid = f"poglavje-{c.folder[:2]}"
        toc.append(f'<li><a href="#{cid}"><span class="num">{k}</span> {html.escape(c.meta.get("title", c.folder))}</a></li>')
        screens = [f'<div class="screen chapter-title" data-chapter="{k}"><p class="kicker">{k}. poglavje</p>'
                   f'<h2>{html.escape(c.meta.get("title", ""))}</h2><p class="question">{html.escape(c.meta.get("question", ""))}</p></div>']
        for s in c.screens:
            h, notes, names = render_text(s, terms)
            for n in names:
                used.append(n)
                h = h.replace(f'<div class="figure-slot" data-figure="{html.escape(n)}"></div>',
                              _figure_html(n, figs, sources_md(n) if n in figs else ""))
            note_html = "".join(f'<aside class="note">{html.escape(n)}</aside>' for n in notes)
            screens.append(f'<div class="screen" data-chapter="{k}">{h}{note_html}</div>')
        body.append(f'<section class="chapter" id="{cid}" data-minutes="{html.escape(c.meta.get("minutes", ""))}" '
                    f'data-title="{html.escape(c.meta.get("title", ""))}">{"".join(screens)}</section>')
    toc += ['<li><a href="#podatki">Podatki</a></li>', '<li><a href="#za-radovedne">Za radovedne</a></li>']
    body.append(f'<section class="chapter appendix" id="podatki"><div class="screen long"><h2>Podatki</h2>'
                f'<p>Vsi viri, ki smo jih uporabili, s točnimi datotekami. Pod vsakim grafom je zapisano, katere od njih uporablja.</p>{data_section()}</div></section>')
    back = "".join(_md(TERM_RE.sub(lambda m: m.group(2) or m.group(1), p.read_text(encoding="utf-8")))
                   for p in sorted((web / "background").glob("*.md"))) if (web / "background").exists() else ""
    gloss = "".join(f"<dt>{html.escape(t)}</dt><dd>{html.escape(d)}</dd>" for t, d in sorted(terms.items()))
    body.append(f'<section class="chapter appendix" id="za-radovedne"><div class="screen long"><h2>Za radovedne</h2>{back}'
                f'<h3>Slovarček</h3><dl class="glossary">{gloss}</dl></div></section>')
    fig_json = "".join(f'<script type="application/json" id="fig-{html.escape(n)}">{_inline(web_theme.apply(figs[n]).to_json())}</script>'
                       for n in dict.fromkeys(used) if n in figs)
    import plotly
    plotly_js = (Path(plotly.__file__).parent / "package_data" / "plotly.min.js").read_text(encoding="utf-8")
    css = (web / "assets" / "theme.css").read_text(encoding="utf-8")
    app = (web / "assets" / "app.js").read_text(encoding="utf-8")
    doc = f"""<!DOCTYPE html>
<html lang="sl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(intro_meta.get("title", "Predstavitev"))}</title><style>{css}</style></head>
<body><div id="progress"></div><nav id="toc" aria-label="Kazalo"><button id="toc-toggle" aria-expanded="false">Kazalo</button><ol>{"".join(toc)}</ol></nav>
<div id="timer" hidden></div><main>{"".join(body)}</main>
{fig_json}<script id="plot-config" type="application/json">{_inline(json.dumps(web_theme.CONFIG))}</script>
<script>{_inline(plotly_js)}</script><script>{_inline(app)}</script></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return out


def main() -> None:
    args = sys.argv[1:]
    r = check(strict="--strict" in args)
    for w in r.warnings:
        print("warning:", w)
    for e in r.errors:
        print("ERROR:", e)
    print(f"chapters: {len(load_chapters())}, time budget {r.minutes:g} of {MAX_MINUTES:g} minutes")
    if r.errors:
        raise SystemExit(1)
    if "--check" not in args:
        print("written", build())


if __name__ == "__main__":
    main()
