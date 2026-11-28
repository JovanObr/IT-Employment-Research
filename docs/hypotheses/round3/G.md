# Round 3 pre-registration, Stream B: hypothesis G

Written 2026-11-27, **before any value of the vacancy data was printed, plotted or summarised**. Commit this file first; the commit is the
registration. Common rules: `docs/hypotheses/round3/README.md` (and rounds 1-2). Family: G, H (one Holm correction, m = 2).

## Design checks done before registration (metadata, counts and flags; no vacancy value)
Both tables were read through the Eurostat API on 2026-11-27 (the replies sit in the local cache, `data/cache/`, not in git); scripts printed
only dimension lists, counts of quarters and flags. Neither table was in the project before (checked: no `jvs_q_nace2` or `irt_st_m` file in
`data/raw/`, no entry in `data/manifest.json`, no reference in `analysis/`, `notebooks/`, `collectors/`; only the task and README files name them).
- **`jvs_q_nace2`** (job vacancy statistics, quarterly). The indicator code is **`JVR`** (job vacancy rate; the task's "JOBRATE" does not exist).
  Dimensions: `s_adj` (NSA, SA), `nace_r2` (30 codes incl. `J` and `B-S`), `sizeclas` (TOTAL, GE10), `indic_em` (JOBVAC, JOBOCC, JVR, JVRCH_Q).
  The unfiltered table is refused by the API (HTTP 413), so the collector filters `JVR`, `TOTAL`, `J` and `B-S`.
  - Section J, size class TOTAL, 2018Q1-2025Q2: **all 27 EU countries publish both NSA and SA**, 30 of 30 quarters each, except France
    (29: **2020Q1 missing**). GE10 is incomplete (25 NSA, 22 SA), so TOTAL is used.
  - Flags in section J (NSA, TOTAL, 2018Q1-2025Q2): `u` (low reliability) **Slovenia, 12 quarters**; `p` (provisional) HU 26 quarters
    (2019Q1 on), NL all 30, BG and MT 10 (2023Q1 on), DK 2 (2025); `b` (break) FI 2018Q1, CZ 2025Q1. No `e` flag.
  - `B-S` (industry, construction and services; Eurostat's headline total): 26 countries; **Denmark publishes no B-S series**; France has
    flag `d` (definition differs) throughout and misses 2020Q1; Sweden has a break `b` in 2024Q2.
- **`irt_st_m`** (money market interest rates, monthly), `IRT_M3` (3-month rate): euro area `EA` 1990-01 to 2026-10 (one `b` flag), CZ, HU,
  PL, RO to 2026-10, DK and SE to 2026-01. **Bulgaria's series ends 2018-06 and Croatia's 2019-12**, so neither has an own rate in the window.
  Also listed: UK, US, JP, TR, MK (not used).
- **Which countries carry the variation** (this is the exposure, not the outcome; printed once): root mean square of (own year-on-year change
  of the quarterly 3-month rate minus the euro area's), 2021Q1-2023Q4, percentage points: **HU 6.23, PL 3.32, CZ 3.08, RO 2.85**, SE 0.30,
  DK 0.17. So Sweden and Denmark follow the euro area closely (the task expected Sweden among the differing countries); **four countries
  (CZ, HU, PL, RO) carry almost all the information**, Hungary most of it.

## Disclosure (what was already seen)
From `docs/hypotheses/round3/README.md`, "What has already been seen":
- **Job postings by country (Indeed, software development):** notebook 01 printed the peaks: US 02/2022, United Kingdom 04/2022,
  Germany 05/2022, France 07/2022. That is why G does **not** use postings for its test.
- **Layoff announcements by region (tracker):** on 2026-11-25, while planning this round, quarterly counts for 2021-2023 were printed for
  Europe and the US: Europe went from 4 (2022Q1) to 31 (2022Q2), at the same time as the US (21 to 174), before the ECB's first hike
  (21 July 2022). That is why G does **not** use the tracker for its test either.
- **Not seen by anyone in the team before this registration:** Eurostat job vacancy statistics (`jvs_q_nace2`), Eurostat interbank rates
  (`irt_st_m`). Since then (design checks above): the counts and flags of the vacancy table, never a value; the rate table's coverage and the
  six root-mean-square numbers above. Central-bank decisions themselves are public knowledge (Czechia and Hungary began hiking in mid-2021,
  Poland in late 2021, the ECB in July 2022).
- The predicted sign (negative) comes from the reasoning in chapter 2 (dearer money, less hiring), not from these data.

---

## G. Own central bank vs. common shock
**Hypothesis.** Across EU countries, a rise in a country's own short-term interest rate is followed by a fall in its ICT job vacancy rate,
**beyond the change common to all countries in the same quarter**. Predicted: **b < 0**.

- **Code.** `collectors/eurostat_g.py` (`python collect.py --sources eurostat_g`, calls the existing `collectors.eurostat.collect` with two
  filtered datasets), `analysis/hypotheses3_b.py` (`python -m analysis.hypotheses3_b`; refuses to run unless this file is committed),
  results `reports/hypotheses3_b_results.json` (key `G`), tests `tests/test_hypotheses3_b.py`.
- **Data.** `data/raw/eurostat_jvs_q_nace2.csv` (indicator JVR, size class TOTAL, sections J and B-S, NSA and SA) and
  `data/raw/eurostat_irt_st_m.csv` (IRT_M3). Values as published.
- **Unit and period.** Country-quarter, the 27 EU countries, **2019Q1-2024Q4** (24 quarters; 648 country-quarters, 646 with an outcome
  because France's 2020Q1 is missing, which removes its 2020Q1 and 2021Q1 differences).
- **Outcome.** y(c,t) = v(c,t) - v(c,t-4): year-on-year change of the job vacancy rate in section J (information and communication),
  unadjusted (NSA) series for every country (all 27 have one; the year-on-year difference removes the seasonal pattern), percentage points.
- **Exposure.** x(c,t) = r(c,t-1) - r(c,t-5): year-on-year change of the country's 3-month rate one quarter earlier, percentage points.
  r = mean of the three monthly values of the quarter (a quarter with fewer than 3 months is missing).
  **Own rate:** CZ, DK, HU, PL, RO, SE (the six EU countries outside the euro area in 2019-2024 with a published 3-month rate).
  **Euro-area rate (`EA`) for all others, for the whole window, including Bulgaria and Croatia.** Change from the task's plan ("Croatia from
  2023-01"), made because of design check G1: Croatia's own series ends 2019-12 and Bulgaria's 2018-06, so neither can be used in
  2019-2024; both currencies were pegged to the euro (Bulgaria's currency board, Croatia's ERM II from July 2020), so their money-market
  rates had no independent path. Mixing an own series with the euro rate at a switch date would also create a false year-on-year jump.
- **Model.** OLS of y on x with **country and quarter fixed effects**. The quarter effects absorb everything common to all countries in a
  quarter (the Fed, the global tech cycle, the energy shock, the euro-area hikes as such), so b is identified only from countries whose own
  rate moved differently from the others: in practice CZ, HU, PL, RO.
- **Primary test.** b, two-sided p from a **restricted wild cluster bootstrap by country** (null b = 0 imposed, Rademacher weights,
  bootstrap-t with the CR1 cluster-robust standard error, **9,999 replicates**, p = (#|t*| >= |t| + 1) / 10,000). Kept as planned because
  the synthetic calibration below shows it holds its size (about 5 %) on this design; the standard cluster-robust p does not.
- **Effect and interval.** b in percentage points of vacancy rate per percentage point of rate rise; 95 % interval from the CR1 standard
  error with 26 degrees of freedom (reported; may be too narrow, see calibration).
- **Synthetic calibration (simulated outcomes only, run before this registration;** `analysis.hypotheses3_b.calibrate`, script output kept
  in the dossier). Outcome = country effect + quarter effect + b x + noise, the noise being the year-on-year difference of an AR(1) level
  series. 400 simulated panels per scenario, b = 0, share with p < 0.05 (CR1 t / wild bootstrap / randomization inference on t):

  | Scenario (noise) | real rate paths: CR1 / wild / RI-t | synthetic paths: CR1 / wild / RI-t |
  |---|---|---|
  | phi 0.5, equal noise | 18.0 / 4.0 / 5.0 % | 18.3 / 5.0 / 5.5 % |
  | phi 0.9 | 16.5 / 2.3 / 3.5 % | 14.3 / 3.0 / 3.5 % |
  | phi 0.7, noise differs by country (log-sd 0.5) | 15.5 / 2.3 / 3.5 % | 13.3 / 2.8 / 4.8 % |
  | phi 0.7, common shock moving with the rates | 16.3 / 3.3 / 4.5 % | 16.5 / 3.3 / 5.0 % |
  | phi 0.7, own-rate countries 2x noisier | 19.5 / 4.8 / 7.3 % | 20.8 / 8.8 / 8.5 % |
  | phi 0.7, own-rate countries 3x noisier + log-sd 0.5 | 19.3 / 5.5 / 9.0 % | 18.8 / 7.8 / 9.3 % |

  (400 panels each: the share has a standard error of about 1.1 points at 5 %. Bootstrap and permutation tests with 399 replicates
  in the calibration; "real rate paths" = the exposure built from `irt_st_m` as above, "synthetic" = `synthetic_rates`.)
  The cluster-robust t-test rejects a true null **13-21 %** of the time (few countries carry the variation), so it is reported only.
  With the real rate paths the wild cluster bootstrap stays at 2.3-5.5 % in every scenario, including a common shock that moves with the
  rates (absorbed by the quarter effects), so it remains the primary. It over-rejects mildly (7.8-8.8 %) only with synthetic paths and
  own-rate countries 2-3 times noisier than the rest; a p just under 0.05 should be read with that in mind. Randomization inference on t is reported as a secondary (it reaches 7-9 % when the own-rate countries are noisier); on b it
  over-rejects badly then (18-24 %), so it is not used.
- **Power.** By simulation from the design (real exposure paths, the same model and test): with noise of standard deviation 1 in the
  year-on-year outcome's level innovation and phi = 0.7, the smallest |b| found 80 % of the time is **0.61** (that noise gives a year-on-year sd of about 1.73, so the effect must be about a
  third of the outcome's noise sd per percentage point of rate rise; `power_search`, 100 panels and 199 bootstrap replicates per step). On the real scale it is
  computed by the code in the single run **before b is estimated** and logged: the per-country noise scale is taken from the two-way
  fixed-effect residuals of the outcome over **2015Q1-2018Q4** (before the window, no rate variation; phi = 0.7 assumed), then the same
  search (doubling, then bisection, 200 simulated panels per step). The 2019-2024 window includes COVID, so the real noise is probably
  larger and this power optimistic.
- **Secondary** (none can change the verdict):
  1. Lag 0 (x = r(t) - r(t-4)) and lag 2 instead of lag 1 (wild bootstrap p).
  2. Without countries with a `u` or `e` flag in any quarter entering an outcome (2018Q1-2024Q4): at registration only **Slovenia** (`u`).
  3. All industries (`B-S`) instead of section J (26 countries; Denmark has no B-S series): does ICT react more than the whole economy?
     b_J - b_BS is reported descriptively.
  4. Randomization inference: own-rate paths reassigned at random among the 27 countries (9,999 times), p on the CR1 t-statistic.
  5. Leave one out: b and its wild bootstrap p without each of the six own-rate countries in turn (Hungary may drive the result alone).
  6. Descriptive and **exploratory (seen data)**: the Indeed peaks by country and the tracker's Europe vs. US quarters next to the three
     first-hike dates (BoE 16 Dec 2021, Fed 16 Mar 2022, ECB 21 Jul 2022), **quoted from `docs/hypotheses/round3/README.md`, not
     recomputed** (the tracker is a manual download on Jovan's machine only).
- **Placebo.** The own-rate paths reassigned at random among the countries (1,000 times; each country gets another country's whole exposure
  path, the outcomes stay), the primary test re-run on each (999 bootstrap replicates); share with p < 0.05 (about 5 % expected).
- **Verdict.** Supported only if the Holm-adjusted p (m = 2, with H) < 0.05 and b < 0. H's p is 0.0001 (`reports/hypotheses3_a_results.json`),
  so Holm leaves G's p unchanged (G is compared with 0.05) unless G's p is the smaller one.
- **Synthetic tests** (`tests/test_hypotheses3_b.py`, all passing before this registration): data helpers (quarterly mean needs 3 months;
  euro countries take the EA rate; the lagged year-on-year exposure; outcome and flags on a hand-made file); the fixed-effect estimate equals
  the dummy regression; a planted b = -1 is found (>= 80 % of runs, all with the right sign); a null is not (<= 12 % in 80 runs); a common
  shock that moves with the rates is absorbed; the CR1 t over-rejects (kept so the reason stays documented); reassigned exposures keep the
  same set of paths; the whole run on fake files laid out like the Eurostat CSVs.
- **Limits.** A vacancy rate is not employment (it measures hiring demand); only four countries carry the variation, Hungary most of it,
  so the result rests on a few central-bank paths; the 3-month rate is a proxy for monetary policy; countries' rates partly respond to their
  own economy (reverse causation: an overheating labour market can push both vacancies and rates up, which would bias b towards zero or
  positive), which the one-quarter lag reduces but does not remove; Central and Eastern European countries may share a regional cycle that
  the quarter effects (common to all 27) do not absorb; section J includes publishing and telecoms, not only IT.

## Amendments
(none)
