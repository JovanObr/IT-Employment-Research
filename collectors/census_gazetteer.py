"""US Census Gazetteer: CBSA (metro and micro area) centroids for the maps in the geography track.

File: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_cbsa_national.zip
(URL checked against the Census 2023 gazetteer page on 2026-10-27; the page lists the zip only, tab-delimited,
and does not document the columns, so the parser looks them up by name and tolerates stray whitespace).
Columns used: GEOID (5-digit CBSA code), NAME, LSAD, INTPTLAT, INTPTLONG (internal point), ALAND_SQMI.
Public US government data. Note: centroids are of the 2023 delineation; QCEW metro codes come from its own year's delineation.

Output: data/raw/census_gazetteer_cbsa.csv  (cbsa_code as a 5-character string)
If Census answers 403, save the zip by hand in data/manual/ (any name containing Gaz_cbsa): it is used first.
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


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
}


def _manual_file():
    """A hand-downloaded copy in data/manual/ (any *Gaz_cbsa*.zip or .txt). Used first, so it also works offline."""
    from . import common
    for pat in ("*Gaz_cbsa*.zip", "*Gaz_cbsa*.txt", "*gaz*cbsa*"):
        hits = sorted(common.MANUAL.glob(pat))
        if hits:
            return hits[0]
    return None


def _download() -> bytes:
    """Normal polite fetch first. Census sometimes answers 403 to non-browser User-Agents, so on a 403 retry once
    with browser-like headers (same file, same single request rate)."""
    import requests
    try:
        return fetch(URL, max_age_days=365, delay=0.5, cache_ok=lambda b: b[:2] == b"PK")
    except requests.HTTPError as e:
        if e.response is None or e.response.status_code != 403:
            raise
        log.warning("Census answered 403 to the default User-Agent; retrying once with browser-like headers")
        r = requests.get(URL, headers=BROWSER_HEADERS, timeout=90)
        if r.status_code == 403 or r.content[:2] != b"PK":
            raise RuntimeError(
                "Census refused the download (403). Download the file in your browser from\n  " + URL +
                "\nand save it in data/manual/ (keep the name 2023_Gaz_cbsa_national.zip), then run this source again."
            ) from e
        return r.content


def collect() -> list[dict]:
    ensure_dirs()
    manual = _manual_file()
    if manual is not None:
        log.info("Census Gazetteer: using the hand-downloaded file %s", manual)
        raw = manual.read_bytes()
    else:
        raw = _download()
    df = parse(raw)
    out = RAW / "census_gazetteer_cbsa.csv"
    df.to_csv(out, index=False)
    log.info("Census Gazetteer CBSA: %d areas -> %s", len(df), out)
    return [record("Census Gazetteer CBSA centroids (2023)", out, URL, LICENCE)]


SOURCES = {"gazetteer": lambda args: collect()}