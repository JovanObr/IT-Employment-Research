"""FHFA House Price Index, all-transactions, metro areas (quarterly, not seasonally adjusted).

Public US government data (https://www.fhfa.gov/data/hpi/datasets). The file has NO header row:
place name, area code, year, quarter, index, standard error. The index is 100 at 1995Q1 for every
area, so compare *changes*, never levels across areas. The 11 largest MSAs are published as
metropolitan divisions ('(MSAD)'); they are kept and flagged (is_division = 1).
"""
from __future__ import annotations

import io
import logging

import pandas as pd

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

URL = "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_metro.csv"
LICENCE = "US Federal Housing Finance Agency: public data, please cite FHFA House Price Index"
COLS = ["place_name", "cbsa_code", "year", "quarter", "hpi_nsa", "hpi_se_raw"]


def parse(raw: bytes, start_year: int) -> pd.DataFrame:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    df = pd.read_csv(io.StringIO(text), header=None, names=COLS, dtype=str, keep_default_na=False)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["quarter"] = pd.to_numeric(df["quarter"], errors="coerce")
    df["hpi_nsa"] = pd.to_numeric(df["hpi_nsa"].str.strip(), errors="coerce")  # '-' = not published
    df = df.dropna(subset=["year", "quarter"])
    df = df[df["year"] >= start_year].copy()
    df["year"], df["quarter"] = df["year"].astype(int), df["quarter"].astype(int)
    df["is_division"] = df["place_name"].str.contains(r"\(MSAD\)", regex=True).astype(int)
    return df[["place_name", "cbsa_code", "is_division", "year", "quarter", "hpi_nsa"]]


def collect(start_year: int = 2015) -> list[dict]:
    ensure_dirs()
    df = parse(fetch(URL, max_age_days=30, delay=1.0), start_year)
    out = RAW / "fhfa_hpi_metro_quarterly.csv"
    df.to_csv(out, index=False)
    log.info("FHFA HPI: %d rows, %d areas -> %s", len(df), df["cbsa_code"].nunique(), out)
    return [record("FHFA HPI (metro, all-transactions)", out, URL, LICENCE)]
