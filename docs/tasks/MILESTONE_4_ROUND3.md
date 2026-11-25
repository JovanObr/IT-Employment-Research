# Milestone 4 extension: round 3 hypotheses G and H (due Wed 2 Dec 2026, midnight)

Two small pre-registered tests that answer the two questions the talk now raises, each on data that is new to the project:

| | Question (plain words) | Why it matters for the talk | Owner |
|---|---|---|---|
| **G** | Did ICT hiring in each EU country follow **its own** central bank, or one common shock? | Chapter 2 says layoffs came "after dearer money". Countries raised rates at different times (Czechia and Hungary mid-2021, Poland late 2021, the euro area July 2022), which is a natural experiment the US data cannot give. | **B (Petar)** |
| **H** | Did IT employment in Slovenia really fall after 2021, or is the dip in the survey only? | Chapter 6 shows Slovenia's ICT share falling 4.8 % -> 3.8 % (2021 -> 2023) in a small survey sample (round 1 A, round 2 A2 could not explain it). The official employment register counts everyone and has no sampling error. | **A (Jovan)** |

Rules for both: `docs/hypotheses/round3/README.md` (family, disclosure, verdict). Work directly on main as before: `git pull --rebase origin main`
before you start and before every push, commit only your own files, push only when `pytest` is green. Never commit downloaded data
(`data/raw`, `data/cache`); the manifest entry is committed.

## Schedule
| When | Stream A (H) | Stream B (G) |
|---|---|---|
| Wed 25 | this plan | read the plan |
| Thu 26 | H1 design check (metadata only), H2 registration committed and pushed | G1 design check (metadata only), G2 registration committed and pushed |
| Fri 27 - Sat 28 | H3 collector, code, synthetic tests, one real run; H4 dossier; notebook 11 (round 2 now) | G3 collector, code, synthetic tests, one real run; G4 dossier |
| Sun 29 | H5 figure `6w_register` + facts for Petar; chapter 2 screen for G (from Petar's figure) | G5 figure `2w_drzave` + facts for Jovan; chapter 6 screen for H (from Jovan's figure) |
| Mon 30 - Tue 1 | notebook 11 with round 3; rehearsal with the timer; non-expert test; `web_build --check --strict` | rehearsal of chapters 5-6; proofreading |
| Wed 2 | freeze | freeze |

