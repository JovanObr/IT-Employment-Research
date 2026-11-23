# F: Did IT job growth 2019-2024 differ between East Coast and West Coast metros? (round 2)

> Methods dossier (template `docs/methods/TEMPLATE.md`), written by Stream B after the single real run. Every number is copied from
> `reports/hypotheses2_b_results.json` (section `F`), produced by `python -m analysis.hypotheses2_b` on 2026-11-23.

## 1. Question and registration
- **Question.** Did employment in IT services (QCEW, NAICS 5415) grow differently from 2019 to 2024 in US metro areas on the West Coast than
  on the East Coast?
- **Prediction.** Two-sided test; predicted direction: **lower growth on the West Coast** (West - East < 0).
- **Registration.** `docs/hypotheses/round2/A2_F.md`, section "F", commit `fdd6e00 2026-11-23 16:42:14 +0100`. Code and synthetic tests:
  `e79b61e 2026-11-23 16:47:29 +0100` (before the run). Results: `7ac6b78 2026-11-23 16:50:06 +0100`.
- **Amendments.** None.
- **Known before registering (copied from the disclosure).** Chapter 5 of notebook 08 and notebook 09: regional medians by Census region (whose
  "West" includes the Mountain states and whose "South" includes Texas), the map, and single metros (Austin about +40 %, San Francisco about
  -2 %; Boston, Los Angeles, San Diego, Philadelphia lost IT jobs; Miami, Orlando, Tampa, Charlotte, Seattle grew). The coast groups were never
  formed or compared. The predicted sign was chosen from that knowledge, so it is not a blind prediction.

## 2. Data
| Dataset | Provider | URL | Retrieved | File in the repo | SHA-256 (first 12) | Period used | Unit / level |
|---|---|---|---|---|---|---|---|
| Metro map table (derived) | built from BLS QCEW + Census Gazetteer (+ one Census ACS column, not used here) | - | file committed 2026-11-02 (`9f77f90`) | `data/processed/metro_map_data.csv` | `91591938b86d` | 2019 and 2024 (quarterly means) | metro area (CBSA) |
| QCEW, state/county/metro, IT industries (source of the table) | US Bureau of Labor Statistics | https://www.bls.gov/cew/ | 2026-10-30 | `data/raw/bls_qcew_areas_it_industries.csv` | `fc05c681079c` (round 1 hash) | 2019, 2024 | area-quarter, NAICS 5415, private |
| Gazetteer CBSA centroids (names only matter here) | US Census Bureau | https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_cbsa_national.zip | 2026-10-30 | `data/raw/census_gazetteer_cbsa.csv` | - | 2023 delineation | CBSA |

- Licences: BLS "public domain, please cite BLS"; Census "public data, please cite the US Census Bureau" (`data/manifest.json`).
- Re-create: `python collect.py --sources qcew gazetteer acs5` (ACS needs `CENSUS_API_KEY`), then `python build_metro_panel.py`, then
  `python -m analysis.geo mapdata`. The test reads only the committed `metro_map_data.csv`, so it can be rerun without any key.

## 3. From raw data to the test sample (every step, in order)
1. **QCEW rows** (`load_qcew` in `build_metro_panel.py`, line 84): metro codes `C####`, years 2015, 2019, 2024, industries 5415 and 10. Code
   changes of the 2023 delineation are joined through `config/qcew_code_crosswalk.csv`. A quarter's employment is the mean of its three monthly
   levels; it is **missing** when `disclosure_code == "N"` or the third month is 0 (withheld), never zero.
2. **Yearly levels** (`_growth_inputs`, line 51): mean over the quarters reported in **both** 2019 and 2024 (at least 2 such quarters:
   `matched`, 243 metros); otherwise the mean of whatever quarters exist in each year (`unmatched`, 20 metros); otherwise none (140 metros).
3. **Outcome** (`build`, line 204): `it_growth_pct = (emp_it_2024 / emp_it_2019 - 1) * 100`; `usable = emp_it_2019 and emp_it_2024 both present`
   (line 210). The panel has 403 metros, 263 usable.
4. **Map table** (`analysis/geo.py` `load_geo_panel` line 63, `map_data` line 196): same 403 rows, columns kept, names from Census.
5. **Coast** (`state_of`, `coast_of` in `analysis/hypotheses2_b.py`, lines 203 and 211): the first two-letter state after the first comma of
   `metro_name`. West = WA, OR, CA; East = ME, NH, MA, RI, CT, NY, NJ, PA, DE, MD, VA, NC, SC, GA, FL, DC. Everything else is out (125 usable
   metros in other states). Lewiston, ID-WA and Chattanooga, TN-GA are out (first state not a coast state); Portland, OR-WA is West;
   New York (NY-NJ-PA), Philadelphia (PA-NJ-DE-MD) and Washington (DC-VA-MD-WV) are East.
6. **Withheld metros dropped** (`test_f`, line 247): West 4, East 30 (listed in `F.withheld`: e.g. Atlanta, Richmond, Jacksonville, Durham,
   Virginia Beach, Spokane, Bend).
7. **Final sample: West 41 metros, East 97 metros**, growth 2019 -> 2024. IT jobs in 2019: West 379,856, East 679,005.

## 4. The test
- **Primary.** Two-sided Mann-Whitney U (`scipy.stats.mannwhitneyu`, asymptotic, continuity correction), West vs. East. Effect: difference in
  medians West - East with a 95 % bootstrap interval (5,000 resamples within each coast, percentile). Alpha 0.05 after Holm.
- **Why.** Growth rates of small metros have heavy tails (East ranges from -62 % to +334 %, West from -51 % to +244 %), so a rank test; the
  question in the feedback is whether the coasts differ, so two-sided.
