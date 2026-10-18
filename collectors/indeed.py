"""Indeed Hiring Lab job-postings index (GitHub). Licence: CC BY 4.0 -> credit
"Indeed Hiring Lab" wherever you publish. Index baseline = 1 Feb 2020 (=100), so
this shows hiring *demand* from COVID onward, not a pre-COVID history.
"""
from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

BASE = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master"
LICENCE = "CC BY 4.0 - attribution to Indeed Hiring Lab required (https://creativecommons.org/licenses/by/4.0/)"
# GB = United Kingdom. Sector files only exist for some countries (404s are skipped).
COUNTRIES = ["US", "GB", "DE", "FR", "ES", "IT", "NL", "IE", "CA", "AU"]
# Exact display_name values in Indeed's files (France has no "Data & Analytics").
IT_SECTORS = {"Software Development", "IT Infrastructure, Operations & Support",
              "IT Systems & Solutions", "Data & Analytics"}


def _load(kind: str) -> pd.DataFrame:
    frames = []
    for cc in COUNTRIES:
        url = f"{BASE}/{cc}/{kind}_{cc}.csv"
        try:
            frames.append(pd.read_csv(io.BytesIO(fetch(url, max_age_days=1))))
        except requests.HTTPError:
            log.info("Indeed: no %s file for %s", kind, cc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def collect() -> list[dict]:
    ensure_dirs()
    records = []
    agg = _load("aggregate_job_postings")
    if not agg.empty:
        out = RAW / "indeed_aggregate_postings.csv"
        agg.to_csv(out, index=False)
        records.append(record("Indeed Hiring Lab (aggregate)", out, BASE, LICENCE))
    sec = _load("job_postings_by_sector")
    if not sec.empty:
        sec = sec[sec["display_name"].isin(IT_SECTORS)]
        out = RAW / "indeed_it_sector_postings.csv"
        sec.to_csv(out, index=False)
        log.info("Indeed IT sectors: %d rows -> %s", len(sec), out)
        records.append(record("Indeed Hiring Lab (IT sectors)", out, BASE, LICENCE))
    return records
