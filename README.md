# IT employment before/after COVID-19 — data collector

Pulls public data for US + European IT employment into tidy CSVs under `data/raw/`.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export CONTACT_EMAIL="you@university.edu"   # goes in the User-Agent (good manners)
export BLS_API_KEY="..."                    # optional, free: data.bls.gov/registrationEngine
python collect.py
```
First run takes a few minutes (QCEW is ~300 small requests). Everything is cached in
`data/cache/`, so re-runs are instant and don't hit the servers again.

## What you get
| Source | File | Covers | Licence |
|---|---|---|---|
| Eurostat API | `eurostat_isoc_sks_*.csv`, `eurostat_lfsa_egan22d.csv` | ICT specialists by country/sex/age/education; employment by NACE (J = information & communication) | Free reuse with attribution |
| BLS CES API | `bls_ces_employment.csv` | Monthly US employment: information sector, software publishers, computer systems design | Public domain, cite BLS |
| BLS QCEW | `bls_qcew_it_industries.csv` | Quarterly US employment/establishments/wages by detailed NAICS (company-type split) | Public domain, cite BLS |
| ONS BRES via Nomis | `nomis_bres_it_industries.csv` | **UK (Great Britain)** annual employment by detailed industry, 2015+: SIC 58/62/63 incl. games (58210, 62011). Fills Eurostat's post-2019 UK gap | Open Government Licence v3.0, credit ONS/Nomis |
| Hacker News (Algolia API) | `hn_whoishiring_posts.csv`, `hn_whoishiring_text.csv` | Monthly "Who is hiring?" posts: remote/junior/AI flags, ~30 skills, company guess (startup-skewed). Run alone: `python collect.py --sources hn --start-year 2015` | Public content; keep raw text local |
| SEC EDGAR (feasibility test 2) | `sec_company_matches.csv`, `sec_revenue_quarterly.csv` | Matches Post-IPO layoff companies to SEC filers (alias > exact > prefix > fuzzy; names also come from the revenue filings, so delisted companies are found) and pulls quarterly revenue (XBRL frames). Needs `CONTACT_EMAIL`. Review `needs_review=1` rows; extend `config/company_aliases.csv` (ticker or CIK) | Public SEC data |
| FHFA house prices | `fhfa_hpi_metro_quarterly.csv` | Metro house-price index (all-transactions), quarterly. Index base 1995Q1 = 100, compare changes only | Public US government data |
| Census ACS 1-year | `census_acs1_metro.csv` | Metro work-from-home share, education, income, rent, home value, age, broadband (2019, 2022-24) | Public; **needs a free `CENSUS_API_KEY`** (api.census.gov/data/key_signup.html) |
| Indeed Hiring Lab | `indeed_*.csv` | Daily job-postings index, US + EU countries + UK (`GB`), from Feb 2020 | CC BY 4.0, credit Indeed |
| Layoffs (manual) | `processed/layoffs_clean.csv` | Tech layoffs since Mar 2020, tagged US/Europe/Other | Check the copy's terms |

`data/manifest.json` records every file's source, URL, licence and retrieval time — use it
for your references/attribution section.

## Build the master file
```bash
python build_master.py            # US + Europe only (add --include-other to keep the rest)
```
Writes `data/processed/it_employment_master.csv` and `data/processed/master_validation.txt`
(checks, row counts, unmapped codes). Column meanings and the rules for using it safely:
see `DATA_DICTIONARY.md`. Company types are defined in `config/segment_map.csv`.
QCEW also writes `data/raw/bls_qcew_areas_it_industries.csv` (state/county/metro) for the geography track.

## Metro panel (geography track)
```bash
export CENSUS_API_KEY=...                       # PowerShell: $env:CENSUS_API_KEY="..."
python collect.py --sources qcew fhfa acs acs5   # qcew is fast from cache; acs5 covers small metros
python build_metro_panel.py                    # -> data/processed/metro_panel.csv + usable-metro counts
```
One row per metro: IT employment growth 2019-2024 (NAICS 5415, quarter-matched because QCEW suppression is erratic), location quotient, work-from-home change,
education, income, rent, house-price growth. The printout says how many metros are complete cases.
FHFA publishes the biggest metros as divisions; `config/msad_parent.csv` maps them to their parent metro.

## Sharing on GitHub
Safe to publish: code, `config/`, docs, `data/processed/` (except `layoffs_clean.csv`), `reports/figures/`.
`.gitignore` already excludes API keys, caches, raw downloads and the layoffs file. Prefer a **private** repo shared with
your supervisor; see `DATA_SOURCES.md` for licences before making anything public. Never put API keys in code.

## Explore
```bash
jupyter lab notebooks/01_first_look.ipynb     # run all cells; figures are saved to reports/figures/
```
The notebook reads only the master file, so re-run `build_master.py` after collecting new data.

## Layoffs: one manual step
Download the layoffs CSV yourself (e.g. search Kaggle for "layoffs" — the widely used copy is
by `swaptr`, or follow Layoffs.fyi's own terms), put it in `data/manual/` with "layoff" in the
filename, then:
```bash
python collect.py --sources layoffs
```

## Known gotchas (important for your analysis)
- **UK data (Nomis BRES) is Great Britain only** (no Northern Ireland) and is *industry*-based, like Eurostat `lfsa_egan22d`, not like the occupation-based ICT-specialist series. If the dataset lookup fails, set `NOMIS_BRES_ID` (find it at nomisweb.co.uk/api/v01/dataset/def.htm).
- **NAICS break:** software publishers are `511210` before 2022 and `513210` from 2022. Stitch them.
- **Series IDs may need adjusting.** If BLS logs "no data" for a series, find the right ID at
  https://data.bls.gov/dataQuery/find and edit `SERIES` in `collectors/bls.py`.
- **Eurostat vs BLS definitions differ** (ICT *occupations* vs *industries*): compare indexed trends, not levels.
- **Indeed's index starts Feb 2020** (=100), so it has no pre-COVID history; use Eurostat/BLS for the baseline.
- **Layoffs data is crowdsourced and skewed to VC-backed/large firms**; treat as a sample.
- Scraping extras (SEC EDGAR 10-K headcounts, Wikipedia company lists) aren't included yet.
