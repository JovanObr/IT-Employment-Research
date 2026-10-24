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


# ---------------------------------------------------------------------------------------------------------
# A1: more financials (quarterly), same XBRL frames API.  Source name: sec_fin
# Frames are CALENDAR-aligned approximations (CY2022Q1 = the filing period closest to Jan-Mar 2022), so a
# company with a fiscal year ending in, say, June is mapped to the nearest calendar quarter, not its own.
# ---------------------------------------------------------------------------------------------------------
# concept -> us-gaap tags in preference order (companies use different tags for the same thing)
FIN_FLOWS = {
    "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "operating_income": ["OperatingIncomeLoss"],
    "gross_profit": ["GrossProfit"],
    "rnd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    # components used only to fill gaps (many tech companies report S&M and G&A separately, and cost of revenue
    # instead of gross profit); see add_derived_concepts()
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "sales_marketing": ["SellingAndMarketingExpense"],
    "g_and_a": ["GeneralAndAdministrativeExpense"],
}
FIN_INSTANTS = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "assets": ["Assets"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
}
FIN_COLUMNS = ["cik", "period", "concept", "value", "kind", "tag"]
_QUARTER_ENDS = ((1, 3, 31), (2, 6, 30), (3, 9, 30), (4, 12, 31))


def _instant_periods(start_year: int, end_year: int, today: dt.date | None = None):
    """Balance-sheet frames end in 'I' and exist for all four quarter ends (Q4 is in the 10-K)."""
    today = today or dt.date.today()
    for y in range(start_year, end_year + 1):
        for q, m, d in _QUARTER_ENDS:
            if dt.date(y, m, d) <= today:
                yield f"CY{y}Q{q}I"


def _period_kind(period: str) -> str:
    if period.endswith("I"):
        return "instant"
    return "annual" if re.fullmatch(r"CY\d{4}", period) else "quarter"


def fetch_concept_frames(concept: str, tags: list[str], periods, ciks: set[int]) -> pd.DataFrame:
    """One request per tag and period; keep only the wanted companies; the best-ranked tag wins per (cik, period)."""
    rows = []
    for period in periods:
        for rank, tag in enumerate(tags):
            try:
                j = json.loads(fetch(FRAMES.format(tag=tag, period=period), max_age_days=30, delay=0.3))
            except requests.HTTPError:
                continue  # this tag has no frame for this period
            for r in j.get("data", []):
                cik = int(r["cik"])
                if cik in ciks and r.get("val") is not None:
                    rows.append({"cik": cik, "period": period, "concept": concept, "value": r["val"],
                                 "tag": tag, "rank": rank})
    if not rows:
        return pd.DataFrame(columns=FIN_COLUMNS)
    df = pd.DataFrame(rows).sort_values("rank").drop_duplicates(["cik", "period"])
    df["kind"] = df["period"].map(_period_kind)
    return df[FIN_COLUMNS]


def add_derived_q4_long(fin: pd.DataFrame) -> pd.DataFrame:
    """Flows only: Q4 = annual - (Q1+Q2+Q3), when all four exist. Instants need no derivation.
    Caveat: the four inputs may come from different tags of the same concept; kept simple on purpose."""
    flows = fin[fin["kind"].isin(["annual", "quarter"])]
    if flows.empty:
        return fin
    wide = flows.pivot_table(index=["cik", "concept"], columns="period", values="value", aggfunc="first")
    years = [c for c in wide.columns if re.fullmatch(r"CY\d{4}", c)]
    new = []
    for (cik, concept), row in wide.iterrows():
        for p in years:
            parts = [row.get(f"{p}Q{q}") for q in (1, 2, 3)]
            if pd.notna(row.get(p)) and all(pd.notna(x) for x in parts):
                new.append({"cik": cik, "period": f"{p}Q4", "concept": concept, "value": row[p] - sum(parts),
                            "kind": "derived_q4", "tag": "derived"})
    return pd.concat([fin, pd.DataFrame(new, columns=FIN_COLUMNS)], ignore_index=True) if new else fin


