# B: Did IT employment in San Francisco fall relative to Austin after the first rate hike? (round 1)

> Methods dossier (template `docs/methods/TEMPLATE.md`), written by Stream B after the run. Every number is copied from
> `reports/hypotheses_b_results.json` (section `B`), produced by `python -m analysis.hypotheses_b` on 2026-11-16 (rerun after the amendment).

## 1. Question and registration
- **Question.** After the Fed's first rate hike (2022-03-16), did IT employment (QCEW, NAICS 5415) in the San Francisco metro fall relative to Austin?
- **Prediction.** b < 0 (the SF-Austin gap drops after 2022Q1).
- **Registration.** `docs/hypotheses/PREREGISTRATION.md`, section "B", commit `1de58cb 2026-11-14 09:05:20 +0100`. Code and synthetic tests:
  `40f4e25 2026-11-16 16:25:36 +0100`; real run, amendment and results: `2744f82 2026-11-16 17:12:25 +0100`.
- **Amendment 2026-11-16 (end of the sample = last published quarter).** The first run took the file's last row (2025Q4) as the end. The QCEW file
  holds placeholder rows for 2025Q3-2025Q4 in all metros (levels 0, disclosure code `-`, not yet published). They were already treated as missing,
  so **the primary estimate did not change**, but the placebo requires complete series to the end and found no metro. Fix: the end is the last
  quarter in which SF or Austin has a value (2025Q2). Test, sample rule and thresholds unchanged; regression test
  `test_unpublished_trailing_quarters_do_not_end_the_sample`.
- **Known before registering.** Metro growth 2019-2024 (Austin about +40 %, San Francisco about -2 %) from the milestone 2 comparison; "not looked
  at: the quarterly timing of IT employment in San Francisco vs. Austin around the first rate hike" (registration disclosure).

## 2. Data
| Dataset | Provider | URL | Retrieved | File in the repo | SHA-256 (first 12) | Period used | Unit / level |
|---|---|---|---|---|---|---|---|
| QCEW, state/county/metro, IT industries | US Bureau of Labor Statistics | https://www.bls.gov/cew/ | 2026-10-30 | `data/raw/bls_qcew_areas_it_industries.csv` | `fc05c681079c` | 2019Q1-2025Q2 | metro-quarter, NAICS 5415, private ownership |
| QCEW code crosswalk (2023 delineation) | own file | - | committed 2026-10-29 (`198b38d`) | `config/qcew_code_crosswalk.csv` | `66c31fc4083d` | - | old -> new area code |

- Licence: "US Bureau of Labor Statistics: public domain, please cite BLS" (`data/manifest.json`).
- Re-create: `python collect.py --sources qcew` (no key). The file is not committed (size); `data/raw/` is git-ignored.

## 3. From raw data to the test sample (every step, in order)
1. **Load** the QCEW area file as strings: 868,932 rows, years 2015-2026, of which 142,242 rows for industry 5415. (`run`, line 391)
2. **Select the two metros** (`qcew_area_codes`, line 154; `quarterly_series`, line 167): area `C4186` (San Francisco-Oakland, CBSA 41860) and
   `C1242` (Austin-Round Rock, CBSA 12420), industry `5415`, private ownership (filtered by the collector); crosswalk codes added where they map.
3. **Quarterly value** = mean of the three monthly employment levels; **missing** when `disclosure_code` is set (`N` or `-`) or any month is 0 or
   missing; never filled or zero.
4. **Sample end** = last published quarter (`last_published_quarter`, line 367): 2025Q2. Placeholder quarters 2025Q3-Q4 (code `-`) are excluded.
5. **Variable** (`_gap`, line 231): d_t = log(emp SF_t) - log(emp Austin_t), 2019Q1-2025Q2. post_t = 1 from 2022Q2.
6. **Final sample: 26 quarters** (13 pre 2019Q1-2022Q1, 13 post 2022Q2-2025Q2), no missing quarter in either series. SF 100,495 -> 91,780 jobs,
   Austin 39,202 -> 59,463 (2019Q1 -> 2025Q2).

## 4. The test
- **Pre-trend check (decides the model).** OLS of d_t on time over 2019Q1-2022Q1, classical t test: slope -0.024 log points per quarter,
  p = 0.00002 (significant), so **the linear trend was added as registered**; b then measures the break from the trend.
- **Primary.** d_t = a + b * post_t + c * t + e_t; Newey-West (Bartlett, 4 lags, small-sample factor n/(n-k)) standard error for b; Student t with
  23 df; two-sided (`test_b`, line 242; `newey_west`, line 203). Alpha 0.05 after Holm across A, B, C, D.
- **Why.** The quarterly gap is autocorrelated, so ordinary standard errors are too small; Newey-West corrects for that. Using the gap between the
  two metros removes national shocks that hit both.
