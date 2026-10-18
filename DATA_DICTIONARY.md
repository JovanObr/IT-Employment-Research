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
