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
| FHFA House Price Index | Metro house-price growth | Public; cite FHFA |
| US Census Bureau (Gazetteer files) | CBSA centroids for the metro maps (`census_gazetteer_cbsa.csv`) | Public; cite the US Census Bureau |
| US Census Bureau (ACS) | Metro work-from-home, education, income, rent | Public. "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau." |

## What is in this repository
Code, configuration, documentation, small derived tables (`data/processed/`: master file, validation report,
metro panel) and figures. Raw downloads and caches are excluded (size, and some sources do not allow redistribution);
run `python collect.py` to re-create them.