- **Assumptions checked.** The Newey-West code matches statsmodels 0.15 (`OLS.fit(cov_type="HAC", ...)`) to numerical precision (test).
- **Secondary.** Without 2020Q1 (pandemic shock): b = -0.051 (-0.144 to +0.041), p = 0.26. Establishments instead of employment: b = -0.102
  (-0.317 to +0.112), p = 0.33. Trend added in both.
- **Placebo.** The same model for every pair among the 30 largest complete metros (2019 NAICS 5415 jobs), SF-Austin left out: 434 pairs;
  **29 % have p < 0.05** and 83 % get the trend. So this short design rejects far too often (a synthetic size test gives about 14 %). SF-Austin's
  |b| ranks 241 of 435; 55 % of pairs have |b| at least as large.
- **Power.** Limited by 13 + 13 quarters; the placebo shows the design is anti-conservative rather than underpowered, which is why B is weak even
  in principle.
- **Multiple testing.** Round 1 family A, B, C, D, Holm: B p 0.290 -> **0.579**.

## 5. Code
- Entry point `python -m analysis.hypotheses_b`. Functions in `analysis/hypotheses_b.py`: `qcew_area_codes` (154), `quarterly_series` (167),
  `ols` (196), `newey_west` (203), `ols_classic` (221), `_gap` (231), `test_b` (242), `placebo_metros` (286), `placebo_b` (309), `secondary_b` (337),
  `last_published_quarter` (367), `run_b` (376).
- Synthetic tests (`tests/test_hypotheses_b.py`): `test_b_finds_a_planted_drop_with_the_right_sign`, `test_b_no_break_mostly_not_found`,
  `test_b_trend_added_exactly_when_pretrend_is_significant`, `test_newey_west_matches_statsmodels_reference`,
  `test_newey_west_is_calibrated_in_a_long_series`, `test_registered_short_design_false_positive_rate_is_measured`,
  `test_quarterly_series_keeps_disclosed_quarters_missing`, `test_quarterly_series_applies_the_crosswalk`, `test_placebo_b_ranks_and_shares`,
  `test_unpublished_trailing_quarters_do_not_end_the_sample`.
- Core computation:
```python
    y = d.to_numpy()
    pt = ols_classic(y[pre], np.column_stack([np.ones(n_pre), time[pre]]))
    pretrend_p = float(pt["p"][1])
    trend_added = bool(pretrend_p < ALPHA)
    cols = [np.ones(ok.sum()), post[ok]] + ([time[ok]] if trend_added else [])
    r = newey_west(y[ok], np.column_stack(cols), lags=lags)
    b, se = float(r["beta"][1]), float(r["se"][1])
    crit = float(stats.t.ppf(0.975, r["df"]))
```

## 6. Results
| Quantity | Value |
|---|---|
| b, break from trend (log points; about -5 %) | -0.051 |
| 95 % interval | -0.150 to +0.047 |
| Newey-West se | 0.047 |
| p (raw) | 0.290 |
| p (Holm, round 1) | 0.579 |
| predicted sign? | yes |
| verdict | **not supported** |

Unexpected: the gap was already closing fast before the hike (Austin growing, SF flat), so most of the SF-Austin divergence predates 2022.

## 7. How to read it, and its limits
- *San Francisco je za Austinom zaostajal že pred zvišanjem obrestne mere: razlika se je zmanjševala že od leta 2019. Po zvišanju se ta trend ni
  opazno pospešil (ocena −5 %, a z razponom od −14 % do +5 %). Poleg tega tak kratek test pogosto najde »učinek« tudi tam, kjer ga ni.*
- Limits: two metros; NAICS 5415 is IT services, not software publishers or big tech; 26 quarters; the placebo rejects in 29 % of pairs.

## 8. Likely questions and answers
- **Why add a trend?** The registration said so in advance if the 2019-2022Q1 trend was significant; it was (p = 0.00002). Without it, b would
  mostly measure the earlier divergence.
- **Why Newey-West with 4 lags?** Quarterly data, one year of lags; fixed in the registration, not tuned.
- **What does the 29 % placebo mean?** Applied to random metro pairs, the design finds a "significant break" far more often than 5 %, so even a
  significant SF-Austin result would have been weak evidence. We report it rather than hide it.
- **What changed in the amendment?** Only the end of the sample (placeholder quarters); the primary estimate is identical before and after.
- **Why NAICS 5415 and not all tech?** It is the IT group that passed the metro feasibility test (235 of 407 metros usable, AGENTS.md section 7);
  the 6-digit codes, software publishers among them, failed it, and software publishers changed code (511210 -> 513210) in 2022.
- **Is the employment data complete?** Yes for both metros: no quarter withheld 2019Q1-2025Q2.
