# Master file: `data/processed/it_employment_master.csv`

Long ("tidy") format: **one row = one observation** of one metric for one series at one date.
Values are as reported (only unit conversions, e.g. persons -> thousands; Indeed daily -> monthly mean).
Built by `python build_master.py`; mapping of codes to company types is in `config/segment_map.csv` (edit freely).

## Columns
| Column | Meaning |
|---|---|
| `date` | Start of the period (YYYY-MM-DD). Annual = 1 Jan, quarterly = first day of quarter. |
| `frequency` | `A` annual, `Q` quarterly, `M` monthly |
| `region` | `US`, `Europe`, or `Global` (Hacker News only). `Other` is dropped unless `--include-other` |
| `country` | ISO-2 code (GR, GB used, not EL/UK). For Eurostat aggregates: the Eurostat code (e.g. `EU27_2020`) |
| `area_level` | `country` or `aggregate`. **Exclude `aggregate` when summing across countries.** |
| `segment_group` | Comparable company-type bucket (from the segment map) |
| `segment` | Source-faithful label (e.g. "Games & entertainment software development") |
| `industry_code` | Native code (NAICS, SIC 2007, NACE, CES series id, Indeed/layoffs category) |
| `granularity` | `total`, `sector`, `aggregate` (overlaps its parts), `detailed` (non-overlapping finest level) |
| `metric` | see below |
| `value`, `unit` | the number and its unit (one unit per metric) |
| `breakdown` | extra dimension as `key=value;...`; blank = everyone / total |
| `source`, `dataset` | provenance (`dataset` names the raw file / table) |
| `series_id` | `dataset|industry_code|country|breakdown|metric`; with `date` it is the unique key |
| `quality_flag` | `series_break`, `partial_month`, or an Eurostat flag (b = break, p = provisional, e = estimated, u = low reliability) |
| `notes` | caveats for that series |

## Metrics
`employment_level` (thousand persons) · `employment_share_pct` (% of total employment) · `establishments` (count) ·
`avg_weekly_wage` (USD) · `job_postings_index` (Indeed, 1 Feb 2020 = 100) · `layoff_events` (events) ·
`layoff_headcount` (persons; blank when no event in the group reported a number) · `layoff_events_missing_headcount` (events) ·
`hn_posts` (count of Hacker News job posts) · `hn_post_share` (% of posts mentioning a flag or skill; the flag/skill is in `segment`)

## Rules that prevent wrong answers
1. **Sum only within one dataset, and only `granularity == 'detailed'`.** `aggregate` rows contain their sub-codes.
2. **Never mix datasets for levels.** Eurostat (occupations/LFS), BLS (industries/establishment surveys) and ONS (business register) use different definitions. Compare indexed trends.
3. **Software publishers (US):** NAICS 511210 until 2021 Q4, 513210 from 2022 Q1. The first 2022 row is flagged `series_break`; the jump (about +6% employment, +11% establishments in one quarter) is mostly reclassification.
4. **UK:** Eurostat's UK series ends in 2019; use `ons_bres` (Great Britain, annual, 2015+) afterwards. BRES counts are **rounded** for disclosure control (steps of 250 / 1,000), so small codes look steppy.
5. **UK BRES "Employment"** (employees + working owners) has a blank `breakdown` and is the one comparable with Eurostat; other statuses carry `employment_status=...`.
6. **Indeed** starts Feb 2020 (index = 100): there is no pre-COVID history. The latest month is flagged `partial_month`.
7. **Layoffs** are crowdsourced, list only companies with reported layoffs (no negatives), and ~1/3 of events lack a headcount; prefer `layoff_events`.
8. `All industries` rows with `dataset = layoffs_tracker` are the sum over tracker industries for that country-month, not an official total.
9. **Eurostat flags are frequent** (`e` estimated, `u` low reliability, `b` break in series, `d` definition differs; can be combined, e.g. `be`). Check `quality_flag` before reading a year-to-year jump as real, and treat `b` rows as possible discontinuities.
10. **Layoffs have no gaming label.** The tracker's industries (Consumer, Media, Other...) can't isolate game studios; that needs company-name matching.


