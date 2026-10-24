# Status board (updated 2026-10-24)

Each person edits **only their own section**. Tick a task when its pull request is merged; add one line on what changed and any caveat.

## Stream A: Companies and causes
- [x] A1 SEC financials (more XBRL concepts, quarterly)
- [x] A2 Tech-company universe from SEC SIC codes
- [x] A3 Company-quarter panel + layoff-risk baseline (notebook 03)
- [ ] A4 *(stretch)* Macro data (FRED, JOLTS) and causes tests (notebook 04)

Notes:
- A1: `sec_fin` (8 concepts + 3 components; gross profit and SG&A filled from components where not reported, tag `derived_*`). 8+ quarters for 201 of 204 matched companies; ASML, Freightos, Sportradar (foreign filers) have none.
- A2: `sec_universe` (7,044 companies, 999 tech by SIC 357x/366x/367x/737x) also writes `sec_revenue_universe.csv`. 111 of 204 matched layoff companies are tech by SIC; **model on `is_tech`, not `in_universe`**.
- A3: `python -m analysis.company_panel`, then `python -m analysis.company_models`, then notebook 03. Run order for data: `layoffs`, `sec`, `sec_universe`, `sec_fin`. Panel: 866 tech companies, 14,709 rows, 3.0% base rate; test 2023Q1+ has 294 positives from 90 companies.
- A3 result: logistic PR-AUC 0.28 (0.16-0.44) vs base rate 0.041, **but company size alone gives 0.32**; without size about 0.08 (about 2x base rate). Read the limits section of notebook 03 before quoting numbers.

## Stream B: Text, geography and quality
- [ ] B1 Tests (pytest) and CI
- [ ] B2 Hacker News text analysis (notebook 05)
- [ ] B3 Geography maps, metro-code stability (notebook 06)
- [ ] B4 *(stretch)* County Business Patterns for the 5 missing metros

Notes:

## Requests between streams
(Write "A asks B: ..." or "B asks A: ..." here; the owner of the file makes the change.)

## Blocked / questions
