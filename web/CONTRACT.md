# Website contract (final presentation)

How the presentation website is built, and the rules both streams follow so each can work alone. Stream A owns this file;
changes are announced in `docs/STATUS.md`. The site is in **Slovenian**, for a **general audience**, **15-20 minutes** in total.

## Commands
```
python -m analysis.web_figures_a      # Stream A: computes its figures from local data -> web/figures/a/*.json (slow, needs data)
python -m analysis.web_figures_b      # Stream B: the same for its figures            -> web/figures/b/*.json
python -m analysis.web_build          # assembles everything -> web/dist/index.html (fast, needs no data, only the JSON files)
python -m analysis.web_build --check  # checks only: time budget, figures, glossary terms, sources (also run by pytest)
python -m analysis.web_build --sample # also writes the style guide web/build/vzorec.html (for authors)
```
Open `web/dist/index.html` by double-clicking: it is one self-contained file (styles, scripts, plotly.js and all figures inside), so it
works offline on any laptop. GitHub Pages serves the same file (`.github/workflows/pages.yml` deploys `web/dist/` on every push to `main`;
once, in the repository settings: Pages -> Source: GitHub Actions). **Commit `web/dist/` after building**, because the figures need local
data that GitHub does not have.

## Folder layout and ownership
| Path | What | Owner |
|---|---|---|
| `web/intro.md` | Title screen and the opening question | A |
| `web/chapters/NN_slug/chapter.md` | One chapter (format below) | 01-04, 07, 08: A; **05, 06: B** |
| `web/figures/a/`, `web/figures/b/` | Exported figure JSON (generated, committed) | A / B |
| `analysis/web_figures_a.py`, `analysis/web_figures_b.py` | Figure builders | A / B |
| `web/glossary/a.yml`, `web/glossary/b.yml` | Glossary terms | A / B |
| `web/background/a.md`, `web/background/b.md` | Background page "Za radovedne" (questions and answers, methods) | A / B |
| `web/assets/`, `analysis/web_theme.py`, `analysis/web_build.py`, `web/vzorec.md`, this file | Theme, scripts, build, style guide | A |
New chapters later: a new folder with the next free number (e.g. `09_...`), owner in its front matter. Chapters are shown in folder-name order.

## Chapter format (`chapter.md`)
```
---
title: Kje?
question: Jug ZDA proti velikim središčem, vzhodna proti zahodni obali, Evropa in Slovenija
minutes: 2.5
owner: B
---
Prvi zaslon: en sam poudarek, kratko besedilo (2-4 stavki).

{{figure: 6w_regije}}

{{govor: Kar povem na glas ob tem zaslonu. Občinstvo tega ne vidi; prikaže se s tipko N.}}

---

Drugi zaslon ...
```
- **Front matter** (between the first two `---` lines), all required: `title` (short), `question` (the question the chapter answers, one
  line), `minutes` (time budget, number), `owner` (`A` or `B`).
- **Screens:** a line with only `---` starts a new screen. One idea per screen; at most one figure per screen; 2-4 short sentences.
- **Figures:** `{{figure: name}}` on its own line. The name must exist in `web/figures/a|b/` and have a row in
  `analysis/data_sources.py` `FIGURE_SOURCES`; the build adds the "Viri podatkov" line under it automatically.
- **Speaker notes:** `{{govor: ...}}` anywhere on a screen; hidden, shown with the N key. Write what you will say, so the timing can be rehearsed.
- **Glossary terms:** `[[izraz]]` or `[[izraz|prikazana oblika]]` (e.g. `[[nenavadni donos|nenavadnega donosa]]`). The term must exist in a
  glossary file; the page shows its definition on hover or tap.
- Ordinary Markdown otherwise (bold, lists, links). No raw HTML.

## Figures
- Each stream has one builder module with `build_web_figures() -> dict[str, plotly.graph_objects.Figure]` (keys written as literal strings
  in that function) and a `main()` that writes every figure to `web/figures/<a|b>/<name>.json` with `fig.to_json()`.
