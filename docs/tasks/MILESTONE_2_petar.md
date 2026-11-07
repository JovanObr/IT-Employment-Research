# Milestone 2 (due Thursday 2026-11-12, aim for Tuesday 11-10): compare our findings with published studies (Stream B agent)

## Context
Milestone 2 asks us to (a) set our findings beside existing case studies and (b) say, under **every** graph, where its data comes
from (original source and exact CSV files). Stream A has done the case-study search (Claude Docs doc *"Case studies vs. our findings"*,
John has the link; the studies relevant to you are copied below so you do not need it), the source lines (`analysis/data_sources.py`),
and four like-for-like tests on companies, stocks and Challenger counts (`analysis/comparisons.py`). Stream A will assemble
**notebook 09** (`notebooks/09_primerjava_SL.ipynb`, Slovenian, casual audience, same style as notebook 08) with a verdict table and one
figure per comparison.

**Your part: the comparisons for Hacker News (chapter 4) and geography (chapter 5)**, delivered like last time as pure figure functions,
explanations and small committed aggregates, behind one entry point. You do not write the notebook.

## Rules (same as before)
- Branch `milestone2/compare-b`. Pull `main` first; read `AGENTS.md`, `docs/STATUS.md`, `analysis/viz_theme.py`, `analysis/data_sources.py`,
  `analysis/viz_text_geo.py` (your own chapter 4-5 code) and this file.