def add_derived_concepts(fin: pd.DataFrame, revenue: pd.DataFrame | None) -> pd.DataFrame:
    """Fill gaps, never overwrite a reported value (derived rows carry tag 'derived_*'):
      sga          = sales_marketing + g_and_a            where no combined SG&A tag was reported
      gross_profit = revenue - cost_of_revenue            where no GrossProfit tag was reported
    Caveat: revenue and cost of revenue can come from different tags; treat derived margins as approximate."""
    have = lambda c: set(map(tuple, fin.loc[fin["concept"] == c, ["cik", "period"]].to_numpy()))
    new = []
    sm = fin[fin["concept"] == "sales_marketing"].set_index(["cik", "period"])
    ga = fin[fin["concept"] == "g_and_a"].set_index(["cik", "period"])
    both = sm.index.intersection(ga.index).difference(pd.MultiIndex.from_tuples(sorted(have("sga")), names=["cik", "period"]))
    for key in both:
        new.append({"cik": key[0], "period": key[1], "concept": "sga", "value": sm.loc[key, "value"] + ga.loc[key, "value"],
                    "kind": sm.loc[key, "kind"], "tag": "derived_sum"})
    if revenue is not None and len(revenue):
        rv = revenue.set_index(["cik", "period"])["revenue"]
        rv = rv[~rv.index.duplicated()]
        cr = fin[fin["concept"] == "cost_of_revenue"].set_index(["cik", "period"])
        gp_have = have("gross_profit")
        for key in cr.index.intersection(rv.index):
            if key not in gp_have:
                new.append({"cik": key[0], "period": key[1], "concept": "gross_profit",
                            "value": rv.loc[key] - cr.loc[key, "value"], "kind": cr.loc[key, "kind"],
                            "tag": "derived_revenue_minus_cost"})
    return pd.concat([fin, pd.DataFrame(new, columns=FIN_COLUMNS)], ignore_index=True) if new else fin


def coverage_table(fin: pd.DataFrame, ciks: set[int], min_quarters: int = MIN_QUARTERS) -> pd.DataFrame:
    """Per concept: matched companies with any data, and with >= min_quarters quarters (share of all matched)."""
    q = fin[fin["kind"].isin(["quarter", "derived_q4", "instant"])]
    rows = []
    for concept in [*FIN_FLOWS, *FIN_INSTANTS]:
        n = q[q["concept"] == concept].groupby("cik")["period"].nunique()
        rows.append({"concept": concept, "companies_any": int(len(n)),
                     f"companies_{min_quarters}q": int((n >= min_quarters).sum()),
                     f"share_{min_quarters}q": round(float((n >= min_quarters).sum()) / max(len(ciks), 1), 3)})
    return pd.DataFrame(rows)


def fetch_financials(ciks: set[int], start_year: int = 2015, end_year: int | None = None) -> pd.DataFrame:
    """Long table (cik, period, concept, value, kind, tag) for the given companies."""
    end_year = end_year or dt.date.today().year
    parts = []
    for concept, tags in FIN_FLOWS.items():
        parts.append(fetch_concept_frames(concept, tags, _periods(start_year, end_year), ciks))
        log.info("SEC financials: %s done", concept)
    for concept, tags in FIN_INSTANTS.items():
        parts.append(fetch_concept_frames(concept, tags, _instant_periods(start_year, end_year), ciks))
        log.info("SEC financials: %s done", concept)
    parts = [p for p in parts if len(p)]
    fin = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=FIN_COLUMNS)
    return add_derived_q4_long(fin).sort_values(["cik", "concept", "period"]).reset_index(drop=True)


