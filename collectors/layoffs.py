"""Layoffs: loads a CSV *you* download by hand into data/manual/.

Why manual? Layoffs.fyi is an interactive embed and its terms, not mine, decide
what automated access is allowed. Downloading the published dataset yourself
(e.g. the Kaggle copy, check its licence) keeps you clearly on the right side.
"""
from __future__ import annotations

import logging

import pandas as pd

from .common import MANUAL, PROCESSED, ensure_dirs, record

log = logging.getLogger("covid_it_data")

RENAME = {  # variants seen in public copies of the dataset -> our names
    "Company": "company", "Location_HQ": "location", "Location": "location",
    "Laid_Off": "total_laid_off", "Date_layoffs": "date", "Date": "date",
    "Percentage": "percentage_laid_off", "Industry": "industry", "Stage": "stage",
    "Country": "country", "Money_Raised_in_$_mil": "funds_raised",
}
EUROPE = {
    "United Kingdom", "Germany", "France", "Spain", "Italy", "Netherlands", "Ireland",
    "Sweden", "Norway", "Denmark", "Finland", "Poland", "Portugal", "Belgium",
    "Switzerland", "Austria", "Estonia", "Lithuania", "Latvia", "Czech Republic",
    "Czechia", "Romania", "Bulgaria", "Greece", "Hungary", "Croatia", "Slovenia",
    "Slovakia", "Luxembourg", "Iceland", "Serbia", "Ukraine", "Malta", "Cyprus",
}


def collect() -> list[dict]:
    ensure_dirs()
    files = [p for p in MANUAL.glob("*.csv") if "layoff" in p.name.lower()]
    if not files:
        log.warning(
            "No layoffs CSV in %s. Download one (see README) and re-run with --sources layoffs.",
            MANUAL,
        )
        return []
    src = max(files, key=lambda p: p.stat().st_mtime)
    df = pd.read_csv(src).rename(columns=RENAME)
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df["total_laid_off"] = pd.to_numeric(df.get("total_laid_off"), errors="coerce")
    df["region"] = df.get("country", pd.Series(dtype=str)).map(
        lambda c: "US" if c == "United States" else "Europe" if c in EUROPE else "Other"
    )
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    out = PROCESSED / "layoffs_clean.csv"
    df.to_csv(out, index=False)
    log.info("Layoffs: %d rows from %s -> %s", len(df), src.name, out)
    return [record("Layoffs tracker (manual download)", out, str(src),
                   "Check the licence/terms of the copy you downloaded; credit Layoffs.fyi")]
