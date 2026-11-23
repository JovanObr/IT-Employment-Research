# Round 2 pre-registration, Stream B: hypotheses A2 and F

Written 2026-11-23, **before any test of A2 or F was run and before the B1 Slovenia exploratory figures were drawn** (B1 shows every
country's level, which would reveal the A2 relation, so it is done after this commit). Commit this file first; the commit is the
registration. Common rules: `docs/hypotheses/round2/README.md` (and round 1, "Common rules"). Family: A2, F, C2, E (one Holm correction).

## Design checks done before registration (counts only)
- A2: `data/raw/eurostat_isoc_sks_itspt.csv`, unit `PC_EMP`: all 27 EU countries have a numeric value in every year 2005-2025
  (26 in 2004). So the start level 2019-2020, the change 2021 -> 2024 and the secondary 2021 -> 2025 are available for all 27.
  The file also has unit `THS_PER` (thousand persons), used only in the B1 exploratory figures.
- F: `data/processed/metro_map_data.csv` (403 metro and micro areas, 263 with `usable == True` job growth). With the state lists below and
  the first-state rule: **West 41 usable (4 withheld or incomplete), East 97 usable (30 withheld or incomplete)**, other states 125 usable
  (106 not). Establishment growth (`usable_estab`): West 44, East 117. Usable metros with at least 1,000 IT jobs in 2019: West 15, East 44.
  While checking the file layout one data row (Abilene, TX, not a coast metro) was printed; no growth value of a coast metro was looked at.

## Disclosure (what was already seen)
- **A2 comes from round 1's A.** Round 1 computed, and the team has seen, every EU country's change in the ICT share 2021 -> 2024
  (`reports/hypotheses_b_results.json`, `A.primary.values`): Slovenia had the smallest change (-0.50 points, rank 27 of 27) and the
  mean of the other 26 was +0.58. The relation between those changes and any starting level was **not** computed or plotted; the
  2019 and 2020 levels of countries other than Slovenia were not looked at for this question. Because the changes themselves are known,
  A2 is a weaker confirmation than a test on new data; it is registered anyway because the milestone feedback asks for it, and the
  dossier will say so. The secondary 2021 -> 2025 adds one year that round 1 did not use (it is not new data for 2021-2024).
- **F:** what is known is chapter 5 of notebook 08 and notebook 09: regional medians by Census region (the Census "West" also holds the
  Mountain states, the "South" holds Texas), the map, and single metros: Austin about +40 %, San Francisco about -2 %, Boston, Los Angeles,
  San Diego and Philadelphia lost IT jobs, Miami, Orlando, Tampa, Charlotte, Seattle grew (AGENTS.md section 8). The East and West
  Coast groups defined below were never formed or compared. The predicted sign (West below East) is chosen from that knowledge.

---

## A2. Catch-up across the EU: countries that started higher grew less
**Hypothesis.** Across the 27 EU countries, the change in the ICT-specialist share of employment from 2021 to 2024 is negatively related to
the country's level before the period.
- **Data.** Eurostat `isoc_sks_itspt`, unit `PC_EMP` (ICT specialists as % of total employment), `data/raw/eurostat_isoc_sks_itspt.csv`
  (`python collect.py --sources eurostat`). Values used as published; flagged cells are listed in the results.
- **Unit.** Country, n = 27 (EU27 member states; the `EU27_2020` aggregate is not a unit).
- **Outcome.** change_c = share_c(2024) - share_c(2021), percentage points (the same outcome as round 1's A).
- **Start level.** start_c = mean(share_c(2019), share_c(2020)), percentage points.
- **Why this start level (regression to the mean).** If the start level were share(2021), the same noisy 2021 number would enter both the
  start (with +) and the change (with -), so a negative slope would appear even with no real catch-up. The 2019-2020 average shares no
  survey year with the change, so independent sampling noise cannot create a slope. The 2021 method break (new Labour Force Survey
  regulation, flag `b`) lies between start and change; a country-specific level shift at the break moves the start level relative to the new
  series but does not enter the change, which is measured wholly in the new series. Averaging two years halves the sampling variance of
  the start. What it does not remove: a real, persistent temporary high in 2019-2021 that later fades would still look like catch-up.
- **Primary test.** OLS slope b of change_c on start_c; two-sided permutation p (10,000 permutations of change_c across countries; p =
  (number of |b_perm| >= |b_obs| + 1) / (10,000 + 1)). Predicted: **b < 0**.
- **Effect and interval.** b in percentage points of change per 1 point of start level, with a 95 % bootstrap interval resampling countries
  (5,000 times, percentile).
- **Why this test.** 27 points are too few to trust a normal approximation if one country is extreme (Ireland, Finland, Sweden have high
  levels); the permutation test needs only exchangeability under no relation. The classical OLS p is reported next to it.
- **Slovenia (answers the feedback).** The line fitted on the other 26 countries; Slovenia's residual (observed minus predicted change), its
  prediction-interval t (as in round 1) and its rank among the 27 residuals of the full fit. Read as: if Slovenia's residual is small, its
  small change in round 1 is what its high starting level predicts; if it is still strongly negative, the level does not explain it.
  Descriptive only, no verdict.
- **Secondary.** (1) Start level = 2021 (the naive design, reported to show the regression-to-the-mean bias next to the primary);
  (2) Spearman rank correlation of start_c and change_c; (3) relative change 100 * (share 2024 / share 2021 - 1) on start_c; (4) change
  2021 -> 2025 on start_c; (5) primary without Slovenia. None can change the verdict.
- **Placebo (simulation with the measured noise).** Noise sd sigma = root mean square, over the 27 countries, of the residual sd of a linear
  trend fitted to each country's 2015-2020 values (6 years, 4 df; an upper bound, since real wiggles count as noise). Simulated world with
  no catch-up: true level_c = start_c; true change_c drawn independently of the level from N(mean, sd_true) with mean and sd_true taken from
  the observed changes (sd_true^2 = max(var(change) - 2 sigma^2, 0)); every observed yearly value = true value + N(0, sigma). 2,000 simulated
  data sets; the primary test (1,000 permutations each) and the naive 2021-start design are run on each; the share with p < 0.05 is reported
  for both (expected about 5 % for the primary; above 5 % for the naive design if regression to the mean matters).
- **Power.** n = 27: a correlation of about |r| = 0.52 is detectable with 80 % power at alpha 0.05 (Fisher z: 2.80 / sqrt(24) = 0.57).
  Smaller catch-up effects will usually be missed.
- **Limits.** 27 countries; levels and changes are survey estimates (small countries such as SI, CY, LU, MT have larger sampling error);
  the 2021 break; a correlation across countries says nothing about why.

## F. East vs. West Coast: IT job growth 2019-2024
**Hypothesis.** IT job growth 2019 -> 2024 (QCEW, NAICS 5415) differs between US metro areas on the West Coast and on the East Coast;
predicted: **lower on the West Coast**.
- **Data.** `data/processed/metro_map_data.csv` (`python build_metro_panel.py`, then `python -m analysis.geo mapdata`), column `it_growth_pct`
  (growth of NAICS 5415 employment 2019 -> 2024, %, as built by `build_metro_panel.py`), rows with `usable == True` only.
- **Coasts, by state** (state = the first state code after the comma in `metro_name`, the rule used in chapter 5,
  e.g. "New York-Newark-Jersey City, NY-NJ-PA" -> NY):
  West = WA, OR, CA. East = ME, NH, MA, RI, CT, NY, NJ, **PA**, DE, MD, VA, NC, SC, GA, FL and DC.
  PA is included because Philadelphia lies on the tidal Delaware estuary and PA is an Atlantic coastal-zone state (NOAA); without it,
  Philadelphia (first state PA) would fall out. The whole state counts, so inland metros (Sacramento, Spokane, Atlanta, Pittsburgh) are in;
  Florida's Gulf metros are East. AK and HI are not West Coast. Every other state is out of the test.
- **Withheld metros.** Metros without usable job growth (employment withheld in 2019 or 2024, or no quarter) are excluded and counted per
  coast in the results (East 30, West 4 at registration). Withholding is not random (Atlanta and Richmond are among the East ones), so the
  establishment secondary covers almost all metros.
- **Primary test.** Two-sided Mann-Whitney U (scipy, asymptotic with continuity correction) of `it_growth_pct`, West vs. East.
- **Effect and interval.** Difference in medians, West - East (percentage points), with a 95 % bootstrap interval (5,000 resamples of
  metros within each coast, percentile). Predicted sign: negative. Also reported: the probability that a random West metro grew more than a
  random East metro (U / (n_west * n_east)).
- **Why this test.** Growth rates of small metros have heavy tails (a metro going from 200 to 600 IT jobs is +200 %), so a rank test rather
  than a t-test on means; two-sided because the question in the feedback is whether the coasts differ.
- **Secondary.** (1) Size-weighted: aggregate growth per coast, sum(emp_it_2024) / sum(emp_it_2019) - 1, difference West - East with a
  bootstrap interval over metros (5,000); (2) only metros with at least 1,000 IT jobs in 2019 (Mann-Whitney); (3) establishment growth
  (`estab_growth_pct`, `usable_estab == True`, Mann-Whitney), which also covers most withheld metros. None can change the verdict.
- **Placebo.** Random coast labels: 1,000 times, draw groups of the same sizes (41 and 97 at registration) at random from **all** usable
  metros in the file (any state) and run the primary test; share with p < 0.05 (expected about 5 %).
- **Power.** With 41 and 97 metros, a shift of about 0.53 standard deviations (normal approximation, Mann-Whitney efficiency 0.955) is
  detectable with 80 % power, i.e. a probability of about 0.65 that a West metro beats an East metro. Smaller differences will usually be missed.
- **Limits.** A state list is crude (inland metros count as coast); NAICS 5415 is IT services, not software publishers or big tech; withheld
  metros are missing; growth over five years says nothing about why (Sun Belt migration, cost of living, remote work); not causal.

## Amendments
(none)