def collect_financials(start_year: int = 2015) -> list[dict]:
    ensure_dirs()
    if not os.environ.get("CONTACT_EMAIL"):
        raise RuntimeError("SEC requires a contact email in the User-Agent. Set CONTACT_EMAIL and re-run.")
    path = RAW / "sec_company_matches.csv"
    if not path.exists():
        log.warning("%s not found - run the sec step first", path)
        return []
    ciks = {int(c) for c in pd.read_csv(path)["cik"].dropna()}
    uni_path = RAW / "sec_universe_sic.csv"
    if uni_path.exists():  # also the comparison companies: the risk model needs companies WITHOUT layoffs
        uni = pd.read_csv(uni_path, dtype={"sic": str})
        extra = {int(c) for c in uni.loc[uni["is_tech"], "cik"]} - ciks
        log.info("SEC financials: %d matched layoff companies + %d tech comparison companies", len(ciks), len(extra))
        ciks |= extra
    else:
        log.warning("%s not found: only the matched layoff companies are fetched; run sec_universe first for "
                    "comparison companies (the layoff-risk panel needs them)", uni_path)
    fin = fetch_financials(ciks, start_year)
    rev_path = RAW / "sec_revenue_universe.csv"
    if not rev_path.exists():
        rev_path = RAW / "sec_revenue_quarterly.csv"
    revenue = pd.read_csv(rev_path) if rev_path.exists() else None
    if revenue is None:
        log.warning("%s not found: gross profit cannot be derived from revenue - cost of revenue", rev_path)
    if len(fin):
        fin = add_derived_concepts(fin, revenue).sort_values(["cik", "concept", "period"]).reset_index(drop=True)
    if fin.empty:
        log.warning("SEC financials: no data returned")
        return []
    out = RAW / "sec_financials_quarterly.csv"
    fin.to_csv(out, index=False)
    log.info("SEC financials: %d rows for %d of %d companies -> %s",
             len(fin), fin["cik"].nunique(), len(ciks), out)
    missing = pd.read_csv(path)[lambda d: ~d["cik"].isin(fin["cik"])]
    if len(missing):
        log.info("SEC financials: no data for %d matched companies: %s", len(missing),
                 ", ".join(f"{n} ({c})" for n, c in zip(missing["layoffs_company"], missing["cik"])))
    log.info("Coverage (share of matched companies with >= %d quarters):\n%s", MIN_QUARTERS,
             coverage_table(fin, ciks).to_string(index=False))
    log.info("Note: frames are calendar-aligned approximations; Q4 flows are derived (annual - Q1..Q3).")
    return [record("SEC EDGAR XBRL frames: quarterly financials", out, "https://data.sec.gov/api/xbrl/frames/", LICENCE)]


# ---------------------------------------------------------------------------------------------------------
# A2: comparison universe. The layoff tracker lists only companies WITH layoffs; a risk model also needs
# companies without. We take every company with enough revenue history in the XBRL frames, look up its SIC
# code in the EDGAR submissions API, and flag technology companies.  Source name: sec_universe
# ---------------------------------------------------------------------------------------------------------
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
# Final tech choice (documented): computer & office equipment (357x), communications equipment (366x),
# electronic components incl. semiconductors (367x), computer services and software (737x).
TECH_SIC_RANGES = ((3570, 3579), (3661, 3669), (3670, 3679), (7370, 7379))
UNIVERSE_COLUMNS = ["cik", "name", "sic", "sic_description", "ticker", "is_tech", "matched_layoff",
                    "in_universe", "revenue_quarters"]


def is_tech_sic(sic) -> bool:
    try:
        n = int(str(sic).strip())
    except (TypeError, ValueError):
        return False
    return any(lo <= n <= hi for lo, hi in TECH_SIC_RANGES)


def parse_submission(j: dict) -> dict:
    """Pick the few fields we need from a submissions reply. SIC stays a string (leading zeros)."""
    tickers = j.get("tickers") or []
    return {"name": j.get("name") or "", "sic": str(j.get("sic") or "").strip(),
            "sic_description": j.get("sicDescription") or "", "ticker": tickers[0] if tickers else ""}


def fetch_submission(cik: int) -> dict | None:
    try:
        return parse_submission(json.loads(fetch(SUBMISSIONS.format(cik=cik), max_age_days=90, delay=0.25)))
    except requests.HTTPError:
        return None  # no submissions file for this CIK


def build_sic_universe(ciks: set[int], quarters: pd.Series, names: dict[int, str], matched: set[int],
                       fetcher=fetch_submission, progress: int = 250) -> pd.DataFrame:
    """One row per CIK in `ciks` plus every matched layoff company (they are the positives, so they stay in even
    when their SIC code is outside the tech list). `quarters`: revenue quarters per CIK."""
    ciks = sorted(set(ciks) | set(matched))
    rows = []
    for i, cik in enumerate(ciks, 1):
        info = fetcher(cik) or {}
        sic = info.get("sic", "")
        tech = is_tech_sic(sic)
        rows.append({"cik": cik, "name": info.get("name") or names.get(cik, ""), "sic": sic,
                     "sic_description": info.get("sic_description", ""), "ticker": info.get("ticker", ""),
                     "is_tech": tech, "matched_layoff": cik in matched, "in_universe": tech or cik in matched,
                     "revenue_quarters": int(quarters.get(cik, 0))})
        if i % progress == 0:
            log.info("SEC universe: %d / %d companies looked up", i, len(ciks))
    return pd.DataFrame(rows, columns=UNIVERSE_COLUMNS)


