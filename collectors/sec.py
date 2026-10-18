"""SEC EDGAR: can we attach public-company financials to layoff events?  (Feasibility test 2)

Steps
  1. Match layoff companies (default: stage 'Post-IPO', US/Europe) to SEC filers by name.
  2. Pull quarterly revenue for the matched companies from the XBRL 'frames' API
     (one request per tag and calendar period, not one per company).
  3. Count layoff events whose company has >= 8 quarters of revenue data.

TEST 2 RULE (set in advance): PASS if >= 250 layoff events belong to matched
companies with >= 8 quarters of revenue data.

Honest limits: company_tickers.json lists *current* filers only, so we ALSO take company names from the
revenue filings themselves, which include delisted, acquired and renamed companies; foreign filers (20-F/40-F) mostly lack
us-gaap data; name matching can be wrong, so every non-exact match is flagged for review.

SEC requires a descriptive User-Agent with a contact email: set CONTACT_EMAIL.
Terms: SEC data is public; keep within ~10 requests/second (we are far below).
"""
from __future__ import annotations

import datetime as dt
import difflib
import json
import logging
import os
import re

import pandas as pd
import requests

from .common import PROCESSED, RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"
LICENCE = "SEC EDGAR: public data (https://www.sec.gov/os/webmaster-faq#developers)"
ALIASES = "config/company_aliases.csv"
# preference order when a company reports more than one revenue tag for a period
REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"]
MIN_QUARTERS, MIN_EVENTS = 8, 250
STOP = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc",
        "llc", "lp", "holdings", "holding", "group", "the", "sa", "nv", "ag"}


