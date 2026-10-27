"""US Census Gazetteer: CBSA (metro and micro area) centroids for the maps in the geography track.

File: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_cbsa_national.zip
(URL checked against the Census 2023 gazetteer page on 2026-10-27; the page lists the zip only, tab-delimited,
and does not document the columns, so the parser looks them up by name and tolerates stray whitespace).
Columns used: GEOID (5-digit CBSA code), NAME, LSAD, INTPTLAT, INTPTLONG (internal point), ALAND_SQMI.
Public US government data. Note: centroids are of the 2023 delineation; QCEW metro codes come from its own year's delineation.

Output: data/raw/census_gazetteer_cbsa.csv  (cbsa_code as a 5-character string)
Self-registering: collect.py finds SOURCES below, run `python collect.py --sources gazetteer`.
"""
from __future__ import annotations

import io
import logging
import zipfile

import pandas as pd

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_cbsa_national.zip"
LICENCE = "US Census Bureau: public data (Gazetteer files); please cite the US Census Bureau"
NEEDED = ["GEOID", "INTPTLAT", "INTPTLONG"]


def parse(raw: bytes) -> pd.DataFrame:
    """Zip bytes (or plain tab-delimited text) -> tidy DataFrame with string CBSA codes and float coordinates."""
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not names:
                raise ValueError(f"no .txt file in the gazetteer zip: {z.namelist()}")
            raw = z.read(names[0])
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    df = pd.read_csv(io.StringIO(text), sep="\t", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]          # the last header often carries trailing whitespace
    missing = [c for c in NEEDED if c not in df.columns]
    if missing:
        raise ValueError(f"gazetteer columns {missing} not found; got {list(df.columns)}")
    out = pd.DataFrame({
        "cbsa_code": df["GEOID"].str.strip().str.zfill(5),
        "name": df["NAME"].str.strip() if "NAME" in df else "",
        "lsad": df["LSAD"].str.strip() if "LSAD" in df else "",
        "lat": pd.to_numeric(df["INTPTLAT"].str.strip(), errors="coerce"),
        "lon": pd.to_numeric(df["INTPTLONG"].str.strip(), errors="coerce"),
        "aland_sqmi": pd.to_numeric(df["ALAND_SQMI"].str.strip(), errors="coerce") if "ALAND_SQMI" in df else float("nan"),
    })
    out = out.dropna(subset=["lat", "lon"])
    return out[out["cbsa_code"].str.fullmatch(r"\d{5}")].reset_index(drop=True)


def collect() -> list[dict]:
    ensure_dirs()
    raw = fetch(URL, max_age_days=365, delay=0.5, cache_ok=lambda b: b[:2] == b"PK")
    df = parse(raw)
    out = RAW / "census_gazetteer_cbsa.csv"
    df.to_csv(out, index=False)
    log.info("Census Gazetteer CBSA: %d areas -> %s", len(df), out)
    return [record("Census Gazetteer CBSA centroids (2023)", out, URL, LICENCE)]


SOURCES = {"gazetteer": lambda args: collect()}
