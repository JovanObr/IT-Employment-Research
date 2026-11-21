# Milestone 4 (due Wednesday 2026-12-02, midnight): round 2 hypotheses, presentation theme, first version of the final presentation

## The whole plan (both streams)

### What the milestone asks for
1. More hypothesis testing (round 2).
2. A full visual theme for the final presentation.
3. The beginnings of the core presentation: a **website in Slovenian**, the final talk of the project (second week of January).
4. From the feedback on milestone 3: (a) check whether Slovenia's result in hypothesis A is driven by its starting level or timing;
   (b) add the type of each source (journal, conference, working paper, report) to notebook 09's table; (c) an East vs. West Coast
   hypothesis; (d) **complete documentation of every hypothesis**: data, where it came from, every preparation step, the code, the test.

### The final presentation (what we are building towards)
- **For everyone:** a high-school student, a grandparent, the professor and a stranger must all follow every point and every chart.
  One idea per screen; each chart's title states its conclusion; annotations on the chart, not in a legend; every technical word has
  a hover definition; tested on one real non-expert before the deadline.
- **One through-line:** *"Kaj se je zgodilo z delovnimi mesti v IT po koroni in zakaj?"* Each chapter answers the next obvious question.
- **15-20 minutes, and it must stay that way as later milestones add work:** every chapter has a time budget; the core is planned for
  about 15 minutes, leaving up to 5 for later additions. New work joins as a chapter or a slot in one, never as a second storyline;
  detail that does not fit goes to the background page.
- **Data section:** every dataset, provider, period, the features we use and why (generated from `data/manifest.json` and
  `analysis/data_sources.py`, so it cannot go stale).
- **Background page "Za radovedne":** methods, glossary, the hypothesis dossiers, likely questions. Not part of the 20 minutes; it is
  what we use to answer follow-up questions.
- **One build, two ways to run it:** `web/dist/` is a self-contained folder (charts, data and plotly.js included) that GitHub Pages
  serves and that opens offline on a laptop by double-clicking `web/dist/index.html`.

| # | Chapter (working title) | Owner | Minutes |
|---|---|---|---|
| 1 | Kaj se je zgodilo? Val zaposlovanja, nato val odpuščanj (koliko ljudi, kdaj) | A | 2 |
| 2 | Zakaj takrat? Obrestne mere, ne ChatGPT; uradna stopnja odpuščanj se skoraj ni premaknila | A | 2-3 |
| 3 | Koga je zadelo? Velika podjetja in tista, ki so prej najhitreje zaposlovala; padec prihodkov tega ne pojasni | A | 2-3 |
| 4 | Se je res zgodilo? Napovedi se pokažejo v številu zaposlenih; borza se je komaj odzvala | A | 2 |
| 5 | Kaj se je spremenilo pri delovnih mestih? Delo na daljavo, umetna inteligenca, mladi | **B** | 2 |
| 6 | Kje? Jug ZDA proti velikim središčem, vzhodna proti zahodni obali, Evropa in Slovenija | **B** | 2-3 |
| 7 | Kaj smo dokazali in česa ne? Preverjene hipoteze, preprosto povedano | A | 2 |
| 8 | Kaj to pomeni? Trije sklepi | A | 1 |

### Round 2 hypotheses (one Holm family; rules in `docs/hypotheses/round2/README.md`)
| | Hypothesis | Owner |
|---|---|---|
| A2 | EU countries with a higher ICT share in 2021 grew less by 2024 (catch-up) | **B** |
| F | IT job growth 2019-2024 differed between East Coast and West Coast metros | **B** |
| C2 | Layoffs announced in year t show up in that year's headcount change, for t = 2024 and 2025 (new 10-K data) | A |
| E | Layoff announcements cluster within three business days of the company's earnings release | A |