- **Assumptions.** Independent metros (neighbouring metros can share shocks: the p-value may be a little too small, not too large); the
  rank test compares whole distributions, the median difference is the reported effect.
- **Secondary** (cannot change the verdict): size-weighted aggregate growth per coast; only metros with at least 1,000 IT jobs in 2019;
  establishment growth (never withheld, so it covers most withheld metros).
- **Placebo.** 1,000 times: random groups of 41 and 97 drawn from all 263 usable metros (any state), same test. False-positive rate **4.2 %**.
- **Power (from the counts).** With 41 and 97 metros, a shift of 0.53 standard deviations (probability 0.65 that a West metro beats an East
  metro) is detectable with 80 % power. Observed: probability 0.44, i.e. a shift well below that.
- **Multiple testing.** Round 2 family A2, F, C2, E, Holm. Raw p: E 0.0002, C2 0.0009, F 0.292, A2 0.734. Holm-adjusted F: **0.585**.

## 5. Code
- Entry point: `python -m analysis.hypotheses2_b`. Functions in `analysis/hypotheses2_b.py`: `state_of` (203), `coast_of` (211), `f_data` (220),
  `mann_whitney` (237), `mde_d` (242), `test_f` (247), `weighted_growth` (264), `secondary_f` (268), `placebo_f` (288), `run_f` (299).
- Synthetic tests (`tests/test_hypotheses2_b.py`): `test_coast_by_first_state` (10 cases incl. multi-state metros, Portland OR vs. ME, Hawaii),
  `test_f_finds_a_planted_west_shortfall` (planted -30 points with heavy-tailed noise found, interval below zero, withheld counted),
  `test_f_null_is_not_found` (30 null data sets, at most 15 % rejected), `test_f_placebo_rate_near_five_percent`,
  `test_f_weighted_growth_is_aggregate_growth`, `test_f_secondary_sections`, `test_mde_for_registered_counts`.
- Core computation:
```python
def test_f(g: pd.DataFrame, n_boot: int = 5000, seed: int = 0, col: str = "it_growth_pct", usable: str = "usable") -> dict:
    """Primary test F (registered): Mann-Whitney West vs. East; difference in medians with a bootstrap interval (within coast)."""
    u = g[g[usable] & g[col].notna()]
    w, e = u.loc[u["coast"] == "west", col].to_numpy(float), u.loc[u["coast"] == "east", col].to_numpy(float)
    rng = np.random.default_rng(seed)
    mw = mann_whitney(w, e)
    boots = [_median_diff(rng.choice(w, len(w)), rng.choice(e, len(e))) for _ in range(n_boot)]
    diff = _median_diff(w, e)
```

## 6. Results
| Quantity | Value |
|---|---|
| median growth West (n = 41) | +2.0 % |
| median growth East (n = 97) | +12.7 % |
| difference in medians, West - East (percentage points) | -10.7 |
| 95 % interval (bootstrap) | -25.4 to +14.5 |
| Mann-Whitney U; P(West metro > East metro) | 1,762; 0.44 |
| p (raw) | 0.292 |
| p (Holm, round 2) | 0.585 |
| predicted sign? | yes |
| verdict | **not supported** |

- **Secondary.** Size-weighted: West -2.9 %, East +0.2 %, difference -3.0 points (-13.3 to +5.9). Metros with at least 1,000 IT jobs: West 15,
  median -9.8 %; East 44, median -0.9 %; p = 0.096. Establishments: West 44 metros, median +25.9 %; East 117, median +43.3 %; difference -17.4
  (-30.8 to +6.4), p = 0.117. All point the same way (West below East), none is significant.
- **Biggest metros.** West: San Francisco -2.1 %, San Jose -2.6 %, Los Angeles -11.8 %, Seattle +15.2 %, San Diego -10.2 %. East: Washington
  -4.1 %, New York +4.5 %, Boston -18.4 %, Philadelphia -9.9 %, Baltimore -2.1 %, Miami +32.7 %.

## 7. How to read it, and its limits
- *V tipičnem mestu na zahodni obali so IT delovna mesta 2019-2024 zrasla za 2 %, na vzhodni za 13 %. Razlika je v pričakovani smeri, a premajhna
  glede na to, kako zelo se mesta med sabo razlikujejo: lahko je naključje. Velika središča na obeh obalah (San Francisco, Boston, Washington)
  so stagnirala ali izgubila; rast je bila v manjših mestih na jugovzhodu.*
- Limits: a state list is crude (Atlanta, Pittsburgh, Sacramento count as coast); 30 East metros (among them Atlanta) are withheld; NAICS 5415
  is IT services, not big tech or software publishers; five-year growth says nothing about why; not causal.

## 8. Likely questions and answers
- **Why Mann-Whitney and not a t-test?** Small metros can grow by +200 % or more; one such metro moves a mean a lot and a rank not at all.
- **Why is the difference of 10 points "not significant"?** Metros differ hugely within each coast (sd about 50-60 points); with 41 and 97 metros
  the interval runs from -25 to +15 points. We can say the West did not grow much more than the East; we cannot rule out "the same".
- **Why include Pennsylvania?** Philadelphia sits on the tidal Delaware estuary and PA is an Atlantic coastal-zone state; without it Philadelphia
  would drop out. Decided before the run, in the registration.
- **What about the withheld metros?** They are missing (30 East, 4 West). The establishment secondary covers almost all of them and gives the same
  direction, also not significant.
- **Big cities count as much as small towns?** In the primary yes (one metro, one vote). The size-weighted secondary counts jobs instead: -3.0
  points, interval -13 to +6.
- **Does this tell us remote work moved jobs east?** No. It compares two groups of places over five years; causes are not tested.