def norm(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", str(name).lower().replace("&", " and "))
    toks = [t for t in s.split() if t not in STOP]
    if len(toks) > 1 and toks[-1] == "com":  # 'amazon com inc' / 'booking.com'
        toks = toks[:-1]
    return " ".join(toks)


def load_tickers() -> pd.DataFrame:
    j = json.loads(fetch(TICKERS_URL, max_age_days=30))
    rows = j.values() if isinstance(j, dict) else j
    return pd.DataFrame([{"cik": int(r["cik_str"]), "ticker": r["ticker"], "title": r["title"]} for r in rows])


def build_universe(tickers: pd.DataFrame, frames: pd.DataFrame) -> pd.DataFrame:
    """Every (cik, name) we can match against: current filers (tickers file) PLUS every company
    that ever reported revenue in the frames, which includes delisted/acquired/renamed ones."""
    t = tickers[["cik", "title"]].rename(columns={"title": "name"}).assign(source="tickers")
    f = (frames[["cik", "entityName"]].drop_duplicates().rename(columns={"entityName": "name"}).assign(source="frames")
         if len(frames) else pd.DataFrame(columns=["cik", "name", "source"]))
    u = pd.concat([t, f], ignore_index=True).dropna(subset=["name"]).drop_duplicates(["cik", "name"])
    u["cik"] = u["cik"].astype(int)
    u["norm"] = u["name"].map(norm)
    return u[u["norm"] != ""]


def match_companies(companies: list[str], universe: pd.DataFrame, tickers: pd.DataFrame,
                    aliases: dict[str, str]) -> pd.DataFrame:
    """Alias > exact > prefix > fuzzy. Everything except alias and a unique exact match is flagged for review."""
    by_norm = universe.groupby("norm")
    keys = sorted(by_norm.groups)
    by_ticker = tickers.drop_duplicates("ticker").set_index("ticker")["cik"]
    ticker_of = tickers.drop_duplicates("cik").set_index("cik")["ticker"]
    title_of = universe.drop_duplicates("cik", keep="last").set_index("cik")["name"]
    src_of = universe.drop_duplicates("cik").set_index("cik")["source"]

    def pick(cik, mtype, score, review):
        return {"cik": int(cik), "ticker": ticker_of.get(int(cik), ""), "sec_title": title_of.get(int(cik), ""),
                "match_type": mtype, "score": score, "needs_review": review, "name_source": src_of.get(int(cik), "")}

    out = []
    for name in sorted(set(companies)):
        n, hit = norm(name), None
        al = aliases.get(name.strip().lower())
        if al is not None:  # alias target is a ticker or a numeric CIK
            cik = int(al) if str(al).isdigit() else by_ticker.get(al)
            if cik is not None and pd.notna(cik):
                hit = pick(cik, "alias", 1.0, 0)
        if hit is None and n in by_norm.groups:
            g = by_norm.get_group(n)
            hit = pick(g.iloc[0]["cik"], "exact", 1.0, int(g["cik"].nunique() > 1))
        if hit is None and n:
            pre = [k for k in keys if k.startswith(n + " ") and len(k.split()) - len(n.split()) <= 2]
            ciks = {int(c) for k in pre for c in by_norm.get_group(k)["cik"]}
            if len(ciks) == 1:  # 'Rivian' -> 'Rivian Automotive', 'Uber' -> 'Uber Technologies'
                hit = pick(next(iter(ciks)), "prefix", 0.95, 1)
        if hit is None and n:
            first = n.split()[0]
            cand = [k for k in keys if k.split()[0] == first]
            close = difflib.get_close_matches(n, cand, n=1, cutoff=0.88)
            if close:
                g = by_norm.get_group(close[0])
                hit = pick(g.iloc[0]["cik"], "fuzzy", round(difflib.SequenceMatcher(None, n, close[0]).ratio(), 3), 1)
        if hit:
            out.append({**hit, "layoffs_company": name})
    return pd.DataFrame(out)


def _periods(start_year: int, end_year: int):
    today = dt.date.today()
    for y in range(start_year, end_year + 1):
        for suffix, first_month in (("Q1", 1), ("Q2", 4), ("Q3", 7), ("", 1)):
            if dt.date(y, first_month, 1) <= today:
                yield f"CY{y}{suffix}"


def fetch_frames(start_year: int, end_year: int) -> pd.DataFrame:
    """Revenue for ALL reporting companies, one request per tag and calendar period."""
    frames = []
    for period in _periods(start_year, end_year):
        for rank, tag in enumerate(REVENUE_TAGS):
            try:
                j = json.loads(fetch(FRAMES.format(tag=tag, period=period), max_age_days=30, delay=0.3))
            except requests.HTTPError:
                continue  # no data for this tag/period
            d = pd.DataFrame(j.get("data", []))
            if d.empty:
                continue
            frames.append(d.reindex(columns=["cik", "entityName", "val"]).assign(period=period, tag=tag, rank=rank))
        log.debug("SEC frames %s done", period)
    if not frames:
        return pd.DataFrame(columns=["cik", "entityName", "val", "period", "tag", "rank"])
    df = pd.concat(frames, ignore_index=True)
    df["cik"] = df["cik"].astype(int)
    return df


def revenue_for(frames: pd.DataFrame, ciks: set[int]) -> pd.DataFrame:
    df = (frames[frames["cik"].isin(ciks)].sort_values("rank").drop_duplicates(["cik", "period"])
          .rename(columns={"val": "revenue"}))
    df["kind"] = df["period"].map(lambda p: "annual" if re.fullmatch(r"CY\d{4}", p) else "quarter")
    return df[["cik", "period", "revenue", "tag", "kind"]]


def add_derived_q4(rev: pd.DataFrame) -> pd.DataFrame:
    """Q4 = annual - (Q1+Q2+Q3), only when all four inputs exist."""
    wide = rev.pivot(index="cik", columns="period", values="revenue")
    new = []
    for cik, row in wide.iterrows():
        for p in [c for c in wide.columns if re.fullmatch(r"CY\d{4}", c)]:
            parts = [row.get(f"{p}Q{q}") for q in (1, 2, 3)]
            if pd.notna(row.get(p)) and all(pd.notna(x) for x in parts):
                new.append({"cik": cik, "period": f"{p}Q4", "revenue": row[p] - sum(parts),
                            "tag": "derived", "kind": "derived_q4"})
    return pd.concat([rev, pd.DataFrame(new)], ignore_index=True) if new else rev


def feasibility(events: pd.DataFrame, matches: pd.DataFrame, rev: pd.DataFrame) -> None:
    q = rev[rev["kind"].isin(["quarter", "derived_q4"])].groupby("cik")["period"].nunique()
    usable = set(q[q >= MIN_QUARTERS].index)
    m = events.merge(matches[["layoffs_company", "cik"]], left_on="company", right_on="layoffs_company")
    ok = m[m["cik"].isin(usable)]
    log.info("SEC: %d events in scope | %d matched to a filer (%d companies) | %d with >= %d quarters of revenue (%d companies)",
             len(events), len(m), m["cik"].nunique(), len(ok), MIN_QUARTERS, ok["cik"].nunique())
    log.info("Matched events by year (usable):\n%s", ok.assign(year=ok["date"].dt.year).groupby("year").size().to_string())
    log.info("Matches to review (fuzzy/ambiguous): %d of %d", int(matches["needs_review"].sum()), len(matches))
    log.info("FEASIBILITY TEST 2 (SEC company panel): %s - %d usable events (need %d)",
             "PASS" if len(ok) >= MIN_EVENTS else "FAIL", len(ok), MIN_EVENTS)


def collect(start_year: int = 2015, stages: tuple[str, ...] = ("Post-IPO",)) -> list[dict]:
    ensure_dirs()
    if not os.environ.get("CONTACT_EMAIL"):
        raise RuntimeError("SEC requires a contact email in the User-Agent. Set CONTACT_EMAIL and re-run.")
    path = PROCESSED / "layoffs_clean.csv"
    if not path.exists():
        log.warning("%s not found - run the layoffs step first", path)
        return []
    lay = pd.read_csv(path)
    lay["date"] = pd.to_datetime(lay["date"], errors="coerce")
    events = lay[lay["region"].isin(["US", "Europe"]) & lay["stage"].isin(stages)].dropna(subset=["company"])
    log.info("SEC: %d in-scope layoff events from %d companies (stages: %s)", len(events), events["company"].nunique(), ", ".join(stages))

    al_path = ALIASES if os.path.exists(ALIASES) else None
    aliases = {}
    if al_path:
        a = pd.read_csv(al_path)
        aliases = {n.strip().lower(): t for n, t in zip(a["layoffs_name"], a["sec_ticker"])}
    tickers = load_tickers()
    end_year = dt.date.today().year
    frames = fetch_frames(start_year, end_year)
    universe = build_universe(tickers, frames)
    log.info("SEC: matching against %d company names (%d from the ticker list, %d more from revenue filings)",
             len(universe), int((universe["source"] == "tickers").sum()), int((universe["source"] == "frames").sum()))
    matches = match_companies(events["company"].tolist(), universe, tickers, aliases)
    if matches.empty:
        log.warning("SEC: no companies matched")
        return []
    out_m = RAW / "sec_company_matches.csv"
    matches.sort_values(["needs_review", "match_type"], ascending=False).to_csv(out_m, index=False)
    rev = add_derived_q4(revenue_for(frames, set(matches["cik"])))
    out_r = RAW / "sec_revenue_quarterly.csv"
    rev.to_csv(out_r, index=False)
    log.info("SEC: matches -> %s ; revenue (%d rows) -> %s", out_m, len(rev), out_r)
    feasibility(events, matches, rev)
    return [record("SEC EDGAR company matches", out_m, TICKERS_URL, LICENCE),
            record("SEC EDGAR XBRL frames: revenue", out_r, "https://data.sec.gov/api/xbrl/frames/", LICENCE)]