def universe_report(uni: pd.DataFrame, min_quarters: int = MIN_QUARTERS) -> None:
    """Universe size and the selection check: do the companies WITH layoffs fall inside the tech-SIC list?"""
    has_sic = uni["sic"] != ""
    tech = uni[uni["is_tech"]]
    log.info("SEC universe: %d companies | %d with a SIC code | %d tech (%d with >= %d revenue quarters)",
             len(uni), int(has_sic.sum()), len(tech), int((tech["revenue_quarters"] >= min_quarters).sum()), min_quarters)
    m = uni[uni["matched_layoff"] & has_sic]
    if len(m):
        log.info("SELECTION CHECK: %d of %d matched layoff companies (%.0f%%) are inside the tech-SIC universe; "
                 "the rest stay in as positives", int(m["is_tech"].sum()), len(m), 100 * m["is_tech"].mean())
        out = m[~m["is_tech"]]["sic_description"].value_counts().head(10)
        log.info("Most common SIC groups of matched layoff companies OUTSIDE the tech list:\n%s", out.to_string())
    log.info("Base rate of tech-universe companies with a tracker layoff: %.1f%%",
             100 * tech["matched_layoff"].mean() if len(tech) else float("nan"))


def collect_universe(start_year: int = 2015) -> list[dict]:
    ensure_dirs()
    if not os.environ.get("CONTACT_EMAIL"):
        raise RuntimeError("SEC requires a contact email in the User-Agent. Set CONTACT_EMAIL and re-run.")
    path = RAW / "sec_company_matches.csv"
    matched = {int(c) for c in pd.read_csv(path)["cik"].dropna()} if path.exists() else set()
    if not matched:
        log.warning("%s not found or empty - run the sec step first (matched layoff companies are the positives)", path)
    frames = fetch_frames(start_year, dt.date.today().year)  # cached by fetch(); all reporting companies
    if frames.empty:
        log.warning("SEC universe: no revenue frames")
        return []
    all_ciks = set(frames["cik"])
    rev = add_derived_q4(revenue_for(frames, all_ciks))
    q = rev[rev["kind"].isin(["quarter", "derived_q4"])].groupby("cik")["period"].nunique()
    keep = q[q >= MIN_QUARTERS]
    log.info("SEC universe: %d companies in the frames; %d with >= %d revenue quarters (looked up) + %d matched",
             len(all_ciks), len(keep), MIN_QUARTERS, len(matched - set(keep.index)))
    names = frames.drop_duplicates("cik").set_index("cik")["entityName"].to_dict()
    log.info("SEC universe: about %d requests at >= 0.25 s each; re-runs are cached", len(set(keep.index) | matched))
    uni = build_sic_universe(set(keep.index), q, names, matched)
    out = RAW / "sec_universe_sic.csv"
    uni.to_csv(out, index=False)
    log.info("SEC universe -> %s", out)
    universe_report(uni)
    # revenue of everyone in the universe (tech companies + matched layoff companies), for sec_fin and the panel;
    # sec_revenue_quarterly.csv from the `sec` step covers matched layoff companies only
    out_r = RAW / "sec_revenue_universe.csv"
    rev[rev["cik"].isin(set(uni.loc[uni["in_universe"], "cik"]))].to_csv(out_r, index=False)
    log.info("SEC universe: revenue of %d companies -> %s", int(uni["in_universe"].sum()), out_r)
    return [record("SEC EDGAR submissions: SIC codes", out, "https://data.sec.gov/submissions/", LICENCE),
            record("SEC EDGAR XBRL frames: revenue of the comparison universe", out_r,
                   "https://data.sec.gov/api/xbrl/frames/", LICENCE)]


# new collectors register themselves; collect.py does not need editing
SOURCES = {"sec_fin": lambda a: collect_financials(a.start_year),
           "sec_universe": lambda a: collect_universe(a.start_year)}