### Schedule
| Phase | Dates | Stream A (John + Claude) | Stream B (Petar) |
|---|---|---|---|
| 0 | Fri 20 - Sat 21 Nov | Source-type column in 09; register C2, E; **`web/CONTRACT.md`** (chapter format, theme, build) and the site skeleton | Register A2, F; Slovenia exploratory check |
| 1 | Sun 22 - Wed 25 | C2 (2024 headcounts), E; dossiers C, D, C2, E; full theme | A2, F; dossiers A, B, A2, F |
| 2 | Wed 25 - Sun 29 | Chapters 1-4, 7, 8; data section generator; build script | Chapters 5-6; background Q&A for chapters 5-6 and A, B, A2, F |
| 3 | Mon 30 Nov - Tue 1 Dec | Notebook 11 (Holm across round 2); rehearsal with a timer; non-expert test | Same for chapters 5-6; proofreading |
| - | Wed 2 Dec, midnight | Freeze | Freeze |

---

## Stream B (Petar's agent): what to do

### Rules
- **Work directly on `main`.** `git pull --rebase origin main` before you start and before every push; commit only your own files (never
  `git add -A`); push only when `pytest -q` and `python -m compileall -q .` are green. Never commit `data/raw/` or `data/manual/`.
- **Files you own:** `docs/hypotheses/round2/A2_F.md`, `analysis/hypotheses2_b.py`, `tests/test_hypotheses2_b.py`,
  `reports/hypotheses2_b_results.json`, `docs/methods/A.md`, `B.md`, `A2.md`, `F.md`, your rows in `analysis/data_sources.py`
  (add only), and from phase 2 the folders `web/chapters/05_*`, `web/chapters/06_*`, `web/background/b.md`, `web/glossary/b.yml`,
  `analysis/web_figures_b.py`, `tests/test_web_figures_b.py`. Your section of `docs/STATUS.md`. Everything else belongs to Stream A;
  requests go under *Requests between streams* in `docs/STATUS.md`.
- **Pre-registration as in round 1:** design checks that only count rows are fine; no looking at outcomes before your registration is
  committed and your synthetic tests pass; then **one** real run; a bug fix after the run is a dated amendment, never a changed test.

### B1 Slovenia: exploratory check (answers feedback point 1; no test, no verdict)
The reviewer asked: is the data normalised, does Slovenia's small size matter, was its level already high in 2021, did its rise come earlier?
- Answer "normalised" in writing: the measure is the ICT share of total employment (`PC_EMP`), so country size is already divided out;
  say what that does and does not solve.
- Show, from `eurostat_isoc_sks_itspt.csv`: Slovenia's share 2015-2025 next to the EU-27 aggregate and the range of other countries
  (2021 break marked); Slovenia's 2021 level and its rank; relative change (%) next to the absolute change (points); absolute numbers of
  ICT specialists if Eurostat publishes them (`isoc_sks_itspn` or similar; add a collector if needed, with a manifest record).
- Deliver as `build_figures_b(results)` entries named `11x_slovenija_*` (below), with the four Slovenian explanation parts. Clearly
  labelled exploratory.

### B2 Register A2 and F (`docs/hypotheses/round2/A2_F.md`), commit before any real run
**A2 (catch-up):** across the EU-27, the change in ICT share 2021 -> 2024 is negatively related to the 2021 level.
- **Watch out for regression to the mean:** if the starting level is measured with noise, regressing the change on it produces a
  negative slope even without any real catch-up. Choose a design that avoids it and justify it in the registration (for example a
  starting level not used in the change, such as the 2020 value or the 2019-2020 average, despite the method break; or a placebo by
  simulation with the measured noise). State how Slovenia's position will be read (its residual).
- Primary test, placebo, power with only 27 countries, and the disclosure that round 1's A result is known.
**F (East vs. West Coast):** IT job growth 2019-2024 (`metro_map_data.csv`, `it_growth_pct`, `usable` metros only) differs between East
and West Coast metros.
- Define the coasts **by state list in the registration** (a suggestion to check: West = WA, OR, CA; East = the Atlantic states from ME to
  FL plus DC), how a metro spanning states is assigned (first state in the name, as in chapter 5), and how withheld metros are handled.
- Primary test (two-sided; justify the choice, e.g. Mann-Whitney because growth rates have heavy tails), effect with a bootstrap interval,
  a size-weighted secondary, placebo (random coast labels among all metros), power from the counts per coast.
- Disclose what is already known from chapter 5 and notebook 09 (regional medians).