- **Files you own:** `analysis/compare_text_geo.py` (new), `tests/test_compare_text_geo.py` (new), additive changes to `analysis/hn_text.py`,
  `analysis/geo.py`, `collectors/hn.py` (D1 only, see there) and any new collector `collectors/<name>.py`, plus **your own rows** in
  `FIGURE_SOURCES` / `DERIVED` / `SOURCE_LABELS` of `analysis/data_sources.py` (add rows; do not change Stream A's rows or the functions).
  Edit only your section of `docs/STATUS.md`.
- **Do not edit** `analysis/viz_theme.py`, `analysis/viz.py`, `analysis/story_text.py`, `analysis/comparisons.py`, `collect.py`. Requests go under
  *Requests between streams* in `docs/STATUS.md` as "B asks A: ...".
- Tests: synthetic data only, no network (`tests/conftest.py` sets a temporary `DATA_DIR`). `pytest -q` and `python -m compileall -q .` green before you push.
- Never commit raw post text, API keys, `data/raw/` or `data/manual/`. Only aggregates. Statista files (faculty licence) are never committed.

## The data-source rule (applies to every figure you make, from now on)
Every figure name you return must have a row in `analysis/data_sources.py` `FIGURE_SOURCES`, listing the CSV files the figure reads. A derived
file needs a `DERIVED` row (`"data/processed/x.csv": ("python -m analysis.<module> <cmd>", [input files])`), and every original file must be in
`data/manifest.json` (a new collector puts it there via `record(...)`) with a Slovenian `SOURCE_LABELS` entry. `tests/test_data_sources.py`
checks this for `viz.build_figures` and `viz_text_geo.build_figures`; **extend that test (one line) so it also reads the figure names of your
`build_figures` in `compare_text_geo.py`.** `python -m analysis.data_sources` prints every line and must end with `OK`.
A published number you type in from a study (not from a CSV) goes in the explanation with the study named; it is not a data file.

**Also check Stream A's rows for your chapters 4-5** (already added by Stream A): `4_teme_*` read `hn_topics_monthly.csv` (built from posts and text),
`4_daljava_ui` reads `hn_flags_monthly.csv` and `hn_change_points.csv`, `5_*` read `metro_map_data.csv`, listed as QCEW areas + Census Gazetteer only
(the map uses job and establishment growth, not FHFA or ACS). Fix them if any of that is wrong; say so in STATUS.

## Deliverables

### D1 A usable junior flag (needed to compare with Brynjolfsson, Chandar & Chen 2025)
*Study:* Brynjolfsson, Chandar & Chen (2025), "Canaries in the Coal Mine?", Stanford Digital Economy Lab: from ADP payroll data, workers aged 22-25 in
AI-exposed jobs lost about 16 % of employment relative to others since late 2022; young software developers are about 20 % below their late-2022 peak.
(https://digitaleconomy.stanford.edu/publications/canaries-in-the-coal-mine/)
*Problem:* our keyword flag (`collectors/hn.py`, regex `junior|interns?|internships?|entry[- ]level|new grad|graduates?`) has a recall of about 5 % in
your hand validation, so it cannot measure junior hiring.
1. Read the posts your validation labelled junior = 1 that the flag missed; write down what words they use (for example "early career", "all levels",
   "0-2 years", "Engineer I", "bootcamp", "college", "mentorship", "no experience required"; check, do not assume).
2. Write `junior_v2` as a new rule in `analysis/hn_text.py` (do not change the old `junior` flag, other code reads it), including a negation
   check like `NEGATED_JUNIOR`. Keep it a transparent keyword/regex rule; no language model.
3. Validate on a **fresh** random sample (the old sample was used to design the rule, so it would flatter it): `make_validation_sample` with a new seed,
   at least 200 posts, oversampling posts that mention a seniority word so there are 20+ true juniors; John or you label them by hand.
   Report precision and recall with the existing Wilson intervals (`validate_flags`).
4. **Decision rule, written down before you look at trends:** use `junior_v2` in a figure only if precision >= 0.8 and recall >= 0.5 (lower CI bound
   of recall >= 0.35). Otherwise report the validation numbers and say in STATUS that junior hiring cannot be compared; that is an acceptable result.
5. If it passes: add `junior_v2` to the committed flags (`hn_flags_monthly.csv` via `python -m analysis.hn_text flags`; keep `junior` out).

### D2 Comparison figures (in `analysis/compare_text_geo.py`), names prefixed `9b_`
Each comes with `explain_<name>(data) -> dict` with the four Slovenian parts `kaj`, `zakaj`, `pomen`, `omejitve`, exactly as in chapter 4-5
(numbers computed from the data; wording adapts when the data flips; `omejitve` never empty). In `pomen`, put **their number beside ours**
and name the study.

1. `9b_daljava_primerjava` - remote work. *Study:* Hansen, Lambert, Bloom, Davis, Muvdi, Sadun & Taska (2026), "Remote Work Across Jobs, Companies and
   Space", Dallas Fed WP 2629 (https://doi.org/10.24149/wp2629): the US share of postings offering remote work rose more than threefold 2019-2026.
   *Ours:* HN remote share 32 % (2019), peak about 84 % (August 2022), 54 % now. Figure: our monthly remote share indexed to 2019 = 1 next to a
   reference band or marker for their "more than 3x" (and, if you find an open, citable US remote-postings series, e.g. from Indeed Hiring Lab under
   CC BY, a second line from it, added through a new collector). Question to answer in `pomen`: same direction? same timing of the peak? why is HN's level higher?
2. `9b_ui_primerjava` - AI. *Studies:* Bernard (2025), Indeed Hiring Lab, "The US Tech Hiring Freeze Continues"
   (https://hiringlab.indeed.com/2025/07/30/the-us-tech-hiring-freeze-continues/): ML-engineer postings +59 %, software-engineer postings -49 % (early 2020
   to early 2025); Acemoglu, Autor, Hazell & Restrepo (2022, JOLE). *Ours:* HN AI/ML share 10 % to 57 %. Figure: our AI share and our total HN post
   count on one time axis (two y axes or indexed), so "AI share up while all posts down" is visible.
3. `9b_mladi` - junior hiring, **only if D1 passed its decision rule**: junior_v2 share over time with the late-2022 line, next to the Stanford result in text.
4. `9b_regije_primerjava` - geography. *Studies:* Bernard (2025) above: tech postings fell least in Texas and the Southeast (Austin -28 %) and most in
   hubs (Boston -51 %, also Seattle, San Francisco, Minneapolis); Muro & You (2022), Brookings
   (https://www.brookings.edu/articles/superstars-rising-stars-and-the-rest-pandemic-trends-and-shifts-in-the-geography-of-tech/): Sun Belt "rising stars".
   **Copy their numbers from the pages and check them; do not use the ones in this file without checking.** *Ours:* `metro_map_data.csv`.
   Figure: for the metros they name, our IT job growth 2019-2024 next to their postings change (a dot plot: one row per metro, two markers), with
   "podatek je skrit" where our number is withheld. Say clearly that postings and jobs are different measures.

### D3 Entry point (exact signature)
`analysis/compare_text_geo.py` exposes `build_comparisons_b() -> dict[str, tuple[Figure, dict, dict]]`: for every figure,
`(figure, explanation, verdict)` where `verdict` is one row for notebook 09's table:
`{"tema": str, "studija": str, "njihov_rezultat": str, "nas_rezultat": str, "ocena": "se ujema" | "delno" | "se razlikuje" | "ni primerljivo"}`
(Slovenian, short; `nas_rezultat` computed from the data). It loads committed aggregates through loaders; raises a clear `FileNotFoundError` if one is
missing. Also `build_figures(...)` returning `{name: Figure}` (the data-source test reads its names).

### D4 Tests and preview
`tests/test_compare_text_geo.py`: names and tuple shape of `build_comparisons_b()`; every explanation has four non-empty parts without 'nan'/'None';
numbers in `pomen` change with the input; wording flips when the data flips; verdict has the five keys and a valid `ocena`; figure smoke tests
(no exception on NaN, inputs not modified); for D1, tests of `junior_v2` on hand-written positive and negative sentences, including negations.
`python -m analysis.compare_text_geo preview` writes `reports/figures_sl/preview_9b_<name>.html`.

## Schedule
| When | What |
|---|---|
| Sat 7 - Sun 8 Nov | D1 steps 1-3 (rule + fresh sample for labelling); D2.1 and D2.2 with tests; push |
| Mon 9 Nov | Labels in, D1 decision; D2.3 if it passed; D2.4; data-source rows; push |
| Tue 10 Nov, noon | **Open the pull request**, STATUS updated (what exists, the junior decision with its numbers) |
| Tue 10 - Wed 11 | Review fixes only |

## Done means
`pytest -q` green; `python -m analysis.data_sources` ends with `OK` and lists your `9b_*` figures; `build_comparisons_b()` works on the committed
aggregates; the junior decision is recorded in STATUS with precision and recall; your STATUS line says what exists and what does not.

## Prompt to paste into the agent
"You are the Stream B agent on this repository. Read AGENTS.md, docs/STATUS.md, analysis/viz_theme.py, analysis/data_sources.py,
analysis/viz_text_geo.py and docs/tasks/MILESTONE_2_petar.md. Work on branch milestone2/compare-b. Do D1 steps 1-3 first, then the D2 figures with
their Slovenian explanations and verdict rows, then the data-source rows and the test extension. Apply the D1 decision rule as written; do not change
it after seeing the trend. Copy published numbers from the study pages and check them. Do not edit files owned by Stream A except adding your own rows
in analysis/data_sources.py. Test with synthetic data only; never commit raw text, keys, data/raw or data/manual. Open the pull request on Tuesday
10 November at noon."
