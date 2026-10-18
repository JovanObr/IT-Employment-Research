"""US BLS: Current Employment Statistics (CES) via the public API.

Works without a key (v1: 25 queries/day, 10 years per request). Set BLS_API_KEY
(free: https://data.bls.gov/registrationEngine/) for the v2 limits.
BLS information is public domain; cite BLS as the source.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os

import pandas as pd

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

LICENCE = "US Bureau of Labor Statistics: public domain, please cite BLS (https://www.bls.gov/opub/copyright-information.htm)"

# CEU = not seasonally adjusted (exists for every industry). Values: thousands of employees.
# If a series comes back empty, look up the right ID at https://data.bls.gov/dataQuery/find
SERIES = {
    "CEU0000000001": "Total nonfarm",
    "CEU5000000001": "Information (sector)",
    "CEU5051320001": "Software publishers",
    "CEU5051800001": "Data processing, hosting & related",
    "CEU6054150001": "Computer systems design & related services",
}


def collect(start_year: int = 2015, end_year: int | None = None) -> list[dict]:
    ensure_dirs()
    end_year = end_year or dt.date.today().year
    key = os.environ.get("BLS_API_KEY")
    version = "v2" if key else "v1"
    url = f"https://api.bls.gov/publicAPI/{version}/timeseries/data/"
    names, rows = SERIES, []

    for y0 in range(start_year, end_year + 1, 10):  # both versions allow <=10y safely
        y1 = min(y0 + 9, end_year)
        body = {"seriesid": list(names), "startyear": str(y0), "endyear": str(y1)}
        if key:
            body["registrationkey"] = key
        cache_key = f"bls|{version}|{sorted(names)}|{y0}|{y1}"  # never cache the API key
        try:
            j = json.loads(fetch(url, json_body=body, cache_key=cache_key, max_age_days=1))
        except Exception as e:
            log.error("BLS request %s-%s failed: %s", y0, y1, e)
            continue
        if j.get("status") != "REQUEST_SUCCEEDED":
            log.error("BLS %s-%s: %s", y0, y1, j.get("message"))
            continue
        for m in j.get("message", []):
            log.warning("BLS: %s", m)
        for s in j["Results"]["series"]:
            if not s["data"]:
                log.warning("BLS: no data for %s", s["seriesID"])
            for d in s["data"]:
                if not d["period"].startswith("M") or d["period"] == "M13":
                    continue  # skip annual averages
                rows.append({
                    "series_id": s["seriesID"],
                    "series_name": names.get(s["seriesID"], ""),
                    "date": f"{d['year']}-{d['period'][1:]}-01",
                    "employees_thousands": pd.to_numeric(d["value"], errors="coerce"),
                })

    if not rows:
        return []
    df = pd.DataFrame(rows).drop_duplicates(["series_id", "date"]).sort_values(["series_id", "date"])
    out = RAW / "bls_ces_employment.csv"
    df.to_csv(out, index=False)
    log.info("BLS CES: %d rows -> %s", len(df), out)
    return [record("BLS CES", out, url, LICENCE)]
