"""Employee counts from annual 10-K filings (SEC EDGAR), to test over-hiring directly.  Source name: sec_headcount

US companies state their headcount in Item 1 of the 10-K ("As of December 31, 2021, we had approximately 2,447 full-time
employees"), but almost none tag it in XBRL, so it is read from the text. For each tech company of the SEC universe
(sec_universe_sic.csv: tech SIC and >= 8 revenue quarters) and each wanted year, the 10-K covering that year is found in
the cached submissions file, its main document is streamed and reading stops as soon as the headcount sentence is found
(Item 1 comes before the long financial sections, so usually well under 1 MB is read).

Output data/raw/sec_headcount.csv, one row per 10-K tried: cik, period_year, report_date, accession, url, employees
(missing if no sentence was found), snippet (the sentence it came from, for checking by hand), bytes_read.
The run is resumable: filings already in the file are skipped. Needs CONTACT_EMAIL (SEC rule). The documents are not
cached (that would be gigabytes); only the parsed number and its sentence are kept.

`period_year`: the calendar year the headcount refers to. A fiscal year ending in January-March belongs to the year
before (e.g. Domo's 10-K for the year ending 2022-01-31 gives the headcount at the end of 2021).
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import time

import pandas as pd
import requests

from collectors.common import RAW, ensure_dirs, fetch, record, session

log = logging.getLogger("covid_it_data")

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"      # the same URL (and cache) as collectors/sec.py
SUBMISSIONS_PAGE = "https://data.sec.gov/submissions/{name}"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
YEARS = (2019, 2021, 2022, 2023)
OUT_COLUMNS = ["cik", "period_year", "report_date", "accession", "url", "employees", "snippet", "bytes_read"]
LICENCE = "SEC EDGAR: public data (https://www.sec.gov/os/webmaster-faq#developers); cite SEC EDGAR"

# ---------------------------------------------------------------------------------------- text -> headcount
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?(?:\s*(?:thousand|million))?)"
_QUAL = (r"(?:(?:approximately|about|around|over|more than|nearly|roughly|almost|a total of|an aggregate of|in excess of|"
         r"just over|just under|some|total)\s+)*")
_ADJ = (r"(?:(?:full[- ]time(?:[- ]equivalent)?|part[- ]time|total|global|worldwide|regular|permanent|active|salaried|direct)"
        r"(?:\s+(?:and|or)\s+(?:part[- ]time|full[- ]time|contract|temporary))?\s+)*")
_NOUN = (r"(employees|employee|team members|teammates|people|associates|staff members|staff|personnel|FTEs|workers|"
         r"colleagues|individuals)\b")
_CANDIDATE = re.compile(rf"{_QUAL}{_NUM}\s+{_ADJ}{_NOUN}", re.I)
# The words just before the number must say "this is our headcount" ...
_HEADCOUNT_CONTEXT = re.compile(r"\b(had|have|has|employ(?:ed|s)?|workforce|headcount|team|consist(?:ed|s)?|compris(?:ed|es)?|"
                                r"total(?:ed|led|s)?|was|were)\b", re.I)
# ... and not "this is a change, a part of it or someone else".
_NOT_HEADCOUNT = re.compile(r"\b(reduc\w*|laid|layoffs?|eliminat\w*|terminat\w*|severance|restructur\w*|hire[sd]?|hiring|"
                            r"recruit\w*|add(?:ed|ing)?|acqui\w*|unions?|represented|contractors?|temporary|located|based|"
                            r"of whom|of which|including|includes|approximately \d+%|percent|outside|consultants?|"
                            r"affected|impacted|departures?|attrition|plan(?:s|ned)? to)\b", re.I)
_AS_OF = re.compile(r"\b(as of|at the end of|at year[- ]end|at the date of|on (?:january|february|march|april|may|june|july|august|september|"
                    r"october|november|december) \d|december 31|fiscal year[- ]end|at (?:january|february|march|april|may|june|july|august|"
                    r"september|october|november|december))\b", re.I)
# Right after the noun: the number is only a part of the staff ("employees engaged in R&D") or not a headcount at all.
_SUBSET_AFTER = re.compile(r"^\s*(?:(?:who are|that are|are|were)\s+)?(?:engaged in|dedicated to (?:research|r&d|sales|engineering|product|"
                           r"development|manufactur|customer)|in (?:our )?(?:research|r&d|engineering|sales|product|manufacturing|operations|"
                           r"customer|marketing)|in our [\w ,&]{0,40}(?:organization|team|department|function|group|operations)|-?related|benefits?\b|"
                           r"focused on|that works? (?:out of|in|for)|outside (?:of )?(?:the|our)|"
                           r"compensation|stock|share|options?\b|retirement|pension)", re.I)
_OF_THE = re.compile(r"\b(?:of|from)\s+(?:the|our|its|these|those)\s*$", re.I)        # "307 of the 464 employees included in this action"
_TABLE = re.compile(r"in thousands|in millions|\$", re.I)
_FT_PT = re.compile(rf"{_QUAL}{_NUM}\s+full[- ]time(?:\s+employees)?,?\s+and\s+{_QUAL}{_NUM}\s+part[- ]time\s+{_NOUN}", re.I)
# A department, not the whole company: "our research and development team was comprised of approximately 994 employees".
_DEPARTMENT = re.compile(r"\b(?:research|r&d|engineering|sales|marketing|development|product|support|services|manufacturing)"
                         r"(?:\s+and\s+\w+)?\s+(?:team|organi[sz]ation|department|staff|group|function|personnel)\b", re.I)
_YEAR_LIKE = re.compile(r"^(19[89]\d|20[0-4]\d)$")


def html_to_text(raw: str) -> str:
    """Visible text of an (inline XBRL) HTML document, one line, entities decoded."""
    raw = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]*>", " ", raw)
    text = html.unescape(raw).replace("\xa0", " ").replace("\u2009", " ")
    return re.sub(r"\s+", " ", text)


def _number(s: str) -> float | None:
    s = s.strip().lower()
    mult = 1000 if "thousand" in s else 1_000_000 if "million" in s else 1
    s = re.sub(r"[^\d.]", "", s.replace(",", ""))
    try:
        return float(s) * mult
    except ValueError:
        return None


def _candidates(text: str):
    """(start, end, value, noun) for every number-of-people phrase; '12 full-time and 9 part-time employees' counts as 21."""
    for m in _FT_PT.finditer(text):
        a, b = _number(m.group(1)), _number(m.group(2))
        if a is not None and b is not None:
            yield m.start(), m.end(), a + b, m.group(3), True
    for m in _CANDIDATE.finditer(text):
        yield m.start(), m.end(), _number(m.group(1)), m.group(2), not _YEAR_LIKE.match(m.group(1))


def find_headcount(text: str) -> tuple[float | None, str, int]:
    """(employees, sentence, 3) for the first DATED headcount statement in `text` ("As of December 31, 2021, we had ..."), or
    (None, "", 0). Undated mentions are not used: in practice they come from biographies, tables or narrative, not the headcount."""
    found = []
    for start, end, value, noun, ok in _candidates(text):
        if not ok or value is None or not (1 <= value < 3_000_000):
            continue
        lo = max(0, start - 160)
        prefix = text[lo:start]
        cut = max(prefix.rfind(". "), prefix.rfind("; "))          # only the clause the number is in
        prefix = prefix[cut + 2:] if cut >= 0 else prefix
        after = text[end:end + 70]
        if not _HEADCOUNT_CONTEXT.search(prefix) or _NOT_HEADCOUNT.search(prefix + " " + text[start:end]):
            continue
        if _SUBSET_AFTER.search(after) or _OF_THE.search(prefix) or _TABLE.search(prefix) or _DEPARTMENT.search(prefix):
            continue
        if not (_AS_OF.search(prefix) or _AS_OF.search(after[:45])):
            continue
        stop = text.find(". ", end)
        found.append((start, value, (prefix + text[start: stop if 0 <= stop < end + 200 else end + 200]).strip()[:300]))
    if not found:
        return None, "", 0
    start, value, snippet = min(found)                            # the earliest in the document
    return value, snippet, 3


# ---------------------------------------------------------------------------------------- filings
def period_year(report_date: str) -> int:
    d = pd.Timestamp(report_date)
    return d.year - 1 if d.month <= 3 else d.year


def annual_filings(sub: dict, page_fetcher=None) -> pd.DataFrame:
    """Every original 10-K (not amendments) in a submissions reply: accession, report_date, document, period_year.
    Older pages (filings.files) are read only when the recent list does not reach back to 2019."""
    def frame(block: dict) -> pd.DataFrame:
        keys = ("accessionNumber", "form", "reportDate", "primaryDocument")
        return pd.DataFrame({k: block.get(k, []) for k in keys})

    rec = sub.get("filings", {}).get("recent", {})
    parts = [frame(rec)]
    oldest = min(rec.get("filingDate") or ["9999"])
    if oldest > "2019-06-30" and page_fetcher is not None:
        for f in sub.get("filings", {}).get("files", []):
            if f.get("filingTo", "9999") >= "2019-01-01":
                parts.append(frame(page_fetcher(f["name"])))
    d = pd.concat(parts, ignore_index=True)
    d = d[(d["form"].isin(["10-K", "10-KT"])) & (d["reportDate"].astype(str).str.len() == 10) & (d["primaryDocument"] != "")]
    if d.empty:
        return pd.DataFrame(columns=["accession", "report_date", "document", "period_year"])
    d = d.rename(columns={"accessionNumber": "accession", "reportDate": "report_date", "primaryDocument": "document"})
    d["period_year"] = d["report_date"].map(period_year)
    return d.sort_values("report_date").drop_duplicates("period_year", keep="last")[["accession", "report_date", "document", "period_year"]]


def stream_headcount(url: str, chunk: int = 262_144, max_bytes: int = 8_000_000, getter=None) -> tuple[float | None, str, int]:
    """Read the document in chunks and stop once a dated headcount sentence is found. Returns (employees, snippet, bytes read)."""
    getter = getter or (lambda u: session().get(u, stream=True, timeout=90))
    r = getter(url)
    r.raise_for_status()
    raw, n, best = "", 0, (None, "", 0)
    for part in r.iter_content(chunk):
        raw += part.decode("utf-8", errors="ignore")
        n += len(part)
        best = find_headcount(html_to_text(raw))
        if best[2] == 3 or n >= max_bytes:
            break
    r.close()
    return best[0], best[1], n


def target_companies(universe: pd.DataFrame, min_quarters: int = 8) -> list[int]:
    t = universe[universe["is_tech"].astype(str).str.lower().isin(["true", "1"]) & (universe["revenue_quarters"] >= min_quarters)]
    return sorted(int(c) for c in t["cik"])


def collect(years=YEARS, delay: float = 0.15) -> list[dict]:
    ensure_dirs()
    if not os.environ.get("CONTACT_EMAIL"):
        raise RuntimeError("SEC requires a contact email in the User-Agent. Set CONTACT_EMAIL and re-run.")
    uni_path = RAW / "sec_universe_sic.csv"
    if not uni_path.exists():
        raise RuntimeError("Run collect.py --sources sec_universe first (it lists the tech companies).")
    ciks = target_companies(pd.read_csv(uni_path, dtype={"sic": str}))
    out = RAW / "sec_headcount.csv"
    done = pd.read_csv(out, dtype={"accession": str}) if out.exists() else pd.DataFrame(columns=OUT_COLUMNS)
    done, n_redo = recheck(done)
    if n_redo:
        log.info("SEC headcount: %d earlier results no longer pass the (stricter) sentence rules; they are read again", n_redo)
    seen = set(done["accession"].astype(str))
    log.info("SEC headcount: %d tech companies x %d years; %d filings already done (resumable)", len(ciks), len(years), len(seen))
    page = lambda name: json.loads(fetch(SUBMISSIONS_PAGE.format(name=name), max_age_days=90, delay=0.25))
    rows, t0 = [], time.time()
    for i, cik in enumerate(ciks, 1):
        try:
            sub = json.loads(fetch(SUBMISSIONS.format(cik=cik), max_age_days=90, delay=0.25))
            filings = annual_filings(sub, page)
        except (requests.HTTPError, ValueError) as e:
            log.warning("SEC headcount: no submissions for %s (%s)", cik, e)
            continue
        for f in filings[filings["period_year"].isin(years)].itertuples():
            if f.accession in seen:
                continue
            url = ARCHIVE.format(cik=cik, acc=f.accession.replace("-", ""), doc=f.document)
            try:
                emp, snip, n = stream_headcount(url)
            except requests.RequestException as e:
                log.warning("SEC headcount: %s failed (%s)", url, e)
                continue
            rows.append({"cik": cik, "period_year": f.period_year, "report_date": f.report_date, "accession": f.accession,
                         "url": url, "employees": emp, "snippet": snip, "bytes_read": n})
            time.sleep(delay)
        if i % 50 == 0 or i == len(ciks):
            _save(done, rows, out)
            got = sum(r["employees"] is not None for r in rows)
            log.info("SEC headcount: %d / %d companies, %d new filings (%d with a number), %.0f min so far",
                     i, len(ciks), len(rows), got, (time.time() - t0) / 60)
    allrows = _save(done, rows, out)
    report(allrows, years)
    return [record("SEC EDGAR 10-K filings: employee counts (parsed from text)", out, "https://www.sec.gov/Archives/edgar/data/", LICENCE)]


def recheck(done: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Apply the current sentence rules to the saved sentences. A sentence that now gives a different valid number is corrected in
    place (no download); a row whose sentence no longer gives any number is dropped so the filing is read again. Rows without a
    number are kept as they are (their document had no usable sentence, and the rules only got stricter).
    Returns (rows to keep, number of rows to read again)."""
    if done.empty:
        return done, 0
    done = done.copy()
    has = done["employees"].notna()
    new = done["snippet"].fillna("").map(lambda t: find_headcount(t)[0])
    fix = has & new.notna() & (new != done["employees"])
    done.loc[fix, "employees"] = new[fix]
    redo = has & new.isna()
    if fix.any():
        log.info("SEC headcount: %d saved sentences re-read with the current rules gave a corrected number", int(fix.sum()))
    return done[~redo].reset_index(drop=True), int(redo.sum())


def _save(done: pd.DataFrame, rows: list[dict], out) -> pd.DataFrame:
    allrows = pd.concat([done, pd.DataFrame(rows, columns=OUT_COLUMNS)], ignore_index=True).drop_duplicates("accession", keep="last")
    allrows.to_csv(out, index=False)
    return allrows


def report(d: pd.DataFrame, years=YEARS) -> None:
    ok = d["employees"].notna()
    log.info("SEC headcount: %d filings, %d with a headcount (%.0f%%) -> %s", len(d), int(ok.sum()), 100 * ok.mean() if len(d) else 0,
             RAW / "sec_headcount.csv")
    log.info("Companies with a headcount in every year %s: %d", list(years),
             int((d[ok].groupby("cik")["period_year"].nunique() == len(years)).sum()))
    log.info("Check by hand: 10 random sentences\n%s", d[ok].sample(min(10, int(ok.sum())), random_state=0)[["cik", "period_year", "employees", "snippet"]]
             .to_string(index=False) if ok.any() else "(none)")


SOURCES = {"sec_headcount": lambda a: collect()}