## Data each stream needs (nothing crosses between machines)
Downloaded data are not on GitHub, so each test uses only data its owner can download with the repository's own code:
- **G** needs only the two new Eurostat tables (public API, `python collect.py --sources eurostat_g` on Petar's machine). It does not need the
  layoff tracker (`layoffs_clean.csv`, a manual download that only Jovan has) or the Indeed files: the numbers already seen are quoted.
- **H** needs only the new SURS table (public download, `python collect.py --sources surs` on Jovan's machine). The survey values it is compared
  with are already in the committed `reports/hypotheses_b_results.json` and `reports/hypotheses2_b_results.json` (Jovan also has the same
  Eurostat file, identical hash).
- **Everything that crosses streams goes through committed files:** results JSON, figure JSON in `web/figures/`, the facts block in the dossier.
  Notebook 11 reads the results files only, so it runs on either machine.
- **Independent re-check:** each of us can re-run the other's test by downloading the same public source. Eurostat and SURS revise data, so
  compare the input hash in the results file first; if it differs, small differences in the numbers are expected and are not an error.

## Website: who writes what (one exception to the folder ownership in `web/CONTRACT.md`)
Each result belongs in the other stream's chapter, so the owner of the **chapter** writes the screen text, and the owner of the **test** supplies
the figure and the numbers:
- **G -> chapter 2** (after the "Pred in po" screen, before the takeaway). Petar: figure `2w_drzave` in `analysis/web_figures_b.py` (with its
  `FIGURE_SOURCES` row) and a short "facts" block at the end of `docs/methods/G.md` (the numbers the screen may quote, in Slovenian).
  Jovan writes the screen in `web/chapters/02_zakaj_takrat/chapter.md`, minutes 2 -> 2.5.
- **H -> chapter 6** (after the "Evropa in Slovenija" screen). Jovan: figure `6w_register` in `analysis/web_figures_a.py` and the facts block at
  the end of `docs/methods/H.md`. Petar writes the screen in `web/chapters/06_kje/chapter.md`, minutes 2.5 -> 3.
- Total 16 of 20 minutes. Whatever the result, the screen says it plainly ("ne moremo trditi" is a result).
- Chapter 7's table (`7w_hipoteze`) gets a third round automatically once both results files exist (Jovan adds G and H to `HYPOTHESES`).

---

## Stream B: hypothesis G (Petar)

### G1 Design check (Thu 26, before registration; metadata and counts only, no values)
- Eurostat `jvs_q_nace2` (job vacancy statistics, quarterly): for indicator `JOBRATE`, section `J` (information and communication), each EU27
  country, which quarters 2018Q1-2025Q2 exist, with which flags, and whether the series is seasonally adjusted (`SA`) or not (`NSA`) per country.
  Some countries publish no section J or only NSA: count them.
- Eurostat `irt_st_m` (money market interest rates, monthly): which countries have the 3-month rate (`IRT_M3`), and the euro-area series (`EA`).
  Euro-area members use the euro-area rate from the month they used the euro (Croatia from 2023-01).
- List the countries with their own rate whose path differs from the euro area's in 2021-2023 (expected: CZ, HU, PL, RO, SE; DK and BG follow
  the euro closely, check). The test's information comes from these countries; record how many there are.
- Verify the data are not in the project yet (`data/raw/`, `data/manifest.json`, notebooks).

### G2 Registration (`docs/hypotheses/round3/G.md`), committed and pushed before any data value is looked at
A proposed design to register (change it in the registration if G1 shows a problem, and say why):
- **Hypothesis.** Across EU countries, a rise in a country's own short-term interest rate is followed by a fall in its ICT job vacancy rate,
  **beyond the change common to all countries in the same quarter**. Predicted: negative.
- **Unit and period.** Country-quarter, EU27 countries with a section J vacancy rate, 2019Q1-2024Q4 (fix the window in the registration).
- **Outcome.** Year-on-year change of the vacancy rate in section J, v(c,t) - v(c,t-4), percentage points (year-on-year removes seasonality, so
  NSA series can be used).
- **Exposure.** Year-on-year change of the country's 3-month interest rate one quarter earlier, r(c,t-1) - r(c,t-5) (quarterly mean of monthly
  values), percentage points.
- **Model.** OLS of outcome on exposure with country fixed effects and **quarter fixed effects**. The quarter effects absorb everything common to
  all countries in a quarter (the Fed, the global tech cycle, the energy shock), so the coefficient b is identified only from countries whose own
  rate moved differently from the others. That is the point of the test.
- **Primary test.** b, two-sided p from a wild cluster bootstrap by country (Rademacher weights, null imposed, 9,999 replicates). Standard
  cluster-robust p is unreliable with few countries that carry the variation; report it next to the bootstrap.
- **Secondary.** (1) Lag 0 and lag 2 instead of lag 1; (2) without countries flagged as estimated or low reliability; (3) all industries
  (`TOTAL`) instead of section J, to see whether ICT reacts more than the whole economy; (4) descriptive and labelled exploratory (seen data):
  the Indeed peaks by country and the tracker's Europe vs. US quarters next to the three first-hike dates (BoE 16 Dec 2021, Fed 16 Mar 2022,
  ECB 21 Jul 2022), **quoted from `docs/hypotheses/round3/README.md`, not recomputed** (the tracker is a manual download on Jovan's machine
  only). None can change the verdict.