## `data/raw/sec_financials_quarterly.csv` (source `sec_fin`, long format)
`cik` · `period` (calendar-aligned XBRL frame, e.g. `CY2022Q1`; balance-sheet items end in `I`, e.g. `CY2022Q1I`; Q4 flows are `CY2022Q4`) ·
`concept` (`net_income`, `operating_income`, `gross_profit`, `rnd`, `sga`, `cash`, `assets`, `equity`) · `value` (USD) ·
`kind` (`quarter`, `annual`, `instant`, `derived_q4` = annual minus Q1..Q3) · `tag` (the us-gaap tag used; `derived` for Q4).
Frames are calendar-aligned approximations (a June fiscal year is mapped to the nearest calendar quarter). Only companies in `sec_company_matches.csv` are kept.

## `data/raw/sec_universe_sic.csv` (source `sec_universe`)
One row per company: every SEC filer with at least 8 quarters of revenue in the XBRL frames, plus every company matched to a tracker layoff.
`cik` · `name` · `sic` (text, 4 digits) · `sic_description` · `ticker` (first listed, blank if none) · `is_tech` (SIC 3570-3579, 3661-3669, 3670-3679, 7370-7379) ·
`matched_layoff` (company matched to a layoff-tracker company) · `in_universe` (`is_tech` or `matched_layoff`; matched companies outside the tech list stay in as positives) ·
`revenue_quarters` (quarters of revenue in the frames, Q4 derived). Blank `sic` = no submissions file found.

## `data/processed/company_panel.csv` (`python -m analysis.company_panel`)
One row per technology company (`is_tech`) and calendar quarter `t`. `quarter`/`qi` (quarter index) · `name`, `ticker`, `sic`, `sic2` ·
`revenue_lagged` · features, all computed from filing quarter `t-1` (reports for `t` are not yet public at the end of `t`):
`rev_yoy`, `rev_qoq`, `gross_margin`, `op_margin`, `rnd_ratio`, `sga_ratio`, `cash_assets`, `log_assets`, `net_loss` (NaN when an input or a positive denominator is missing) ·
`y_next2q` = at least one tracker layoff of the company in quarters `t+1` or `t+2`. Rows whose label window is not fully inside the tracker's observed period are dropped.

## `data/raw/sec_revenue_universe.csv` (written by `sec_universe`)
Same columns as `sec_revenue_quarterly.csv` (`cik, period, revenue, tag, kind`) but for every company in `sec_universe_sic.csv` with `in_universe` (tech companies + matched layoff companies). `sec_fin` and the company panel read this file; run order: `layoffs`, `sec`, `sec_universe`, `sec_fin`, then `python -m analysis.company_panel`.

## Added by Stream B (text, geography)
- `data/processed/hn_topics_monthly.csv`: `month` (YYYY-MM, the thread month), `topic` (label `T<n>: top terms`, or a hand-written name), `share` (share of that month's posts whose strongest NMF topic it is; sums to 1 per month). Startup-skewed sample; topics depend on k (default 10) and the seed.
- `data/raw/census_gazetteer_cbsa.csv`: `cbsa_code` (5-character string), `name`, `lsad`, `lat`, `lon` (internal point, 2023 delineation), `aland_sqmi`.
- `data/processed/metro_panel.csv`, new column `emp_it_2019_reported`: mean 2019 IT employment over the 2019 quarters that are reported, even when 2024 is withheld (so no growth exists). Used only to size map bubbles; use `emp_it_2019` for anything quarter-matched.
- `data/processed/qcew_metro_code_stability.csv` (written by notebook 06): QCEW metro codes (`C####`) present in only one of 2019 and 2024, with the years each appears in.
