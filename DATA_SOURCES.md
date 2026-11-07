# Data sources, licences and attribution

All data are public. Collectors use official APIs or published downloads. `data/manifest.json` (written by
`collect.py`) records the exact URL and download time of every file. Cite the sources below in any report.

| Source | Used for | Terms / attribution |
|---|---|---|
| Eurostat | ICT specialists, employment by industry (Europe) | Free reuse with attribution: "Source: Eurostat" |
| US Bureau of Labor Statistics (CES, QCEW) | US employment, establishments, wages, metro detail | Public domain; cite BLS |
| UK Office for National Statistics via Nomis (BRES) | Great Britain jobs by detailed industry | Open Government Licence v3.0, Crown copyright |
| Indeed Hiring Lab | Job-postings index | CC BY 4.0: "Indeed Hiring Lab" |
| Hacker News "Who is hiring?" via Algolia API | Remote/skills/seniority trends | Public content; **raw text is not redistributed** |
| Layoffs.fyi (CSV downloaded manually) | Layoff events | Credit Layoffs.fyi; check the terms of the copy you downloaded; **raw file not redistributed** |
| SEC EDGAR (XBRL frames) | Public-company revenue; quarterly net income, operating income, gross profit, R&D, SG&A, cash, assets, equity (`sec_fin`); SIC industry codes for the comparison universe (`sec_universe`) | Public SEC data |
| SEC EDGAR (10-K filings) | Employee counts read from the text of annual reports, tech companies, 2019 and 2021-2023 (`sec_headcount`; only the number and its sentence are kept, in `data/raw/sec_headcount.csv`) | Public SEC data |
| FRED (Federal Reserve Bank of St. Louis) | Fed funds rate (FEDFUNDS, DFF) and NASDAQ Composite (NASDAQCOM), for the causes analysis | Public; cite "Federal Reserve Bank of St. Louis (FRED)" and the original source (NASDAQCOM: Nasdaq) |
| BLS JOLTS (Job Openings and Labor Turnover) | Information-sector and total-nonfarm openings, hires, layoffs, quits | Public domain; cite BLS |
| FHFA House Price Index | Metro house-price growth | Public; cite FHFA |
| US Census Bureau (Gazetteer files) | CBSA centroids for the metro maps (`census_gazetteer_cbsa.csv`) | Public; cite the US Census Bureau |
| US Census Bureau (ACS) | Metro work-from-home, education, income, rent | Public. "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau." |

## Sources under every graph

Every figure in the story notebook ends with a "Viri podatkov" line naming the original source and the exact CSV files. The mapping lives in `analysis/data_sources.py` and is checked against `data/manifest.json` by `tests/test_data_sources.py`; run `python -m analysis.data_sources` to print every line.

## What is in this repository
Code, configuration, documentation, small derived tables (`data/processed/`: master file, validation report,
metro panel) and figures. Raw downloads and caches are excluded (size, and some sources do not allow redistribution);
run `python collect.py` to re-create them.