- **Names:** chapter number, then `w`, then a short Slovenian slug: `5w_daljava`, `6w_regije`. Reusing a notebook figure unchanged? Its existing
  name is fine (e.g. `1_ljudje`). Every name needs a `FIGURE_SOURCES` row (`tests/test_data_sources.py` reads the names from both builders).
- **Style:** do not style for the web yourself. Build the figure with `analysis.viz_theme` as in the notebooks; the build applies the web theme
  (`analysis.web_theme.apply`) to every figure, so a later theme change never touches chapter content or figure code.
- **For everyone:** the title states the conclusion ("Odpuščanja so se začela po zvišanju obrestne mere"), not the content ("Število odpuščanj
  po tednih"). Label lines and points directly on the chart where possible; numbers with a decimal comma (`sl_num`, `sl_pct`); no jargon
  in titles or axes (or a glossary term in the text next to it).
- Only aggregates go into the JSON (it is published). Never per-event Yahoo prices or raw Hacker News text.

## Theme (look and feel)
See it all on one page: `python -m analysis.web_build --sample` writes `web/build/vzorec.html` (the style guide; not published, not committed).
- **Colour roles** (`analysis.web_theme.ROLE`), one meaning per colour on every screen: `main` blue = our data, the thing the screen is about;
  `contrast` orange = the one thing it is compared with; `loss` red = layoffs, declines; `context` grey and `muted` light grey = everything else.
  **Never let red vs. green be the only difference** (colour-blind viewers); blue vs. orange is safe.
- **Chart helpers** (`analysis.web_theme`, use them in your figure builder; they only add to a normal `viz_theme` figure):
  `title(fig, "Sklep", "kaj graf kaže")` conclusion-first title with a small grey subtitle; `direct_labels(fig)` names each line at its end and hides the
  legend; `highlight(fig, "ime serije")` keeps one series in colour and greys the rest; `callout(fig, x, y, "besedilo")` an arrow note at the point the
  speaker talks about.
- **One message per chart:** at most two coloured series; everything else grey. If a notebook figure has several panels, make a simpler web version.
- Text: system fonts (works offline); numbers with a decimal comma; no unexplained abbreviations.

## Components for chapter text
- `{{stevilka: 178.725 | ljudi so podjetja v ZDA napovedala odpustiti leta 2023}}` on its own line: a big number with a one-line label. Use it when the
  number itself is the message; the same number must also appear in a figure or in text that names its source.
- `{{poudarek: Val se je začel **po** zvišanju obrestne mere.}}` on its own line: the chapter's key takeaway (normally one per chapter, on its last screen).
  Markdown and glossary terms work inside.
- Any other `{{...: }}` element is an error in `--check` (catches typos such as `{{stevlka: ...}}`).

## Glossary (`web/glossary/a.yml`, `b.yml`)
One term per line, `izraz: razlaga v enem ali dveh stavkih.` Lowercase term, no colon inside the term. The same term must not be in both files.

## Background page (`web/background/a.md`, `b.md`)
Markdown, shown at the end under "Za radovedne" (not part of the 15-20 minutes). Sections with `##`; for each hypothesis a short summary with
a link to its dossier on GitHub (`docs/methods/<id>.md`), and the likely questions with short answers (`**Vprašanje?** Odgovor.`).

## Checks the build enforces (`--check`, and in pytest)
- Total `minutes` of all chapters <= 20 (error); above 15 prints a warning (the 5-minute reserve for later milestones is being used).
- Every chapter has the four front-matter fields, at least one screen, and no screen with more than one figure.
- Every `{{figure: ...}}` exists as JSON and has a `FIGURE_SOURCES` row; every `[[term]]` is in a glossary file; no glossary term in both files.
A missing figure JSON is only a warning while building (a grey box says which figure is missing), so a chapter can be written before its
figures exist; `--check --strict` (run before the final freeze) makes it an error.

## Presenting
Arrow keys, Page Down/Up or Space move one screen; Home/End jump to the start or end; N shows the speaker notes; T shows a timer with the
planned minutes of the current chapter. The table of contents (top left) jumps to any chapter. Everything also works by scrolling.
