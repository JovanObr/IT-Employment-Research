# Status board (updated 2026-10-30)

Each person edits **only their own section**. Tick a task when its pull request is merged; add one line on what changed and any caveat.

## Stream A: Companies and causes
- [x] A1 SEC financials (more XBRL concepts, quarterly)
- [x] A2 Tech-company universe from SEC SIC codes
- [x] A3 Company-quarter panel + layoff-risk baseline (notebook 03)
- [x] A4 *(stretch)* Macro data (FRED, JOLTS) and causes tests (notebook 04)

Notes:
- A1: `sec_fin` (8 concepts + 3 components; gross profit and SG&A filled from components where not reported, tag `derived_*`). 8+ quarters for 201 of 204 matched companies; ASML, Freightos, Sportradar (foreign filers) have none.
- A2: `sec_universe` (7,065 companies, 1,010 tech by SIC 357x/366x/367x/737x on 2026-10-30; first run 7,044 and 999) also writes `sec_revenue_universe.csv`. 184 of 350 matched layoff companies are tech by SIC (first run: 111 of 204); **model on `is_tech`, not `in_universe`**.
- A3: `python -m analysis.company_panel`, then `python -m analysis.company_models`, then notebook 03. Run order for data: `layoffs`, `sec`, `sec_universe`, `sec_fin`. Panel: 866 tech companies, 14,709 rows, 3.0% base rate; test 2023Q1+ has 294 positives from 90 companies.
- A4: `python collect.py --sources macro`, `python -m analysis.causes`, notebook 04. FRED and JOLTS both work (JOLTS API answered on 2026-10-30; the flat-file fallback exists). Results: tracker event counts (not people laid off, not the official JOLTS layoff rate) line up with Fed funds changes and the NASDAQ; the step up in weekly events came around May 2022 with no further jump at ChatGPT, while the JOLTS information-sector layoff rate hardly moved; fast growers of 2019-2021 appear more in the tracker later, but costs outrunning revenue does not. Associations only; see the limits in the notebook.
- A3 result (rerun 2026-10-30, 350 matched layoff companies): panel 869 tech companies, 14,723 rows, 648 positives (4.4%); test 2023Q1+ has 386 positives from 131 companies. Logistic PR-AUC 0.22 (0.14-0.30) vs base rate 0.054, **but company size alone gives 0.28**; without size about 0.08 (1.5x base rate). Read the limits section of notebook 03 before quoting numbers; rerun the notebook so its saved outputs match the text.

## Stream B: Text, geography and quality
- [x] B1 Tests (pytest) and CI
- [~] B2 Hacker News text analysis (notebook 05): code and notebook done and run end to end on synthetic data; **real run and the 100-post hand labelling still to do locally**
- [~] B3 Geography maps, metro-code stability (notebook 06): code, collector and notebook done; **maps and the code-stability list need a local run** (`collect.py --sources gazetteer`, then notebook 06)
- [ ] B4 *(not started)* *(stretch)* County Business Patterns for the 5 missing metros

Notes:
- 2026-10-27 B1: 120+ new tests (162 in total with the existing ones) (`tests/`), CI workflow `.github/workflows/ci.yml` (compileall + pytest, Python 3.12). `tests/conftest.py` sets `DATA_DIR` to a temp folder before imports, so tests never touch `data/`. Chicago/DC suppression patterns are in `tests/test_metro_panel.py`.
- 2026-10-27 B2: `analysis/hn_text.py` (TF-IDF + NMF, own binary segmentation instead of `ruptures`, before/after 2022-11-30 with pre-trend gap, negation diagnostic, validation sample + precision/recall with Wilson intervals). Decision: threads up to 2022-11 count as "before" (the Nov 2022 thread is posted on 1 Nov). Logistics words (remote, onsite, visa) are removed from the topic vocabulary so topics do not repeat the flags. The validation sample is written to `data/manual/` because it holds raw text.
- 2026-10-27 B3: `collectors/census_gazetteer.py` (source name `gazetteer`; URL checked on the Census page, not downloaded here). `analysis/geo.py` draws the maps with a hand-simplified lower-48 outline (about 100 points, not an official boundary); AK/HI/PR are counted but not drawn. `build_metro_panel.py` gained `emp_it_2019_reported` (bubble size for Chicago-type metros); existing columns unchanged, so `metro_panel.csv` needs a rebuild to get it (the maps fall back to `emp_it_2019` without it).
- B4 (County Business Patterns) not started.

## Milestone: complex visualization, due Thursday 2026-11-05
Output: `notebooks/08_zgodba_SL.ipynb` (Slovenian, casual audience), exported to HTML. Palette and layout: `analysis/viz_theme.py`.
- [ ] M-A *(Stream A)* chapters 1-3 and 6 (timeline, heatmaps, size, stock reaction), `analysis/viz.py`, assembly and export
- [ ] M-B *(Stream B)* chapters 4-5 figure functions and aggregate files: see `docs/tasks/MILESTONE_petar_ch4_ch5.md`

## Requests between streams
(Write "A asks B: ..." or "B asks A: ..." here; the owner of the file makes the change.)
- 2026-10-30 A asks B (and everyone, `collect.py` is frozen): `collect.py` overwrote `data/manifest.json` with only the sources of that run, so every partial run (`--sources sec_fin`, `macro`, ...) wiped the other entries. Proposed change, already in this commit: `merge_manifest()` keeps old entries and replaces the ones that were re-run (test: `tests/test_collect_manifest.py`). The committed manifest currently holds only one entry; run `python collect.py` once (everything is cached) to rebuild it.

## Blocked / questions
