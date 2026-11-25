# Round 3 of pre-registered hypotheses (milestone 4 extension, due 2026-12-02)

Same rules as rounds 1 and 2 (`docs/hypotheses/PREREGISTRATION.md`, "Common rules"; `docs/hypotheses/round2/README.md`), with these specifics:

- **Family:** G (Stream B, registration `G.md`) and H (Stream A, registration `H.md`). One Holm correction across the two.
  Rounds 1 and 2 are closed families; their verdicts do not change.
- **Each owner registers in their own file and commits it before the outcome data are downloaded** (or, where they already exist, before any
  value of the outcome is printed, plotted or summarised). The commit is the registration. Allowed before it: metadata only (which countries,
  months, codes, flags a table has; row counts), listed in the registration under "Design checks".
- **Both questions follow from results we have seen, and new data that did not suggest them is the only fair test.** So both use a source
  that is not yet in the project. The disclosure section of each registration must say exactly what was seen, including what is listed below.
- **Every test has:** one primary test (two-sided p), the predicted sign, a placebo or calibration check on data with no effect, synthetic tests
  (planted effect found, null not found), a power statement, and a methods dossier from `docs/methods/TEMPLATE.md` after the run.
- **Verdict rule:** supported only if Holm-adjusted p < 0.05 (m = 2) and the predicted sign. Notebook 11 (Stream A) shows round 2 and round 3
  as two separate families.

## What has already been seen (both registrations must repeat what applies to them)
- **Job postings by country (Indeed, software development):** notebook 01 printed the peaks: US 02/2022, United Kingdom 04/2022,
  Germany 05/2022, France 07/2022. That is why G does **not** use postings for its test.
- **Layoff announcements by region (tracker):** on 2026-11-25, while planning this round, quarterly counts for 2021-2023 were printed for
  Europe and the US: Europe went from 4 (2022Q1) to 31 (2022Q2), at the same time as the US (21 to 174), before the ECB's first hike
  (21 July 2022). That is why G does **not** use the tracker for its test either.
- **Slovenia, Eurostat survey (LFS), ICT specialists as % of employment:** rounds 1-2 and B1 showed 4.8 (2021), 3.8 (2023), 4.3 (2024),
  4.5 (2025). The register data H uses (SURS) have never been downloaded.
- **Not seen by anyone in the team:** Eurostat job vacancy statistics (`jvs_q_nace2`), Eurostat interbank rates (`irt_st_m`), SURS register
  employment by activity. Verify before registering (`data/raw/`, `data/manifest.json`, the notebooks).
