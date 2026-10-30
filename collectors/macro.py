"""Macro series for the causes analysis (A4): FRED public CSV and BLS JOLTS (Information sector).

FRED: https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES> needs no key. FRED data are public; cite
"Federal Reserve Bank of St. Louis (FRED)" and the underlying source. (NASDAQCOM is published by Nasdaq via FRED.)
JOLTS: BLS public API, no key needed for v1 (set BLS_API_KEY for v2). Public domain; cite BLS.

If a JOLTS series comes back empty, check its ID at https://data.bls.gov/dataQuery/find (Job Openings and Labor
Turnover Survey). JOLTS ID = JT + S (seasonally adjusted) + industry (6) + state (2) + area (5) + size class (2)
+ data element (2: JO openings, HI hires, LD layoffs & discharges, QU quits) + L (level, thousands) or R (rate, %).
Source names: `macro`.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import logging
import os

import pandas as pd

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_SERIES = {
    "FEDFUNDS": "Effective federal funds rate, monthly average (%)",
    "DFF": "Effective federal funds rate, daily (%)",
    "NASDAQCOM": "NASDAQ Composite Index, daily close",
}
FRED_LICENCE = "FRED, Federal Reserve Bank of St. Louis: public data; cite FRED and the original source"

JOLTS_URL = "https://api.bls.gov/publicAPI/{version}/timeseries/data/"
JOLTS_LICENCE = "US Bureau of Labor Statistics: public domain, please cite BLS (https://www.bls.gov/opub/copyright-information.htm)"
_INFO, _ALL = "JTS510000000000000", "JTS000000000000000"       # Information sector / total nonfarm
JOLTS_SERIES = {
    f"{_INFO}JOL": "Information: job openings (thousands)",
    f"{_INFO}HIL": "Information: hires (thousands)",
    f"{_INFO}LDL": "Information: layoffs and discharges (thousands)",
    f"{_INFO}QUL": "Information: quits (thousands)",
    f"{_INFO}JOR": "Information: job openings rate (%)",
    f"{_INFO}LDR": "Information: layoffs and discharges rate (%)",
    f"{_ALL}JOL": "Total nonfarm: job openings (thousands)",
    f"{_ALL}LDL": "Total nonfarm: layoffs and discharges (thousands)",
    f"{_ALL}JOR": "Total nonfarm: job openings rate (%)",
    f"{_ALL}LDR": "Total nonfarm: layoffs and discharges rate (%)",
}


JOLTS_FLAT_URL = "https://download.bls.gov/pub/time.series/jt/jt.data.1.AllItems"   # tab-separated, all JOLTS series


def parse_jolts_flat(content: bytes, names: dict[str, str], start_year: int = 2015) -> pd.DataFrame:
    """BLS flat file (series_id, year, period, value, footnote_codes; headers and ids are space-padded) -> same long
    table as parse_jolts, restricted to our series."""
    df = pd.read_csv(io.BytesIO(content), sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    for c in ("series_id", "period", "year", "value"):
        df[c] = df[c].str.strip()
    df = df[df["series_id"].isin(names) & df["period"].str.startswith("M") & (df["period"] != "M13")]
    df = df[df["year"].astype(int) >= start_year]
    out = pd.DataFrame({"series_id": df["series_id"], "series_name": df["series_id"].map(names),
                        "date": pd.to_datetime(df["year"] + "-" + df["period"].str[1:] + "-01"),
                        "value": pd.to_numeric(df["value"], errors="coerce")})
    return out.reset_index(drop=True)


def collect_jolts_flat(start_year: int = 2015) -> pd.DataFrame:
    """Fallback when the API is down: the same data from download.bls.gov (BLS asks for a contact in the User-Agent;
    ours includes CONTACT_EMAIL)."""
    raw = fetch(JOLTS_FLAT_URL, max_age_days=7, cache_ok=lambda b: b[:9].strip().lower().startswith(b"series_id"))
    return parse_jolts_flat(raw, JOLTS_SERIES, start_year)


def _looks_like_fred_csv(content: bytes) -> bool:
    head = content[:40].lower()
    return head.startswith(b"observation_date") or head.startswith(b"date")


def parse_fred(content: bytes, series_id: str) -> pd.DataFrame:
    """FRED csv -> long table (series_id, date, value). Missing values are '.' in the file; the date column is
    called observation_date (current) or DATE (older)."""
    df = pd.read_csv(io.BytesIO(content))
    date_col = df.columns[0]
    value_col = series_id if series_id in df.columns else df.columns[1]
    out = pd.DataFrame({"series_id": series_id,
                        "date": pd.to_datetime(df[date_col], errors="coerce"),
                        "value": pd.to_numeric(df[value_col], errors="coerce")})
    return out.dropna(subset=["date", "value"]).reset_index(drop=True)


def collect_fred(start_year: int = 2015) -> pd.DataFrame:
    parts = []
    for sid in FRED_SERIES:
        try:
            raw = fetch(FRED_URL, params={"id": sid, "cosd": f"{start_year}-01-01"}, max_age_days=1,
                        cache_ok=_looks_like_fred_csv)
        except Exception as e:  # noqa: BLE001 - one failing series must not stop the others
            log.error("FRED %s failed: %s", sid, e)
            continue
        if not _looks_like_fred_csv(raw):
            log.error("FRED %s: reply is not a CSV (is the series id right? is fred.stlouisfed.org reachable?)", sid)
            continue
        df = parse_fred(raw, sid)
        log.info("FRED %s: %d rows, %s .. %s", sid, len(df), df["date"].min().date(), df["date"].max().date())
        parts.append(df)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["series_id", "date", "value"])


def parse_jolts(j: dict, names: dict[str, str]) -> pd.DataFrame:
    """BLS API reply -> long table (series_id, series_name, date, value); monthly rows only."""
    rows = []
    for s in j["Results"]["series"]:
        if not s["data"]:
            log.warning("JOLTS: no data for %s (check the series id)", s["seriesID"])
        for d in s["data"]:
            if not d["period"].startswith("M") or d["period"] == "M13":
                continue
            rows.append({"series_id": s["seriesID"], "series_name": names.get(s["seriesID"], ""),
                         "date": pd.Timestamp(int(d["year"]), int(d["period"][1:]), 1),
                         "value": pd.to_numeric(d["value"], errors="coerce")})
    return pd.DataFrame(rows, columns=["series_id", "series_name", "date", "value"])


def collect_jolts(start_year: int = 2015, end_year: int | None = None) -> pd.DataFrame:
    end_year = end_year or dt.date.today().year
    key = os.environ.get("BLS_API_KEY")
    version = "v2" if key else "v1"
    url = JOLTS_URL.format(version=version)
    parts = []
    for y0 in range(start_year, end_year + 1, 10):
        y1 = min(y0 + 9, end_year)
        body = {"seriesid": list(JOLTS_SERIES), "startyear": str(y0), "endyear": str(y1)}
        if key:
            body["registrationkey"] = key
        try:
            j = json.loads(fetch(url, json_body=body, cache_key=f"jolts|{version}|{sorted(JOLTS_SERIES)}|{y0}|{y1}",
                                 max_age_days=1))
        except Exception as e:  # noqa: BLE001
            log.error("JOLTS request %s-%s failed: %s", y0, y1, e)
            continue
        if j.get("status") != "REQUEST_SUCCEEDED":
            log.error("JOLTS %s-%s: %s", y0, y1, j.get("message"))
            continue
        for m in j.get("message", []):
            log.warning("JOLTS: %s", m)
        parts.append(parse_jolts(j, JOLTS_SERIES))
    if not parts:
        log.warning("JOLTS API gave nothing; trying the flat file %s", JOLTS_FLAT_URL)
        try:
            flat = collect_jolts_flat(start_year)
        except Exception as e:  # noqa: BLE001
            log.error("JOLTS flat file failed too: %s (try again later; the rest of the analysis runs without JOLTS)", e)
            flat = pd.DataFrame(columns=["series_id", "series_name", "date", "value"])
        return flat.sort_values(["series_id", "date"]).reset_index(drop=True)
    return (pd.concat(parts, ignore_index=True).drop_duplicates(["series_id", "date"])
            .sort_values(["series_id", "date"]).reset_index(drop=True))


def collect(start_year: int = 2015) -> list[dict]:
    ensure_dirs()
    out_records = []
    fred = collect_fred(start_year)
    if len(fred):
        p = RAW / "fred_series.csv"
        fred.to_csv(p, index=False)
        log.info("FRED: %d rows -> %s", len(fred), p)
        out_records.append(record("FRED (Federal Reserve Bank of St. Louis)", p, FRED_URL, FRED_LICENCE))
    jolts = collect_jolts(start_year)
    if len(jolts):
        p = RAW / "bls_jolts.csv"
        jolts.to_csv(p, index=False)
        have = jolts.groupby("series_id").size()
        log.info("JOLTS: %d rows -> %s; series with data: %d of %d", len(jolts), p, len(have), len(JOLTS_SERIES))
        out_records.append(record("BLS JOLTS", p, JOLTS_URL.format(version="v1"), JOLTS_LICENCE))
    return out_records


SOURCES = {"macro": lambda a: collect(a.start_year)}