### B3 Implement and run (`analysis/hypotheses2_b.py`)
- Functions per hypothesis as in round 1 (`test_*`, `secondary_*`, `placebo_*`), `run()` and `main()` writing
  `reports/hypotheses2_b_results.json` with `inputs_sha256`, and for each hypothesis `primary` with at least `p` (two-sided),
  `predicted_sign`, the estimate and its interval.
- `build_figures_b(results) -> dict[str, tuple[Figure, dict]]` returning, for notebook 11, one figure with its four Slovenian explanation parts
  (`kaj`, `zakaj`, `pomen`, `omejitve`) for `11a2_*`, `11f_*` and the `11x_slovenija_*` figures. Use `analysis.viz_theme`. Write `pomen` so
  it does not state a verdict: notebook 11 adds the verdict after the Holm correction across all four.
- Add `FIGURE_SOURCES` rows for every figure name. `tests/test_data_sources.py` already reads the names from `build_figures_b` in
  `analysis/hypotheses2_b.py` (keys must be literal strings in that function, like `{"11a2_...": fig}`), so you do not edit the test.
- Synthetic tests first (planted effect found, null not found, placebo rate near 5 % on simulated data), then one real run.

### B4 Methods dossiers: `docs/methods/A.md`, `B.md`, `A2.md`, `F.md`
From `docs/methods/TEMPLATE.md`, every section filled. These are what we will answer the professor's questions from, so: exact files and
hashes, every preparation step with row counts, code excerpts, why the test, the placebo. For A, include the answer to the reviewer's
normalisation question.

### B5 Website chapters 5 and 6 (phase 2, after Stream A publishes `web/CONTRACT.md` on Sat 21 Nov)
Follow the contract exactly (chapter folder format, figure export, theme, glossary). Chapter 5 (2 min): remote work, AI, junior roles (and why
juniors could not be measured). Chapter 6 (2-3 min): Sun Belt vs. hubs, East vs. West (F, whatever its result), Europe and Slovenia (A, A2, B1).
Also `web/background/b.md`: the questions a professor would ask about chapters 5-6 and hypotheses A, B, A2, F, with short answers.
Also `web/data/b.md`: your datasets in the same table as `web/data/a.md` (source, what it measures, exact period, what was used, why,
chapter) plus the list of what was done to the data before testing (contract section "Data section"); check every claim against the code.
Chapter 7's table of all hypotheses (`7w_hipoteze`, Stream A) reads `reports/hypotheses2_b_results.json` by itself: keep the keys `A2` and `F`,
each with `primary.p` and `primary.predicted_sign` (as in round 1), and tell Jovan when it is pushed so the figure is re-exported.
Stream A's chapters 1-4, 7, 8 and `web/background/a.md` are the worked example of the tone and length.
Plain Slovenian for a general audience; conclusion-first chart titles; stay inside your minutes.

### Schedule for Stream B
| When | What |
|---|---|
| Sat 21 Nov | B1 exploratory Slovenia; B2 registration of A2 and F committed and pushed |
| Sun 22 - Tue 24 | B3 code and synthetic tests; one real run; results pushed |
| Wed 25 | B4 dossiers A, B, A2, F |
| Wed 25 - Sun 29 | B5 chapters 5-6 and background Q&A, following `web/CONTRACT.md` |
| Mon 30 Nov - Tue 1 Dec | Proofreading, timing your chapters aloud, fixes only |

### Prompt to paste into the agent
"You are the Stream B agent on this repository. Read AGENTS.md, docs/STATUS.md, docs/tasks/MILESTONE_4.md,
docs/hypotheses/round2/README.md, docs/hypotheses/PREREGISTRATION.md (Common rules), docs/methods/TEMPLATE.md and analysis/hypotheses_b.py
(round 1, for style). Work directly on main: git pull --rebase origin main before you start and before every push, commit only your own
files, push only when pytest is green. Do B1, then B2 (commit the registration before any real run), then B3 with synthetic tests before the
single real run, then B4. Start B5 only after web/CONTRACT.md exists, and follow it exactly. Never change a registered test, sample or
threshold because of a result; a fix after the run is a dated amendment. All visible text is plain Slovenian for a general audience. Do not
edit Stream A's files."
