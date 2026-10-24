# Stream B: Text, geography and quality (21 to 27 October 2026)

**Goal:** give the project a safety net (tests and CI), analyse what employers ask for in the Hacker News posts, and finish the geography track (maps, metro-code stability).

Read `AGENTS.md` first (sections 5, 6, 9 and 11 items 3 to 5). Your files: `tests/`, `.github/`, `requirements-dev.txt`, `collectors/hn.py`, `collectors/fhfa.py`, `collectors/census_*.py`, `analysis/hn_text.py`, `analysis/geo.py`, `analysis/metro_models.py`, `build_metro_panel.py`, `config/msad_parent.csv`, notebooks `05_*` and `06_*`.
Do **not** edit Stream A's files. New collectors self-register with `SOURCES = {...}`; do not edit `collect.py`.

## B1. Tests and CI (3 to 4 hours): do this first
There is **no automated test suite yet**. Create `tests/` (pytest; `requirements-dev.txt` already lists it; the CI workflow `.github/workflows/ci.yml` already runs `pytest`). At least 25 tests, no network (mock `collectors.common.fetch` or the session), and point `DATA_DIR` at `tmp_path` so tests never touch real `data/`.

Cover:
- `collectors/eurostat.jsonstat_to_df` (including a dataset with no extra dimensions: the empty-breakdown bug).
- `collectors/fhfa.parse` (header-less file; `-` becomes missing; `(MSAD)` flag).
- `collectors/qcew.area_level` and `split_national_and_areas`.
- `build_metro_panel.load_qcew` with the **real suppression patterns**: Chicago 2019 reported in all four quarters (about 65,000 jobs) but 2024 withheld in all four (`disclosure_code` N, value 0) while establishments stay reported (6,406 to 6,633); Washington DC reported only in 2019 Q3, Q4 and 2024 Q1. Expected: Chicago has no employment outcome but a complete establishment outcome; DC is rescued with `emp_basis == "unmatched"`.
- `collectors/hn.features` (remote, junior, AI rules; company guess).
- `collectors/sec.norm` and `match_companies` (alias, exact, prefix, fuzzy, delisted names from frames).
- `masterfile/schema.apply_segments` (unmapped codes are kept visible) and the duplicate-key check in `build_master`.
- `collectors/common.fetch` never caches an empty or invalid reply (`cache_ok`).

**Accept:** `pytest -q` is green locally and in CI; a short "Tests" section in `README.md`.

## B2. Hacker News text analysis (6 to 8 hours)
Inputs: `data/raw/hn_whoishiring_text.csv` (`post_id, text`) and `data/raw/hn_whoishiring_posts.csv` (flags, `thread_month`, `company_guess`). Raw text stays local; do not commit or redistribute it.
- `analysis/hn_text.py` and `notebooks/05_skills_nlp.ipynb` (scikit-learn):
  1. TF-IDF + NMF topic model (8 to 12 topics) with readable labels and monthly topic shares.
  2. Change-point detection on the remote and AI-mention shares (simple binary segmentation or `ruptures`).
  3. Entry-level (junior) share over time, and AI mentions before and after 2022-11-30, with an explicit caution about causality (junior mentions were already falling before AI).
  4. **Validate the keyword flags**: hand-label a random sample of 100 posts and report precision and recall for "remote" and "junior". This tests the known weakness (no negation handling).
- Output `data/processed/hn_topics_monthly.csv` (`month, topic, share`).
- **Accept:** the notebook runs end to end; manual-validation numbers reported; findings written with limits (startup skew, keyword rules).

## B3. Geography maps and code stability (5 to 7 hours)
- (a) `collectors/census_gazetteer.py` (self-registering): CBSA centroids from the Census Gazetteer (verify the URL, expected `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_cbsa_national.zip`; tab-delimited with `GEOID`, `INTPTLAT`, `INTPTLONG`) to `data/raw/census_gazetteer_cbsa.csv`.
- (b) `analysis/geo.py` and `notebooks/06_geography_maps.ipynb`: bubble maps of IT employment growth and of IT establishment growth (size = IT jobs 2019, colour = growth); mark metros with no IT employment. Use a simple US outline if you can add one cheaply, otherwise a plain longitude/latitude scatter.
- (c) Code stability: do the QCEW metro codes (`C####` in `bls_qcew_areas_it_industries.csv`) differ between 2019 and 2024 (delineation changes)? List metros that appear in only one year.
- (d) Touch `build_metro_panel.py` or `analysis/metro_models.py` only if needed; you own them.
- **Accept:** two maps saved to `reports/figures/`; (c) answered with a list.

## B4. Stretch: County Business Patterns for the five missing metros (3 to 5 hours)
IT employment is withheld for Chicago, Houston, Atlanta, Minneapolis and St. Louis. Census County Business Patterns (`api.census.gov/data/{year}/cbp`, geography metro areas, NAICS 5415, variables `EMP` and `ESTAB`, years 2019 and the latest) adds noise to values instead of withholding them. Needs `CENSUS_API_KEY`; build the geography clause by hand (see `AGENTS.md` section 9, item 2).
- **Accept:** a short result: does CBP agree with QCEW where both exist (correlation, level differences), and can it fill the five metros? Note the metro-definition and timing differences (CBP counts mid-March employment).

## Definition of done
`python -m compileall -q .` and `pytest -q` pass; `DATA_SOURCES.md` has rows for new sources; no keys or data folders in git; `docs/STATUS.md` ticked.
