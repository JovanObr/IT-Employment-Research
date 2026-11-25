# Round 3 pre-registration, Stream A: hypothesis H

Written 2026-11-25, **before any SURS data were downloaded** (no file from SURS exists in `data/raw/` or `data/cache/`; the collector below has
not been run). Commit this file first; the commit is the registration. Common rules: `docs/hypotheses/round3/README.md` (and rounds 1-2).
Family: G, H (one Holm correction, m = 2).

## Design checks done before registration (metadata only, no values)
- SURS SiStat table **0700921S** "Delovno aktivno prebivalstvo po dejavnostih (SKD 2008), Slovenija, 2000M01 - 2025M12" (register of persons in
  employment, SRDAP), last published 17 March 2026. Read from the table's selection page (variable lists only; no data cell was displayed):
  - `SKD DEJAVNOST` has 110 values, among them the total "SKD dejavnost - SKUPAJ", section "J INFORMACIJSKE IN KOMUNIKACIJSKE DEJAVNOSTI" and
    the divisions "J62 Računalniško programiranje, svetovanje in druge s tem povezane dejavnosti" and "J63 Druge informacijske dejavnosti".
  - `DELOVNO AKTIVNO PREBIVALSTVO` has 7 values, among them "1 Delovno aktivno prebivalstvo - SKUPAJ" and "11 Zaposlene osebe - skupaj".
  - `MESEC` runs monthly from 2000M01 to 2025M12 (312 months), so 2015-2025 are all available.
  - Notes on the table: from January 2020 the activity of a person is the activity of the unit of the business entity where the person works
    (Statistical Business Register); during the move to SKD 2025 the data are still published in SKD 2008 (SKD 2025: table 0700928S).
- A register table by **occupation** (SKP-08 groups 25 and 35, the closest match to Eurostat's "ICT specialists") was not found in a search of
  SiStat; it is not used.

## Disclosure (what was already seen)
- **The question comes from the survey.** Eurostat `isoc_sks_itspt` (Labour Force Survey), ICT specialists as % of total employment, Slovenia:
  4.8 (2021), 3.8 (2023), 4.3 (2024), 4.5 (2025), seen in rounds 1-2 (A, A2) and Petar's B1 figure. Round 1's A found Slovenia's change
  2021 -> 2024 the smallest in the EU (-0.50 points); round 2's A2 found that a high starting level does not explain it.
- **The register has never been looked at by anyone in the team** (checked: no SURS file in `data/raw/`, no SURS reference in the code,
  notebooks or documents before this registration).
- The predicted sign (register share higher in 2023 than in 2021) comes from the reasoning below, not from the register.

---

## H. Slovenia's survey dip is not in the employment register
**Hypothesis.** In the Statistical Register of Employment, the share of Slovenian persons in employment working in IT services (SKD J62 + J63)
was **higher** on average in 2023 than in 2021; the survey's fall from 4.8 % to 3.8 % does not appear in the register.
**Why we expect this.** The Labour Force Survey estimates a small group (about 40 to 50 thousand people in Slovenia) from a sample, so a one-point
swing in two years can be sampling noise; the register counts every person in employment every month and has no sampling error.

- **Code.** `collectors/surs.py` (download and parse), `analysis/hypotheses3_a.py` (`python -m analysis.hypotheses3_a`; refuses to run
  unless this file is committed), results `reports/hypotheses3_a_results.json` (key `H`).
- **Data.** SURS 0700921S, downloaded as PC-Axis (`python collect.py --sources surs`, `collectors/surs.py`), parsed to
  `data/raw/surs_0700921S.csv` (long format: activity, status, month, value). Used: status "1 Delovno aktivno prebivalstvo - SKUPAJ";
  activities "SKD dejavnost - SKUPAJ", J62, J63. Values as published.
- **Unit.** Month.
- **Outcome.** s(t) = 100 x (J62(t) + J63(t)) / total(t), percentage points.
- **Noise model (fixed before the comparison).** Fit a linear trend to s(t) over 2015M01-2019M12 and an AR(1) to its residuals:
  coefficient phi and innovation sd. This is the month-to-month noise of the share when nothing special happens.
- **Primary test.** d = mean of s over the 12 months of 2023 minus the mean over the 12 months of 2021, in percentage points. Its null
  distribution: 10,000 simulated 36-month series (2021-2023) of AR(1) noise with that phi and sd and no change; two-sided
  p = (number of |d_null| >= |d| + 1) / 10,001. Predicted: **d > 0**. The question is the level: any rise counts, including the ordinary
  growth trend (whether growth slowed is secondary 3).
- **Effect and interval.** d with d +- 1.96 x sd(d_null). Shown next to the survey's change, -1.0 point.
- **Why this test (and why not Newey-West).** Monthly values are strongly autocorrelated (the same people month after month), so the 24 months
  carry much less information than 24 independent values. The design was first written with a Newey-West regression (6 lags); the synthetic
  tests, run before this registration on simulated data only, showed that with 24 months it rejects a true null far too often (24 %, 31 % and
  54 % instead of 5 % for phi = 0.3, 0.6, 0.9), while the simulated null keeps 5.3 %, 5.1 % and 5.6 %. So the simulated null is the primary
  and Newey-West is only reported.
- **Secondary** (none can change the verdict):
  1. Persons in J62 + J63: % change of the yearly mean 2021 -> 2023.
  2. The primary test for 2021 vs. 2024 (the years of round 1's A).
  3. Slowdown: linear trend of s(t) fitted on 2015M01-2019M12; mean deviation of 2022M01-2023M12 from that trend
     (did Slovenian IT growth slow after the rate rises, as in the US?). Descriptive: its Newey-West p is printed but, for the reason above,
     not read as evidence. The 2020 change in how activity is assigned (see notes) lies
     between the fit and the test period: read with care.
  4. J62 alone (computer programming and consultancy, the core), with its own noise model.
  5. Employees only (status "11 Zaposlene osebe - skupaj") instead of all persons in employment, with its own noise model.
  6. Newey-West (6 lags) on the 24 months, reported only (see above).
  7. Sensitivity: the primary with phi = 0.9 (much more persistent noise than measured).
- **Placebo (checks the noise model on real data).** 2,000 series of 36 months built from random 12-month blocks of the real detrended
  2015-2019 residuals (so they keep the real dependence, not the AR(1) assumption, and contain no change), run through the primary test;
  share with p < 0.05 (about 5 % expected; clearly more would mean the AR(1) model understates the noise).
- **Synthetic tests** (`tests/test_hypotheses3_a.py`, all passing before this registration): a planted shift of +0.5 and -0.5 points is
  found with the right sign; with no shift the primary's false positive rate is 3-8 %; Newey-West over-rejects (kept as a test, so the reason
  stays documented); the block placebo is near 5 % on AR(1) data; the PC-Axis parser reads a small hand-made file correctly (variable order,
  quotes, missing values, Slovenian letters).
- **Power.** From the noise model: the smallest shift found 80 % of the time by the primary, logged before d is computed.
- **Limits.** Industry is not occupation: the register counts everyone working in IT firms (including non-IT staff) and misses IT specialists in
  banks, industry or government, which the survey includes; so a register that disagrees with the survey does not prove the survey wrong,
  it only shows that IT employment in IT firms did not fall. Activity is that of the employer's unit, as recorded in the business register.
  One country; no cause is tested.

## Amendments
(none)