- **Placebo.** Reassign the own-rate paths at random among the countries (1,000 times) and re-run; share with p < 0.05 (about 5 % expected).
- **Synthetic tests (run them before writing the registration, on simulated data only).** A panel built like the real one with a planted b
  (found) and with b = 0 (not found); a common shock in every country with b = 0 (must not be found: this checks that the quarter effects
  work). **Check the false-positive rate of the primary on simulated nulls (it must be near 5 %) before registering it:** with few
  countries carrying the variation, cluster methods can over-reject badly; H's first design (Newey-West, 24 months) rejected a true null
  24-54 % of the time and had to be replaced before registration. If the wild cluster bootstrap over-rejects, use randomization inference
  (the placebo's reassignment of rate paths) as the primary instead, and say so in the registration.
- **Power.** By simulation from the design: the smallest |b| found 80 % of the time.
- **Disclosure.** Copy the relevant lines of `docs/hypotheses/round3/README.md` ("What has already been seen").
- **Limits.** A vacancy rate is not employment; few countries carry the variation; the 3-month rate is a proxy for monetary policy; countries'
  rates partly respond to their own economy (reverse causation), which the lag reduces but does not remove.

### G3 Code and one real run
- Collector: a new module `collectors/eurostat_g.py` with `SOURCES = {"eurostat_g": lambda a: eurostat.collect(datasets={...})}` that calls the
  existing `collectors.eurostat.collect` with the two datasets and their filters (do not edit `collectors/eurostat.py`); run
  `python collect.py --sources eurostat_g`; add `SOURCE_LABELS` rows in `analysis/data_sources.py`.
- `analysis/hypotheses3_b.py` (test, secondary, placebo, `run`, `main`), `tests/test_hypotheses3_b.py` (synthetic tests first),
  results `reports/hypotheses3_b_results.json` with the key `G` -> `primary.p`, `primary.predicted_sign` (as in rounds 1-2) and the
  input file hashes.

### G4 Dossier `docs/methods/G.md`
From `docs/methods/TEMPLATE.md`, every section filled, plus at the end a "Facts for the website" block: 3-5 short Slovenian sentences with
the numbers the chapter 2 screen may quote.

### G5 Website
Figure `2w_drzave` (one message; conclusion-first title; `analysis.web_theme` helpers; e.g. the coefficient with its interval next to the
placebo distribution, or the vacancy rate of early-hiking countries vs. the euro area around the hikes, whatever shows the result best to a
general audience). Then the chapter 6 screen for H from Jovan's `6w_register` and the facts in `docs/methods/H.md`.

### Prompt to paste into the agent
"You are the Stream B agent on this repository. Read AGENTS.md, docs/STATUS.md, docs/tasks/MILESTONE_4_ROUND3.md,
docs/hypotheses/round3/README.md, docs/hypotheses/PREREGISTRATION.md (Common rules), docs/hypotheses/round2/A2_F.md (your round 2
registration, as the model for G.md), docs/methods/TEMPLATE.md and web/CONTRACT.md. Your task is hypothesis G (G1-G5). Work directly on main:
git pull --rebase origin main before you start and before every push, commit only your own files, push only when pytest is green.
Do G1 using metadata and counts only, then write and commit G2 before any value of the vacancy or interest-rate data is printed, plotted or
summarised. Then G3 with synthetic tests before the single real run, then G4 and G5. Never change a registered test, sample or threshold
because of a result; a fix after the run is a dated amendment. All visible text is plain Slovenian for a general audience. Do not edit
Stream A's files, except the chapter 6 screen described in G5, which is yours."

---

## Stream A: hypothesis H (Jovan)

### H1 Design check (Thu 26, metadata only)
SURS SiStat table **0700921S** "Delovno aktivno prebivalstvo po dejavnostih (SKD 2008), Slovenija, mesečno" (register of persons in
employment, SRDAP; download as PC-Axis: `https://pxweb.stat.si/SiStat/sl/Home/DownloadPxMatrix?pxMatrixName=0700921S`). Check from the
metadata (the `VALUES` lines of the PX file, not the data) that it has divisions J62 and J63 and the total, and which months exist.
If it has sections only, use the division-level table found the same way, and say so. Also check whether SURS publishes register employment by
**occupation** (SKP-08 groups 25 and 35, the closest match to Eurostat's "ICT specialists"), annual is enough.

### H2 Registration: done, `docs/hypotheses/round3/H.md` (2026-11-25)
Written after the metadata check and the synthetic tests, before any SURS download. One change from the first plan: the primary is no longer
Newey-West (it rejected a true null 24-54 % of the time with 24 autocorrelated months in the synthetic tests) but a test against the null
distribution simulated from the 2015-2019 noise; Newey-West is reported only.

### H3-H5
Collector `collectors/surs.py` (`SOURCES = {"surs": ...}`, PX file parsed into a long CSV, manifest record with the SURS licence), code
`analysis/hypotheses3_a.py` + `tests/test_hypotheses3_a.py`, results `reports/hypotheses3_a_results.json` (key `H`), dossier `docs/methods/H.md`
(generated like C2/E) with the facts block, figure `6w_register`, the chapter 2 screen for G, notebook 11 with both families.
