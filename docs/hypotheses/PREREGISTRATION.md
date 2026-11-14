# Milestone 3: pre-registration of four narrow hypotheses

Written 2026-11-14, **before any of the tests below was run**. Commit this file before running them; the commit time is the
registration time. After that, the hypotheses, samples, tests, thresholds and decision rules below do not change. Anything
not specified here is reported as *exploratory*. If an error forces a change, it is added as a dated amendment at the end,
with the reason, and the original text stays.

## Common rules
- **Family and correction.** The four primary tests (A, B, C, D) form one family. Each gives one two-sided p-value. A hypothesis is
  *supported* only if its Holm-adjusted p-value is below 0.05 **and** the effect has the predicted sign. Otherwise it is *not supported*;
  "not supported" is not proof of no effect, and the report gives the confidence interval to show what sizes the data rule out.
- **One primary test per hypothesis.** Secondary checks are listed; they can qualify the conclusion but never turn "not supported" into "supported".
- **Placebo for each test.** The same method applied where no effect should exist; its false-positive rate is reported with the result.
- **Code is tested on synthetic data first:** a planted effect must be found and a null must not be (tests in `tests/`).
- **Frozen inputs.** Results are computed from the data files as they stand at the registration commit; the SHA-256 of each input file is
  printed by the analysis and recorded with the results.
- **Power.** Each hypothesis states its minimum detectable effect (80 % power, alpha 0.05) computed from design facts only.

## What we already knew when writing this (disclosure)
Notebooks 08 and 09 already showed: the tracker-wide stock reaction (-0.58 % over days 0..+1, interval includes zero); that headcount change
2022-2023 is unrelated to 2019-2021 hiring growth; IT job growth 2019-2024 by metro (Austin about +40 %, San Francisco about -2 % in the
milestone 2 geography comparison); the pooled within-firm revenue effect (about zero). **Not looked at before registration:** stock
reactions by first vs. repeat announcement; headcount change by layoff status; Slovenia's ICT share relative to other EU countries;
the quarterly timing of IT employment in San Francisco vs. Austin around the first rate hike.

## Dropped before testing: within-firm revenue effect in semiconductors vs. software
Planned as C. Design check (2026-11-14): only 10 semiconductor firms (SIC 367x) have both layoff and non-layoff quarters; a simulation that
plants a +3 percentage-point within-firm effect (60 % of the 5 % base rate) detects it in 60 % of runs. Below 80 % power, so it is not tested.

---

## A. Slovenia's ICT specialists (Stream B)
**Hypothesis.** From 2021 to 2024, the share of ICT specialists in total employment grew more in Slovenia than in most EU countries.
- **Data.** Eurostat `isoc_sks_itspt`, unit `PC_EMP` (ICT specialists, % of total employment), EU-27 countries. `data/raw/eurostat_isoc_sks_itspt.csv`.
- **Measure.** Change in percentage points, 2021 -> 2024. 2021 is the first year after the EU-wide break in the Labour Force Survey series (flag `b` in 2021).
- **Primary test.** Prediction-interval test: is Slovenia's change an outlier relative to the other 26 countries?
  t = (x_SI - mean_others) / (sd_others * sqrt(1 + 1/26)), two-sided p from Student's t with 25 degrees of freedom. Predicted: t > 0.
  (A rank test alone cannot do this job: with 27 countries its smallest p is 1/27 = 0.037, which the Holm correction would almost never let through.)
- **Secondary.** Slovenia's rank among the 27 (rank p = rank / 27); the same for 2019 -> 2024 (crosses the 2021 break; reported with that warning);
  relative change in %; Slovenia vs. the EU-27 aggregate (`EU27_2020`); a normality check of the 26 other changes (Shapiro-Wilk), since the
  primary test assumes roughly normal spread; if it fails at 0.05 the report says the primary p is approximate.
- **Placebo.** The same prediction-interval test for each of the other 26 countries against the rest; the share with p < 0.05 is reported (about 5 % expected if the test is calibrated).
- **Power / limits.** The test can only say "unusual among EU countries", not why. With 26 comparison countries, Slovenia must lie about 2.1 standard deviations from their mean to reach p < 0.05 before correction.
  Estimated values (flag `e`) are used as published and listed in the report.

