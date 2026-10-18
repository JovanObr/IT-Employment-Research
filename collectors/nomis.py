"""UK (Great Britain) employment by detailed industry: ONS BRES via the Nomis API.

Why: Eurostat's UK series stops at 2019 (Brexit), so this fills the post-COVID UK gap
on the *industry* side. BRES goes down to 5-digit SIC 2007, which is the only place in
this project where games show up: 58210 (publishing of computer games) and
62011 (ready-made interactive leisure & entertainment software development).

Dataset: "Business Register and Employment Survey : open access" (API ref NEWBRES6PUB,
2015 onwards; it includes PAYE-only businesses, so 2015+ is one consistent series).
Coverage is Great Britain (excludes Northern Ireland). No key needed; anonymous
requests are capped at 25,000 cells, so we download one year at a time.
Licence: Open Government Licence v3.0 (Crown copyright) - credit ONS / Nomis.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import logging
import os
import re

import pandas as pd
import requests

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

BASE = "https://www.nomisweb.co.uk/api/v01"
LICENCE = "Open Government Licence v3.0, Crown copyright - credit ONS / Nomis (https://www.nomisweb.co.uk/home/copyright.asp)"
TARGET_NAME = "business register and employment survey : open access"
# Nomis geography code for Great Britain (checked against the returned name below).
GB_GEOGRAPHY = os.environ.get("NOMIS_GEOGRAPHY", "2092957698")
IT_SIC2 = {"58", "62", "63"}  # publishing (incl. games), IT services, information services


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _walk(obj):
    """Yield every dict that has both an 'id' and a 'name' (robust to JSON nesting)."""
    if isinstance(obj, dict):
        if "id" in obj and "name" in obj:
            yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _name(kf: dict) -> str:
    n = kf.get("name")
    if isinstance(n, dict):
        return n.get("value", "")
    if isinstance(n, list) and n:
        return n[0].get("value", "") if isinstance(n[0], dict) else str(n[0])
    return str(n)


def find_dataset_id() -> str:
    """Look up the Nomis dataset id (NM_xxx_1) for BRES open access by name."""
    override = os.environ.get("NOMIS_BRES_ID")
    if override:
        return override
    raw = fetch(
        f"{BASE}/dataset/def.sdmx.json",
        params={"search": "name-*Business Register and Employment Survey*"},
        max_age_days=30,
    )
    cands = [(str(k["id"]), _name(k)) for k in _walk(json.loads(raw))]
    for ds_id, name in cands:
        if _norm(name) == TARGET_NAME:
            return ds_id
    bad = ("public/private", "safeguarded", "excluding", "paye")
    for ds_id, name in cands:
        n = _norm(name)
        if n.startswith("business register and employment survey") and "open access" in n \
                and not any(b in n for b in bad):
            return ds_id
    log.warning("Nomis datasets found: %s", cands)
    raise RuntimeError("Could not identify the BRES dataset. Find its id (NM_..._1) at "
                       "https://www.nomisweb.co.uk/api/v01/dataset/def.htm and set NOMIS_BRES_ID.")


def _read(raw: bytes) -> pd.DataFrame:
    # Nomis CSVs are not always UTF-8 (some name fields use Windows-1252 characters).
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    df = pd.read_csv(io.StringIO(text), dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    return df


def latest_year(ds_id: str) -> int:
    raw = fetch(f"{BASE}/dataset/{ds_id}.data.csv",
                params={"geography": GB_GEOGRAPHY, "date": "latest", "recordlimit": 1},
                max_age_days=1)
    return int(str(_read(raw)["DATE_NAME"].iloc[0])[:4])


def _keep(industry_name: str) -> bool:
    n = industry_name.strip()
    if n.lower().startswith("total"):
        return True
    m = re.match(r"^(\d{2,5})\b", n)
    if m:
        return m.group(1)[:2] in IT_SIC2
    return bool(re.match(r"^J\b", n))  # section J: Information & communication


def collect(start_year: int = 2015) -> list[dict]:
    ensure_dirs()
    ds_id = find_dataset_id()
    last = latest_year(ds_id)
    log.info("Nomis BRES dataset %s, latest year %s", ds_id, last)

    frames = []
    for year in range(max(start_year, 2015), last + 1):  # BRES open access starts 2015
        try:
            raw = fetch(f"{BASE}/dataset/{ds_id}.data.csv",
                        params={"geography": GB_GEOGRAPHY, "date": str(year),
                                "ExcludeMissingValues": "true"},
                        max_age_days=30, delay=1.0)
        except requests.HTTPError as e:
            log.warning("Nomis BRES %s: %s", year, e)
            continue
        df = _read(raw)
        if df.empty:
            log.warning("Nomis BRES %s: no rows", year)
            continue
        geo = df["GEOGRAPHY_NAME"].iloc[0]
        if not re.search(r"great britain|united kingdom", geo, re.I):
            log.warning("Nomis geography %r is not GB/UK - check NOMIS_GEOGRAPHY", geo)
        if "MEASURE_NAME" in df.columns:  # count vs industry-percentage
            df = df[df["MEASURE_NAME"].str.contains("count", case=False, na=False)]
        df = df[df["INDUSTRY_NAME"].map(_keep)]
        frames.append(pd.DataFrame({
            "year": pd.to_numeric(df["DATE_NAME"].str[:4]),
            "geography": df["GEOGRAPHY_NAME"],
            "industry_name": df["INDUSTRY_NAME"].str.strip(),
            "sic_code": df["INDUSTRY_NAME"].str.extract(r"^\s*(\d{2,5})\b", expand=False),
            "employment_status": df["EMPLOYMENT_STATUS_NAME"],
            "jobs": pd.to_numeric(df["OBS_VALUE"], errors="coerce"),
        }))
        log.info("Nomis BRES %s: %d IT-related rows", year, len(frames[-1]))

    if not frames:
        return []
    out_df = pd.concat(frames, ignore_index=True).sort_values(["sic_code", "employment_status", "year"])
    out = RAW / "nomis_bres_it_industries.csv"
    out_df.to_csv(out, index=False)
    log.info("Nomis BRES: %d rows -> %s", len(out_df), out)
    return [record("ONS BRES via Nomis", out, f"{BASE}/dataset/{ds_id}", LICENCE)]
