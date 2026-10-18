"""US Census ACS 1-year estimates for metro areas (CBSAs): work-from-home share, education,
income, housing costs, broadband. Needs a FREE API key in CENSUS_API_KEY (https://api.census.gov/data/key_signup.html).

ACS 1-year covers areas with 65,000+ people (most metros, fewer small towns). 2020 has no
standard 1-year release, so we use 2019 (pre-COVID baseline) and the latest years.
Public US government data; cite the Census Bureau.
"""
from __future__ import annotations

import json
import logging
import os

import numpy as np
import pandas as pd
import requests

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

BASE = "https://api.census.gov/data/{year}/acs/{product}"
GEO = "metropolitan statistical area/micropolitan statistical area:*"
LICENCE = "US Census Bureau American Community Survey: public data, please cite the Census Bureau"
# acs1: 1-year estimates, only areas with 65,000+ people, clean single years (no 2020 release)
# acs5: 5-year estimates (2019 = 2015-2019, 2024 = 2020-2024), ALL metros incl. small ones, smoother but overlapping
PRODUCTS = {"acs1": ([2019, 2022, 2023, 2024], "census_acs1_metro.csv"),
            "acs5": ([2019, 2023, 2024], "census_acs5_metro.csv")}
CORE = {"B01003_001E": "population", "B08301_001E": "workers", "B08301_021E": "workers_home",
        "B15003_001E": "pop25", "B15003_022E": "ba", "B15003_023E": "ma", "B15003_024E": "prof",
        "B15003_025E": "phd", "B19013_001E": "median_hh_income", "B25064_001E": "median_gross_rent",
        "B25077_001E": "median_home_value", "B01002_001E": "median_age"}
EXTRA = {"B28002_001E": "households_total", "B28002_004E": "households_broadband"}


def _url(year: int, variables: dict, product: str = "acs1") -> str:
    # Census documents the geography with %20 for spaces but LITERAL '/', ':' and '*'.
    # Passing it through requests' params= percent-encodes them and the API then replies with nothing.
    url = (BASE.format(year=year, product=product) + "?get=NAME," + ",".join(variables)
           + "&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*")
    key = os.environ.get("CENSUS_API_KEY")
    return url + (f"&key={key}" if key else "")


def _get(year: int, variables: dict, product: str = "acs1") -> pd.DataFrame:
    raw = fetch(_url(year, variables, product), cache_key=f"acs|v2|{product}|{year}|{sorted(variables)}", max_age_days=30, delay=1.0,
                 cache_ok=lambda b: b[:1] == b"[")  # a data reply is a JSON list; error pages are HTML
    try:
        rows = json.loads(raw)
    except ValueError:
        if b"Missing Key" in raw or b"Invalid Key" in raw:
            raise RuntimeError("Census requires a free API key. Get one at https://api.census.gov/data/key_signup.html "
                               "(it arrives by email within minutes; click its activation link), then set CENSUS_API_KEY "
                               "(PowerShell: $env:CENSUS_API_KEY=\"your-key\"; macOS/Linux: export CENSUS_API_KEY=your-key).")
        raise RuntimeError(f"Census returned a non-JSON reply: {raw[:200]!r}")
    df = pd.DataFrame(rows[1:], columns=rows[0]).rename(columns=variables)
    df = df.rename(columns={GEO.split(":")[0]: "cbsa_code", "NAME": "name"})
    for c in variables.values():
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df.loc[df[c] < -1e6, c] = np.nan  # Census uses -666666666 etc. for 'not available'
    return df


def derive(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["wfh_share_pct"] = df["workers_home"] / df["workers"] * 100
    df["bachelors_plus_pct"] = (df["ba"] + df["ma"] + df["prof"] + df["phd"]) / df["pop25"] * 100
    if "households_broadband" in df:
        df["broadband_pct"] = df["households_broadband"] / df["households_total"] * 100
    return df


def collect(product: str = "acs1") -> list[dict]:
    ensure_dirs()
    years, fname = PRODUCTS[product]
    frames = []
    for year in years:
        try:
            try:
                df = _get(year, {**CORE, **EXTRA}, product)
            except requests.HTTPError as e:
                log.warning("ACS %s %s: full variable set rejected (%s), retrying without broadband", product, year, e)
                df = _get(year, CORE, product)
        except Exception as e:
            log.warning("ACS %s %s unavailable: %s", product, year, e)
            continue
        frames.append(derive(df).assign(year=year))
        log.info("ACS %s %s: %d areas", product, year, len(df))
    if not frames:
        return []
    out_df = pd.concat(frames, ignore_index=True)
    out = RAW / fname
    out_df.to_csv(out, index=False)
    return [record(f"Census ACS {product} (metro)", out, "https://api.census.gov/data/", LICENCE)]
