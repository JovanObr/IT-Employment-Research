"""Indeed Hiring Lab remote/hybrid tracker: share of job postings that advertise remote or hybrid work (Milestone 2, D2.1).

Repository: https://github.com/hiring-lab/remote-tracker (checked 2026-11-10). Files used:
  remote_postings.csv         date, jobcountry, remote_share_postings          (all postings, one row per day and country)
  remote_postings_sector.csv  date, jobcountry, normtitlecategory_consistent, remote_share_postings  (by occupational category,
                              e.g. 'software development'; the README calls the column 'sector')
The value column is looked up by its prefix `remote_share` so a rename of the suffix does not break the parser.
Definition (Hiring Lab): share of postings whose title or description mentions remote, hybrid or work-from-home options,
seven-day trailing average. Keyword based, like our Hacker News flag; Hiring Lab says it is a trend indicator.
Licence: CC BY 4.0, credit Indeed Hiring Lab.

Output: data/raw/indeed_remote_postings.csv  (date, country, sector, remote_share_pct); sector "all" for the country file.
Only the US is kept (the project's comparison is with US studies). Self-registering: `python collect.py --sources indeed_remote`.
"""
from __future__ import annotations

import io
import logging

import pandas as pd

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

BASE = "https://raw.githubusercontent.com/hiring-lab/remote-tracker/main"
FILES = {"all": "remote_postings.csv", "sector": "remote_postings_sector.csv"}
LICENCE = "CC BY 4.0 - attribution to Indeed Hiring Lab required (https://creativecommons.org/licenses/by/4.0/)"
COUNTRIES = ("US",)


def _looks_like_csv(b: bytes) -> bool:
    head = b[:200].decode("utf-8", errors="replace").lower()
    return "date" in head and "remote_share" in head


def parse(raw: bytes | str, countries=COUNTRIES) -> pd.DataFrame:
    """CSV text -> date, country, sector ('all' when the file has no sector column), remote_share_pct (float)."""
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    vcols = [c for c in df.columns if c.lower().startswith("remote_share")]
    if "date" not in df.columns or "jobcountry" not in df.columns or not vcols:
        raise ValueError(f"unexpected remote-tracker columns: {list(df.columns)}")
    # the sector column is 'normtitlecategory_consistent' in the 2026 file (the README says 'sector'): any other column is the sector
    scols = [c for c in df.columns if c not in ("date", "jobcountry", *vcols)]
    out = pd.DataFrame({
        "date": pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d"),
        "country": df["jobcountry"].str.strip().str.upper(),
        "sector": df[scols[0]].str.strip() if scols else "all",
        "remote_share_pct": pd.to_numeric(df[vcols[0]], errors="coerce"),
    }).dropna(subset=["date", "remote_share_pct"])
    if countries:
        out = out[out["country"].isin(countries)]
    return out.reset_index(drop=True)


def collect() -> list[dict]:
    ensure_dirs()
    parts = []
    for kind, name in FILES.items():
        raw = fetch(f"{BASE}/{name}", max_age_days=7, cache_ok=_looks_like_csv)
        parts.append(parse(raw))
    df = pd.concat(parts, ignore_index=True).sort_values(["sector", "date"])
    out = RAW / "indeed_remote_postings.csv"
    df.to_csv(out, index=False)
    log.info("Indeed remote tracker: %d US rows, %d sectors -> %s", len(df), df["sector"].nunique(), out)
    return [record("Indeed Hiring Lab remote/hybrid tracker", out, f"{BASE}/", LICENCE)]


SOURCES = {"indeed_remote": lambda args: collect()}
