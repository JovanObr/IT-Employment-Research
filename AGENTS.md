# AGENTS.md: handoff for coding agents

Read this first. It tells you what the project is, what is already built, how it was built, which mistakes were already made (so you don't repeat them), and what to do next. Keep it up to date (see section 13).

## 1. The project in six lines

- **Question:** how did the post-COVID tech boom and bust change *where* IT work happens (geography), *what skills* it asks for (job-posting text), and *who* gets laid off and why (layoffs and causes)? US and Europe, 2015 to 2026.
- **Data:** only public/official sources via APIs or published downloads (Eurostat, BLS, ONS, Indeed, Hacker News, a layoffs tracker, SEC, FHFA, Census). Nothing is scraped from sites whose terms forbid it.
- **Pipeline:** `collect.py` downloads → `build_master.py` merges everything into one long-format CSV → `build_metro_panel.py` builds a per-metro table → notebooks and `analysis/` explore and model.
- **Status:** data foundation done and validated; all three feasibility tests passed; first descriptive results and a first metro regression exist; the layoff-risk model, NLP and causal tests are **not started**.
- **People:** two students (a second one is joining now). Everything user-facing exists in English and Slovenian (notebooks, explainer, summary).
- **Current work split (week of 21 to 27 Oct 2026):** two streams in parallel, see `docs/WORKSTREAMS.md`; your task brief is in `docs/tasks/`; progress is tracked in `docs/STATUS.md`. The repository is the only shared channel.
- **Tone of the work:** honest about limits. Thresholds are set before looking at results. Do not oversell associations as causes.

## 2. Run it

Run everything **from the project root** (paths are relative; `DATA_DIR` overrides `data/`).

Environment variables (PowerShell: `$env:NAME="value"`; bash: `export NAME=value`):

| Variable | Needed for |
|---|---|
| `CONTACT_EMAIL` | **required for SEC**; goes into the User-Agent of every request (good practice for all sources) |
| `CENSUS_API_KEY` | **required for Census**; free at api.census.gov/data/key_signup.html |
| `BLS_API_KEY` | optional (free), raises BLS limits |
| `DATA_DIR` | optional; overrides the `data/` folder (handy for tests) |

```bash
pip install -r requirements.txt            # pandas, requests, matplotlib, jupyterlab
python collect.py                          # every source (layoffs needs a manual CSV, see section 4)
python collect.py --sources qcew fhfa acs5 # any subset; --start-year 2015 is the default; -v for debug
python build_master.py                     # -> data/processed/it_employment_master.csv + master_validation.txt (exit code 1 on a hard failure)
python build_metro_panel.py                # -> data/processed/metro_panel.csv
jupyter lab notebooks/                     # 01_first_look, 02_geography (+ _SL Slovenian copies)
python -m compileall -q .                  # cheap syntax check
```

Valid `--sources`: `eurostat bls qcew nomis hn sec fhfa acs acs5 indeed layoffs`.
Responses are cached in `data/cache/` (default 7 days; QCEW/ACS/SEC 30). To force a refresh delete the relevant cache files.

## 3. Repository map

| Path | What it is |
|---|---|
| `collect.py` | CLI; one entry per source in the `SOURCES` dict |
| `collectors/common.py` | `fetch()` (cached, polite, retrying HTTP), `session()`, `record()` (manifest entry), data paths |
| `collectors/*.py` | one module per source (see section 4) |
| `build_master.py`, `masterfile/` | master-file builder: `schema.py` (columns, country codes, segment map loader), `adapters.py` (one function per source), validation |
| `config/segment_map.csv` | **editable** map: source code → comparable `segment_group`, `segment`, `granularity` |
| `config/company_aliases.csv` | layoffs company name → SEC ticker or CIK |
| `config/msad_parent.csv` | FHFA metropolitan division name → parent metro code and name |
| `build_metro_panel.py`, `analysis/metro_models.py` | metro table; robust OLS and repeated cross-validation |
| `notebooks/` | `01_first_look`, `02_geography`, and Slovenian copies `01_prvi_pogled_SL`, `02_geografija_SL` |
| `DATA_DICTIONARY.md`, `DATA_SOURCES.md`, `README.md` | schema and rules; licences and attribution; setup |
| `data/` | `raw/` (per-source CSVs), `processed/` (master, metro panel, layoffs_clean), `manual/` (hand-downloaded files), `cache/`, `manifest.json` |

`data/raw`, `data/cache`, `data/manual` and `data/processed/layoffs_clean.csv` are git-ignored (size and licences). Re-create them with `collect.py`.

## 4. Sources: collector, output, and the catch

| Source | Collector → file | The catch |
|---|---|---|
| Eurostat (ICT specialists, employment by NACE) | `eurostat.py` → `eurostat_*.csv` | JSON-stat API; **UK series ends 2019**; many flags (`b` break, `e` estimate, `u` unreliable). Dimension columns vary by dataset |
| BLS CES (monthly US employment) | `bls.py` → `bls_ces_employment.csv` | not seasonally adjusted (CEU series); IDs may need adjusting if a series returns no data |
| BLS QCEW (quarterly, by detailed NAICS and area) | `qcew.py` → `bls_qcew_it_industries.csv` (national) and `bls_qcew_areas_it_industries.csv` (~870k rows, state/county/metro) | **employment is often withheld** (`disclosure_code == "N"`, value shown as 0) while the establishment count is still reported; NAICS software publishers change code 511210 → 513210 at 2022Q1; industries collected include `5415` and `10` (total) |
| ONS BRES via Nomis (UK jobs by 5-digit SIC) | `nomis.py` → `nomis_bres_it_industries.csv` | Great Britain only; counts are **rounded**; dataset id is looked up by name (`NM_189_1`); the only place game development (SIC 58210, 62011) is visible |
| Indeed Hiring Lab | `indeed.py` → `indeed_*.csv` | index base 1 Feb 2020 = 100, so no pre-COVID history; exact sector name is "IT Infrastructure, Operations & Support" (an old typo silently dropped it) |
| Hacker News "Who is hiring?" | `hn.py` → `hn_whoishiring_posts.csv` (flags) and `hn_whoishiring_text.csv` | Algolia API, one request per monthly thread; startup-skewed; keyword rules ignore negation; **do not redistribute raw text** |
| Layoffs tracker | `layoffs.py` reads **`data/manual/*layoff*.csv`** → `data/processed/layoffs_clean.csv` | downloaded by hand (Kaggle copy of Layoffs.fyi); lists only companies *with* layoffs; ~1/3 of events lack a headcount; no gaming industry label |
| SEC EDGAR | `sec.py` → `sec_company_matches.csv`, `sec_revenue_quarterly.csv` | needs `CONTACT_EMAIL`; XBRL "frames" API (one request per tag and period); see section 9 |
| FHFA house prices | `fhfa.py` → `fhfa_hpi_metro_quarterly.csv` | the CSV has **no header row**; big metros are published as divisions (MSAD) |
| Census ACS | `census_acs.py` → `census_acs1_metro.csv` / `census_acs5_metro.csv` | **needs an API key**; 1-year data is missing for ~half of areas, so use `acs5` |

## 5. The master file contract

`data/processed/it_employment_master.csv`: long format, one row per observation. About 28k rows plus ~3.5k Hacker News rows. Columns (18):
`date, frequency, region, country, area_level, segment_group, segment, industry_code, granularity, metric, value, unit, breakdown, source, dataset, series_id, quality_flag, notes`.

- `(series_id, date)` is the unique key. `series_id = dataset|industry_code|country|breakdown|metric`.
- `region` is `US`, `Europe` or `Global` (Hacker News). Non-US/Europe rows are dropped unless `--include-other`.
- Datasets: `eurostat_isoc_sks_itspt/itsps/itspa/itspe`, `eurostat_lfsa_egan22d`, `bls_ces`, `bls_qcew`, `ons_bres`, `indeed_aggregate`, `indeed_it_sector`, `layoffs_tracker`, `hn_whoishiring`.
- Metrics: `employment_level` (thousand persons), `employment_share_pct`, `establishments`, `avg_weekly_wage`, `job_postings_index`, `layoff_events`, `layoff_headcount`, `layoff_events_missing_headcount`, `hn_posts`, `hn_post_share`. **One unit per metric** (validated).
- **Summing rule:** sum only within one `dataset` and only `granularity == "detailed"`; exclude `area_level == "aggregate"` (EU27 etc.). Aggregate rows overlap their parts.
- Values are **as reported**; indexing and baselines belong in analysis. Do not resample annual data to months.
- Unknown codes show up as `(unmapped)` in `master_validation.txt`; fix them in `config/segment_map.csv`, never by dropping rows.
- `quality_flag`: `series_break` (QCEW 2022Q1), `partial_month`, or Eurostat flags.

To add a source: collector (with `record()` and licence; register it by defining `SOURCES = {"name": lambda args: [...]}` at module level in `collectors/<module>.py`: `collect.py` discovers it, **do not edit `collect.py`**) → adapter in `masterfile/adapters.py` → rows in `config/segment_map.csv` → add to `build_master.py` → update `DATA_DICTIONARY.md` and `DATA_SOURCES.md` → check `master_validation.txt` shows no FAIL.

## 6. Metro panel and analysis

`build_metro_panel.py` → one row per US metro (CBSA code as a **5-character string**; QCEW code `C1698` = CBSA `16980`).

- IT = **NAICS 5415** (IT consulting and contract services; *not* software publishers or big tech).
- **Outcome A: IT employment growth 2019→2024.** Suppression is erratic, so it compares quarters reported in both years (need ≥2) and falls back to the mean of whatever quarters exist (≥1 per year), flagged in `emp_basis` (`matched` / `unmatched` / `none`).
- **Outcome B: IT establishment growth 2019→2024.** Establishment counts are never withheld, so this covers 372 of 408 metros and all 25 biggest.
- Features: pre-trend, IT location quotient, average establishment size, Census (work-from-home share and change, education, population, income, rent, age) and FHFA house-price growth. The builder prefers `census_acs5_metro.csv` over the 1-year file.
- FHFA divisions are mapped to their parent metro through `config/msad_parent.csv` (by exact name) and averaged unweighted; the builder warns about unmapped division names.
- `analysis/metro_models.py`: `prepare()` (log outcomes and predictors), `fit()` (OLS on standardised predictors, HC1 robust SEs), `cv_r2()` (repeated 5-fold), `run(panel, "A"|"B")`.

## 7. Feasibility tests (thresholds fixed before looking at results)

Rule: continue if at least 2 of 3 pass. **Do not change thresholds after the fact.**

| Test | Threshold | Result |
|---|---|---|
| Metro data (QCEW) | ≥150 metros usable in 2019 and 2024 | 6-digit IT codes: 144 / 165 / 110 (narrow fail); retest with 4-digit group 5415 (announced before the result): **235 of 407, pass** |
| Hacker News text | ≥40,000 posts and ≥5 pp change in "remote" share 2019 vs 2021 | **81,514 posts, +48.4 pp, pass** |
| SEC company panel | ≥250 layoff events from companies matched to SEC filers with ≥8 quarters of revenue | **538 events from 194 companies, pass** (973 Post-IPO events in scope, 551 matched) |

## 8. Results so far (descriptive, not causal)

- Indeed software-developer postings peaked Feb 2022 (US 229, base Feb 2020 = 100) and fell 61–71% by 2026 in US/DE/FR/GB; the US has recovered somewhat since mid-2025, Europe has not.
- Layoff events came in two waves: a short COVID shock in spring 2020 and a longer correction in 2022–2023. US events in the tracker: 455 (2020), 32 (2021), 731 (2022), 860 (2023).
- US IT-services employment (QCEW) peaked Q4 2022 (~2.51M) and is ~5.6% below by early 2026; EU ICT-specialist share rose from 4.0% (2019) to 5.0% (2025). Hiring demand fell much more than employment: **the central open puzzle.**
- Hacker News: "remote" share 32% (2019) → 83% (2022) → 54% (2026); AI/ML mentions 17.6% (2022) → 57% (2026); junior mentions were already falling before AI (10% in 2015 → 7% in 2019 → ~5%).
- Geography: employment model explains ~38% in-sample and **~28% out-of-sample** (n=233); the only robust predictor is average IT establishment size (larger → slower growth). Establishment growth is barely predictable (CV R² ≈ 0.04; only median income is robust). Work-from-home change shows no robust link.
- Sun Belt/Mountain metros (Dallas, Denver, Miami, Orlando, Tampa, Charlotte, Seattle) grew on both outcomes; Boston, Detroit, Los Angeles, Philadelphia, San Diego lost IT jobs but added establishments.
- IT employment is **unavailable** for Chicago, Houston, Atlanta, Minneapolis and St. Louis (suppressed in one or both years).

## 9. Gotchas that already cost us time

1. **Never cache an error page.** `fetch()` takes `cache_ok=`; the Census "Missing Key" HTML was cached for 30 days and survived adding the key. Also never put secrets in cache keys.
2. **`requests` percent-encodes `params=`.** Census wants the geography written literally (`...area/micropolitan%20statistical%20area:*`), so that URL is built by hand.
3. **Windows file locks.** A CSV open in Excel raises `PermissionError` on write; the panel builder then writes `metro_panel_new.csv`.
4. **Validation must run on the full universe.** A printout once chose "the 15 biggest metros" from the already-filtered set and falsely reported 15/15 usable. Compute coverage against all units.
5. **Division codes are not parent codes.** FHFA MSAD codes (e.g. 41884) do not trim to the parent MSA (41860); use `config/msad_parent.csv`.
6. **SEC name matching:** `company_tickers.json` lists current filers only, so names are also taken from the XBRL frames (which include delisted/renamed companies). Match order: alias → exact → prefix (≤2 extra tokens, unique CIK) → fuzzy (same first token, cutoff 0.88). Everything except alias/exact is `needs_review=1`. Q4 revenue is derived (annual − Q1..Q3). Foreign filers (20-F) lack US-GAAP revenue.
7. **Always read codes as strings** (`dtype=str`): CBSA, NAICS, SIC, FIPS lose leading zeros otherwise.
8. **Eurostat/BLS/ONS/Census definitions differ** (occupation vs industry, different coverage). Compare trends, not levels.
9. **Mock tests hid real bugs twice** (e.g. a test column set that hid the empty-dimension case). When fixing something, also test with the *real* file layout the user pasted.
10. Python 3.14 and pandas 3 on the owner's machine: avoid chained assignment and `inplace`; keep new code compatible with pandas ≥2.

## 10. Working agreements

- **Legal and ethical:** official APIs/downloads only. No scraping of LinkedIn, Glassdoor, Levels.fyi or any site whose terms forbid it. Keep the delay and cache; send a User-Agent with a contact email. Check licences before redistributing (`DATA_SOURCES.md`).
- **Secrets:** API keys live in environment variables only, never in code, commits, logs or chat. Never commit `data/raw/`, `data/cache/`, `data/manual/` or `layoffs_clean.csv`.
- **Honesty:** report numbers from the data, not from memory. Say when something is untested. Label associations as associations.
- **Decisions:** state thresholds before looking at results. Keep a short dated log of decisions (section 13).
- **Do not** change the master-file schema, merge datasets of different grain into one wide table, or silently drop rows.
- **Bilingual deliverables:** the notebooks and documents exist in English and Slovenian. If you change results or wording, update both or flag the other as stale.

## 11. Next steps (priority order, each with an acceptance check)

The split of these items between two people for the first week is in `docs/WORKSTREAMS.md` (Stream A: items 1 and 2; Stream B: items 3 to 5).

1. **Layoff-risk panel and model (biggest modelling payoff).**
   - Build a company-quarter panel for US public tech companies: more XBRL concepts (NetIncomeLoss, OperatingIncomeLoss, R&D, SG&A, cash, assets) via the same frames approach in `collectors/sec.py`.
   - Define the **comparison group** (companies with no tracker layoff): the tracker has only positives, so use SEC SIC codes (EDGAR submissions API or a SIC list) for a tech universe. Document the selection bias.
   - Label: any layoff event in the next 2 quarters. Split **by time** (train ≤2022, test 2023+); there are only ~110 usable positives in 2020–2022. Report PR-AUC and a naive baseline.
   - Done when: panel CSV + notebook + honest out-of-sample numbers.
2. **Causes track (over-hiring vs interest rates vs AI).** Add FRED series (policy rate, a market index) and JOLTS information-sector openings/hires/layoffs (BLS API) and Eurostat quarterly job-vacancy statistics; do lead-lag and event studies around 2022-03-16 (first Fed hike) and 2022-11-30 (ChatGPT). Done when each hypothesis has a stated test and a result with limits.
3. **Skills/NLP.** Use `hn_whoishiring_text.csv`: topic model (e.g. BERTopic), a junior-role classifier, change-point detection on remote/AI shares. Optional: Stack Overflow Developer Survey (ODbL). Done when the notebook runs end to end and keyword limits are discussed.
4. **Geography extras.** (a) Map (needs CBSA centroids or shapefiles, e.g. Census Gazetteer/TIGER). (b) Layoffs by metro (tracker `location` = HQ city). (c) Fill the 5 missing metros with Census County Business Patterns (employment is noise-infused rather than withheld) or a state-level QCEW robustness check. (d) Verify metro codes did not change between 2019 and 2024.
5. **Engineering hygiene.** There is **no automated test suite yet**; all checks so far were ad hoc scripts plus `build_master.py` validation. Add pytest tests for the adapters and the parsers (JSON-stat, FHFA header-less CSV, panel logic with the Chicago/DC suppression patterns), plus a CI job that runs them.
6. **Doc sync.** The English explainer doc predates the geography results; the Slovenian explainer and summary are current.

Suggested split between two people: one takes items 1–2 (company panel and causes), the other items 3–5 (NLP, geography extras, tests). Agree on file ownership before editing `masterfile/adapters.py` and `collect.py`, which everything touches.

## 12. Not verified yet

- `python collect.py --sources sec` after the frames-based name matching rewrite: tested with mocks only, not on the real API since the rewrite.
- Notebooks were executed against the real master and real metro panel, but the Hacker News sections only with placeholder data.
- No live test of Census ACS 5-year for 2023 and 2024 beyond one successful run (`acs5`: 938/935/935 areas).

## 13. When you finish a task

1. `python -m compileall -q .`; rerun `python build_master.py` if you touched collectors, adapters or the segment map, and confirm `master_validation.txt` has no FAIL lines.
2. Add or update tests (section 11, item 5) for what you changed.
3. Update `README.md`, `DATA_DICTIONARY.md` and `DATA_SOURCES.md` if sources or columns changed.
4. Record decisions as dated lines under your stream's *Notes* in `docs/STATUS.md` (never both people appending to this file at once); the owner merges them into the decision log below at the weekly sync, and updates the status in section 1 if it changed.
5. Never commit keys or ignored data folders.

### Decision log

- 2026-10: Go/no-go rule fixed in advance (≥2 of 3 feasibility tests); all three passed.
- 2026-10: Metro feasibility retested with NAICS 5415 after the 6-digit codes narrowly failed; threshold unchanged.
- 2026-10: Metro panel gets a second outcome (IT establishments) because employment is withheld for big metros; employment keeps a quarter-matched estimate with a flagged fallback.
- 2026-10: Census ACS 5-year preferred over 1-year (1-year work-from-home table missing for ~half of areas).
- 2026-10: SEC names taken from XBRL filings as well as the ticker list to include delisted companies.
- 2026-10: Repository to be shared privately via GitHub; raw data and the layoffs file stay out of git.
