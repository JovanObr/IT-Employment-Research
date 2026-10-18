"""US BLS QCEW: quarterly employment, establishments and wages by detailed NAICS.

Two outputs:
  bls_qcew_it_industries.csv        national rows (company-type split; feeds the master file)
  bls_qcew_areas_it_industries.csv  state / county / metro rows (feeds the geography track)
Public domain; cite BLS.
"""
from __future__ import annotations

import datetime as dt
import io
import logging

import pandas as pd
import requests

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

URL = "https://data.bls.gov/cew/data/api/{year}/{qtr}/industry/{code}.csv"
LICENCE = "US Bureau of Labor Statistics: public domain, please cite BLS"

# NOTE the NAICS revision: software publishers were 511210 (NAICS 2017) and became
# 513210 (NAICS 2022, used from 2022 data). Stitch the two before comparing eras.
INDUSTRIES = {
    "511210": "Software publishers (NAICS 2017)",
    "513210": "Software publishers (NAICS 2022)",
    "541511": "Custom computer programming",
    "541512": "Computer systems design",
    "541513": "Computer facilities management",
    "541519": "Other computer related services",
    "518210": "Data processing, hosting & related",
    "5415": "Computer systems design & related services (4-digit group)",  # less often suppressed
    "10": "Total, all industries",  # denominator for IT share of local employment
}
KEEP = ["year", "qtr", "industry_code", "qtrly_estabs", "month1_emplvl",
        "month2_emplvl", "month3_emplvl", "total_qtrly_wages", "avg_wkly_wage"]
AREA_KEEP = ["area_fips", "year", "qtr", "industry_code", "disclosure_code", "qtrly_estabs",
             "month1_emplvl", "month2_emplvl", "month3_emplvl", "avg_wkly_wage"]


def area_level(fips: str) -> str:
    """Classify a QCEW area code (US000 = nation, 06000 = state, 06037 = county, C3108 = metro)."""
    if fips == "US000":
        return "national"
    if fips.startswith("US"):
        return "us_aggregate"
    if fips.startswith("C"):
        return "metro_or_combined_area"
    if fips[:2].isdigit() and len(fips) == 5:
        return "state" if fips.endswith("000") else "county"
    return "other"


def split_national_and_areas(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Private-sector, all-size-class rows, split into the national row and sub-national areas."""
    df = df[df["own_code"] == 5]
    if "size_code" in df.columns:
        df = df[df["size_code"] == 0]
    nat = df[df["area_fips"] == "US000"][[c for c in KEEP if c in df.columns]]
    areas = df[df["area_fips"] != "US000"][[c for c in AREA_KEEP if c in df.columns]].copy()
    areas["area_level"] = areas["area_fips"].map(area_level)
    return nat, areas


def collect(start_year: int = 2015, end_year: int | None = None) -> list[dict]:
    ensure_dirs()
    end_year = end_year or dt.date.today().year
    national, areas = [], []
    for code in INDUSTRIES:
        for year in range(start_year, end_year + 1):
            for qtr in (1, 2, 3, 4):
                url = URL.format(year=year, qtr=qtr, code=code)
                try:
                    raw = fetch(url, max_age_days=30, delay=0.4)
                except requests.HTTPError:
                    continue  # quarter not published yet, or code not used that year
                except Exception as e:
                    log.warning("QCEW %s %s Q%s: %s", code, year, qtr, e)
                    continue
                df = pd.read_csv(io.BytesIO(raw), dtype={"area_fips": str, "industry_code": str}, low_memory=False)
                nat, ar = split_national_and_areas(df)
                national.append(nat)
                areas.append(ar)
        log.info("QCEW %s (%s) done", code, INDUSTRIES[code])

    if not national:
        return []
    out_df = pd.concat(national, ignore_index=True)
    out_df["industry_name"] = out_df["industry_code"].map(INDUSTRIES)
    out_df = out_df.sort_values(["industry_code", "year", "qtr"])
    out = RAW / "bls_qcew_it_industries.csv"
    out_df.to_csv(out, index=False)
    log.info("QCEW national: %d rows -> %s", len(out_df), out)
    records = [record("BLS QCEW (national)", out, "https://www.bls.gov/cew/", LICENCE)]

    area_df = pd.concat(areas, ignore_index=True)
    area_df["industry_name"] = area_df["industry_code"].map(INDUSTRIES)
    out2 = RAW / "bls_qcew_areas_it_industries.csv"
    area_df.to_csv(out2, index=False)
    log.info("QCEW areas: %d rows -> %s", len(area_df), out2)
    records.append(record("BLS QCEW (state/county/metro)", out2, "https://www.bls.gov/cew/", LICENCE))
    return records