## B. San Francisco vs. Austin after the first rate hike (Stream B)
**Hypothesis.** After the first Fed rate hike (2022-03-16), IT employment in the San Francisco metro fell relative to Austin.
- **Data.** BLS QCEW, NAICS 5415, private ownership, quarterly average of the three monthly employment levels, San Francisco-Oakland
  (CBSA 41860) and Austin-Round Rock (CBSA 12420), 2019Q1 to the last published quarter. `data/raw/bls_qcew_areas_it_industries.csv`.
  Use the code crosswalk in `config/qcew_code_crosswalk.csv` if a code changed with the 2023 delineation.
- **Model.** d_t = log(emp SF) - log(emp Austin) per quarter; d_t = a + b * post_t + e_t, post = 1 from 2022Q2. **Primary:** b, with
  Newey-West (HAC) standard error, 4 lags; predicted b < 0.
- **Pre-trend check (decides how b is read).** Regress d_t on a linear time trend over 2019Q1-2022Q1. If that trend is significant at 0.05,
  the primary model adds the linear trend (b then measures the break from trend) and the report says so.
- **Placebo.** The same b for every pair of metros among the 30 metros with the most NAICS 5415 jobs in 2019 and complete, undisclosed-free
  series; report where SF-Austin ranks and the share of pairs with |b| at least as large.
- **Secondary.** Same with 2020Q1 excluded (pandemic shock); establishments instead of employment.
- **Limits.** Two areas only; QCEW counts NAICS 5415 (computer systems design), not software publishers or big tech; quarterly series are
  short (about 13 pre and 10 post quarters).

## C. Do announced layoffs show up in headcount? (Stream A)
**Hypothesis.** US tech companies that announced a layoff in 2022-2023 had a larger fall in employees from end-2021 to end-2023 than
tech companies that did not announce one.
- **Sample.** Companies in the SEC tech universe (`is_tech`, SIC 357x/366x/367x/737x) with a 10-K headcount for period years 2021 and 2023
  (`data/raw/sec_headcount.csv`, read with the current sentence rules, `sec_headcount.recheck`). Log changes beyond a factor of 10 are
  parsing errors and dropped (as in notebook 09).
- **Exposure.** At least one tracker announcement dated 2022-01-01 to 2023-12-31 by a company matched to the CIK (`layoffs_clean.csv`,
  `sec_company_matches.csv`).
- **Outcome.** log(employees 2023 / employees 2021).
- **Primary test.** Mann-Whitney U, two-sided; effect = difference in medians (announced - not announced) with a 95 % bootstrap interval over
  companies (5,000 resamples). Predicted: negative.
- **Secondary.** OLS of the outcome on announced + company size (log assets, last 2021 value in the company panel) + SIC 3-digit group,
  HC3 standard errors (big firms announce more and may change differently); the same with outcome 2022 -> 2023.
- **Placebo.** Shuffle the announced label across companies 1,000 times; false-positive rate of the primary test at 0.05 is reported.
- **Power.** 454 companies have both years, 105 announced (counts only, 2026-11-14). Minimum detectable shift is reported from the pooled
  spread of the outcome before the groups are compared.
- **Limits.** Headcount is a point-in-time count read from text (about 9 in 10 correct in hand checks); announcements can be abroad; a firm
  can cut and hire in the same year; acquisitions change headcount.

## D. Repeat layoff announcements and the stock price (Stream A)
**Hypothesis.** A company's repeat layoff announcements get a more negative stock reaction than its first one.
- **Sample.** The 611 usable events of the event study (`data/processed/event_study_events.csv`, days 0..+1 abnormal return, market model on
  the NASDAQ Composite, glitches beyond +-100 % daily blanked, follow-ups within 30 days already dropped).
- **Exposure.** Repeat = the company (CIK) has an earlier tracker announcement on any earlier date (all tracker rows, also those dropped as
  follow-ups); first = none earlier. 228 first, 383 repeat (counts only, 2026-11-14).
- **Primary test.** Difference in mean abnormal return, repeat - first, winsorised at 1 % / 99 % over all events; two-sided permutation test
  shuffling the label across events (10,000 permutations). Predicted: negative.
- **Secondary.** 95 % interval of the difference from the day-clustered bootstrap (as in notebook 09); Mann-Whitney on unwinsorised values;
  excluding events before 2020-09-11 (the tracker starts 2020-03-11, so "first" is uncertain early on); excluding 2020.
- **Placebo.** The same difference on random non-event dates of the same companies with the same labels (as in the event study's placebo);
  false-positive rate reported.
- **Power.** With a spread of about 9.7 % and 228 vs. 383 events, the minimum detectable difference is about 2.3 percentage points.
- **Limits.** "First" means first in the tracker, not first ever; repeat announcers may differ from one-time announcers in other ways.

## Amendments
(none)
