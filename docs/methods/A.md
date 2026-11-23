# A: Did Slovenia's share of ICT specialists grow more than in most EU countries, 2021-2024? (round 1)

> Methods dossier (template `docs/methods/TEMPLATE.md`), written by Stream B after the run. Every number is copied from
> `reports/hypotheses_b_results.json` (section `A`), produced by `python -m analysis.hypotheses_b` on 2026-11-16. Follow-up questions from the
> milestone 3 review are answered here and in `docs/methods/A2.md` (catch-up) and the B1 exploratory figures (`11x_slovenija_*`).

## 1. Question and registration
- **Question.** From 2021 to 2024, did the share of ICT specialists in total employment grow more in Slovenia than in most EU countries?
- **Prediction.** Slovenia's change is above the other countries' (t > 0).
- **Registration.** `docs/hypotheses/PREREGISTRATION.md`, section "A", commit `1de58cb 2026-11-14 09:05:20 +0100`. Code and synthetic tests:
  `40f4e25 2026-11-16 16:25:36 +0100`; real run and results: `2744f82 2026-11-16 17:12:25 +0100`.
- **Amendments.** One, dated 2026-11-16, concerns B only (end of the QCEW sample); A is unaffected.
- **Known before registering.** "Not looked at before registration: Slovenia's ICT share relative to other EU countries" (disclosure section of
  the registration).

## 2. Data
| Dataset | Provider | URL | Retrieved | File in the repo | SHA-256 (first 12) | Period used | Unit / level |
|---|---|---|---|---|---|---|---|
| ICT specialists in total employment (`isoc_sks_itspt`) | Eurostat (EU Labour Force Survey) | https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/isoc_sks_itspt | 2026-10-30 (committed manifest) | `data/raw/eurostat_isoc_sks_itspt.csv` | `c63a1f9bfd71` | 2021 and 2024 (secondary 2019) | country-year, unit `PC_EMP` |

- Licence: "Eurostat: free reuse with attribution" (`data/manifest.json`). Re-create: `python collect.py --sources eurostat`.

## 3. From raw data to the test sample (every step, in order)
1. **Load** with codes as strings: 1,452 rows (37 geographies, 2004-2025, units `PC_EMP` and `THS_PER`). (`run` in `analysis/hypotheses_b.py`, line 391)
2. **Keep unit `PC_EMP`** and the 27 EU member states; the `EU27_2020` aggregate is used only in a secondary check. (`_a_wide`, line 56)
3. **Years.** 2021 (first year of the new survey regulation, flag `b` in every country) and 2024. A country "has" a year only if the value is a
   number; `_a_wide` raises if any of the 27 lacks one (none does).
4. **Variable.** change_c = share_c(2024) - share_c(2021), percentage points (`changes`, line 70).
5. **Flags.** Used as published and listed: SI 2024 is an estimate (`e`); 10 other countries have a flagged 2024 value (`secondary.flagged_cells`).
6. **Final sample: 27 countries** (Slovenia + 26 comparison countries).

## 4. The test
- **Primary.** Prediction-interval t test of Slovenia against the other 26: t = (x_SI - mean_others) / (sd_others * sqrt(1 + 1/26)), Student t
  with 25 df, two-sided (`pi_test`, line 76). Alpha 0.05 after Holm across A, B, C, D.
- **Why.** The question is whether one country is unusual relative to a group. A rank test alone cannot reach significance after Holm with
  27 units (smallest p = 1/27 = 0.037). The prediction interval accounts for Slovenia itself being a new draw (the 1 + 1/26 term).
- **Assumption checked.** Roughly normal spread of the 26 other changes: Shapiro-Wilk p = 0.12, so the primary p was not flagged as approximate.
- **Secondary.** Rank (27 of 27, rank p 1.0); 2019 -> 2024 (crosses the 2021 break): SI +0.40 vs. others +1.19 points, t = -1.45, p = 0.16,
  rank 27; relative change SI -10.4 % vs. others +13.3 % (rank 27); Slovenia minus EU27_2020: -0.90 points (EU27 +0.40).
- **Placebo.** The same test for each of the other 26 countries against the rest: 1 of 26 with p < 0.05 (Lithuania), **3.8 %**.
- **Power.** Slovenia must lie about 2.1 standard deviations from the others' mean to reach p < 0.05 before correction (registration).
- **Multiple testing.** Round 1 family A, B, C, D, Holm: A p 0.027 -> **0.107**.

## 5. Code
- Entry point `python -m analysis.hypotheses_b` (runs A and B, writes `reports/hypotheses_b_results.json` with `inputs_sha256`).
  Functions in `analysis/hypotheses_b.py`: `_a_wide` (56), `changes` (70), `pi_test` (76), `test_a` (92), `estimated_flags` (101),
  `secondary_a` (114), `placebo_a` (145), `run_a` (363).
