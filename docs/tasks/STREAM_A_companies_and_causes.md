# Stream A: Companies and causes (21 to 27 October 2026)

**Goal:** attach company financials to layoff events, build a first layoff-risk model for US public tech companies, and (stretch) start testing the three explanations for the 2022 to 2023 layoff wave: over-hiring, higher interest rates, AI.

Read `AGENTS.md` first (sections 4, 8, 9 on SEC, and 11 item 1 and 2). Your files: `collectors/sec.py`, `collectors/macro.py`, `collectors/eurostat.py`, `analysis/company_*.py`, `analysis/causes.py`, `masterfile/*`, `build_master.py`, `config/segment_map.csv`, `config/company_aliases.csv`, notebooks `03_*` and `04_*`.
Do **not** edit Stream B's files. New collectors self-register with `SOURCES = {...}`; do not edit `collect.py`.

## What exists
- `data/raw/sec_company_matches.csv`: layoff company name → CIK (alias / exact / prefix / fuzzy; `needs_review`).
- `data/raw/sec_revenue_quarterly.csv`: quarterly revenue for matched companies (Q4 derived).
- `data/processed/layoffs_clean.csv`: 4,626 events (3,431 in US/Europe; 973 at stage "Post-IPO"), columns include `company, date, total_laid_off, industry, stage, country, region`.
- Test 2 result: 538 events from 194 companies have 8+ quarters of revenue; only about 110 of the usable events fall in 2020 to 2022.

## A1. SEC financials (3 to 4 hours)
Extend `collectors/sec.py` with `fetch_financials(...)` using the same XBRL frames API (`https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json`; instant values use periods ending in `I`, e.g. `CY2019Q1I`).
- Flows (quarterly + annual, derive Q4 = annual minus Q1..Q3): `NetIncomeLoss`, `OperatingIncomeLoss`, `GrossProfit`, `ResearchAndDevelopmentExpense`, `SellingGeneralAndAdministrativeExpense`.
- Instants: `CashAndCashEquivalentsAtCarryingValue`, `Assets`, `StockholdersEquity`.
- Keep tag-priority lists per concept (companies use different tags). Cache via `fetch()`.
- Output `data/raw/sec_financials_quarterly.csv` (long: `cik, period, concept, value, kind`). Register as source `sec_fin`.
- **Accept:** at least 5 concepts; log a coverage table (share of matched companies with 8+ quarters per concept); unit tests with mocked frames. Frames are calendar-aligned (CY) approximations; say so.

## A2. Comparison universe (3 to 4 hours)
The tracker lists only companies **with** layoffs, so a model needs companies without.
- For CIKs present in the revenue frames, fetch `https://data.sec.gov/submissions/CIK##########.json` (fields `sic`, `sicDescription`); cache, keep the polite delay (SEC allows about 10 requests per second; use 0.2 s or more) and the contact-email User-Agent.
- Tech filter (suggestion, document your final choice): SIC 3570 to 3579, 3661 to 3669, 3670 to 3679, 7370 to 7379.
- Output `data/raw/sec_universe_sic.csv` (`cik, name, sic, sic_description, ticker, is_tech`, plus a flag for companies matched to a tracker layoff).
- **Accept:** universe size reported; the share of matched layoff companies that fall *inside* the tech-SIC universe reported (selection check); mocked test. Matched layoff companies outside the SIC list stay in as positives (state this).

## A3. Company-quarter panel and baseline model (6 to 8 hours)
- `analysis/company_panel.py` writes `data/processed/company_panel.csv`: one row per (cik, quarter). Features use **only information available at quarter end**, lagged one quarter: revenue growth (YoY, QoQ), gross and operating margin, R&D / revenue, SG&A / revenue, cash / assets, log assets, net-loss flag, SIC group.
- Label `y_next2q`: at least one tracker layoff for that company in the next 2 quarters (one positive per window even if several events).
- `analysis/company_models.py`: logistic regression and a gradient-boosting baseline (scikit-learn is in `requirements.txt`). **Split by time**: train up to 2022Q4, test 2023Q1 onward. Report PR-AUC against the base rate, top coefficients or importances, and a calibration sanity check.
- Notebook `notebooks/03_company_layoff_risk.ipynb`.
- **Accept:** runs end to end; out-of-sample PR-AUC next to the base rate; a limits paragraph (positives-only tracker, survivorship because the ticker list holds current filers, few positives before 2023, US public companies only).
- Pitfalls: look-ahead leakage; filings arrive 1 to 2 months after quarter end (shift features by a further quarter unless you use the `filed` date); fiscal-year mismatch.

## A4. Stretch: macro data and causes (4 to 6 hours)
- `collectors/macro.py` (self-registering): FRED public CSV (`https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS`, also `NASDAQCOM`; verify it works without a key, else use a free key) and JOLTS Information-sector series via the BLS API (verify the IDs; pattern `JTS510000000000000JOL` openings, `...HIL` hires, `...LDL` layoffs and discharges, `...QUL` quits).
- `analysis/causes.py` and `notebooks/04_causes.ipynb`: lead-lag between rate changes and layoff events; event studies around 2022-03-16 (first Fed hike) and 2022-11-30 (ChatGPT); over-hiring check: relate the 2020 to 2021 growth of matched companies (A3 panel) to later layoffs.
- **Accept:** each of the three hypotheses has a stated test, a result and a limit, written in the notebook. Associations are not causes.

## Definition of done
`python -m compileall -q .` passes; tests added for new parsers and matching; `build_master.py` shows no FAIL if you touched adapters; `DATA_SOURCES.md` has rows for new sources; `docs/STATUS.md` ticked. No keys, no data folders in git.