- Synthetic tests (`tests/test_hypotheses_b.py`): `test_a_finds_a_planted_outlier`, `test_a_country_from_the_same_distribution_is_not_found`,
  `test_a_formula_matches_the_registration`, `test_a_missing_country_raises`, `test_a_rank_secondary_and_placebo`.
- Core computation:
```python
def pi_test(values: pd.Series, country: str) -> dict:
    """Prediction-interval test of one country against the rest: t = (x - mean) / (sd * sqrt(1 + 1/m)), t with m - 1 df."""
    x = float(values[country])
    others = values.drop(country).to_numpy(float)
    m = len(others)
    mean, sd = float(others.mean()), float(others.std(ddof=1))
    t = (x - mean) / (sd * math.sqrt(1 + 1 / m)) if sd > 0 else float("nan")
    p = float(2 * stats.t.sf(abs(t), df=m - 1)) if np.isfinite(t) else float("nan")
```

## 6. Results
| Quantity | Value |
|---|---|
| Slovenia's change 2021 -> 2024 (points) | -0.50 |
| mean (sd) of the other 26 | +0.58 (0.45) |
| t (25 df) | -2.35 |
| p (raw) | 0.027 |
| p (Holm, round 1) | 0.107 |
| predicted sign? | **no** (Slovenia's share fell; rank 27 of 27) |
| verdict | **not supported** |

The direction is the opposite of the prediction: Slovenia had the smallest change of all 27 countries.

## 7. How to read it, and its limits
- *Med letoma 2021 in 2024 se delež strokovnjakov IKT v Sloveniji ni povečal bolj kot drugje, temveč je padel (−0,5 odstotne točke), medtem ko je
  v povprečju drugih držav zrasel (+0,6). Po popravku za štiri hipoteze to ni dovolj močan dokaz, da Slovenija izstopa.*
- Limits: survey estimates (SI 2024 is `e`), the 2021 break restricts the window to three years, one country against 26 says nothing about why.

## Follow-up from the milestone 3 review (milestone 4)
**"Is the data normalised? Does Slovenia's small size matter?"** The measure is the share of ICT specialists in all employed persons (`PC_EMP`),
so country size is already divided out: a country with ten times more workers does not get a larger value for that reason. What normalising
does **not** solve: (1) the Labour Force Survey samples fewer people in a small country, so Slovenia's share has a larger sampling error (the
prediction-interval test treats all 26 others as equally precise); (2) one firm or a change in classification moves a small country's share more;
(3) the share falls if total employment grows faster than ICT employment, even when the number of specialists does not fall. Eurostat publishes
the absolute number (`THS_PER`): Slovenia had 46.5 thousand ICT specialists in 2021, 37.2 thousand in 2023, 42.9 thousand in 2024 and 45.2
thousand in 2025 (figure `11x_slovenija_stevilo`).

**"Was its level already high in 2021? Did its rise come earlier?"** (exploratory, `reports/hypotheses2_b_results.json`, section `B1`, no test):
- In 2021 Slovenia ranked **10th of 27** by level (4.8 %, EU-27 4.5 %); in 2019 14th, in 2024 24th. Its 2019-2020 mean ranks 13th, the middle.
- The rise did not come earlier: 2015 -> 2020 Slovenia gained +0.80 points, the other countries +0.87 on average (rank 15 of 27).
- **Timing matters:** 2021 was Slovenia's highest year (4.8 %); it fell to 3.8 % in 2023 and recovered to 4.5 % in 2025. A comparison that
  starts in 2021 starts at Slovenia's peak. The registered window was fixed by the 2021 break, not chosen for this reason.
- The catch-up test A2 (`docs/methods/A2.md`) finds no relation between start level and change across the EU (slope -0.025, p = 0.73), and
  the line fitted on the other 26 predicts +0.59 points for Slovenia: its starting level does not explain the fall.

## 8. Likely questions and answers
- **Why a prediction-interval t test and not a z-score?** The z-score ignores that the mean and sd of the 26 are estimated; the t with 25 df and
  the 1 + 1/26 factor account for that.
- **Is the data normalised?** Yes, as a share of total employment; see the follow-up section for what that does not solve.
- **Why start in 2021?** Eurostat changed the Labour Force Survey regulation in 2021 (flag `b`); comparing across the break mixes methods. The
  2019 -> 2024 secondary crosses it and gives the same rank (27).
- **Is Slovenia's 2024 value reliable?** It is flagged as an estimate (`e`). The 2025 value (4.5 %) is closer to 2021, so the size of the fall
  depends on the end year.
- **p = 0.027 is below 0.05: why "not supported"?** Two reasons: the effect has the opposite sign to the prediction, and Holm across four tests
  raises p to 0.107.
- **Could Slovenia's small sample alone produce such a change?** A swing of 0.5 points is within what small-country survey noise can produce
  (Slovenia fell by 0.7 points 2022 -> 2023 and rose by 0.5 points 2023 -> 2024); that is one reason not to over-read it.
