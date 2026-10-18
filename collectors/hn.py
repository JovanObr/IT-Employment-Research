"""Hacker News 'Ask HN: Who is hiring?' monthly threads -> post-level features.

Source: the public Algolia HN Search API (no key). One request per monthly thread
(~140 for 2015-2026), cached on disk. Terms: public Hacker News content; keep the raw text
local for your own analysis and do not redistribute it. Posts skew to startups/tech, so this
shows how *that* corner of the market changed (remote work, seniority, skills), not the whole market.

Outputs:
  hn_whoishiring_posts.csv  one row per top-level job post: flags (remote, junior, AI...) + skills
  hn_whoishiring_text.csv   post_id + cleaned text (for NLP later)

FEASIBILITY TEST 3 (set in advance): pass if >= 40,000 posts parsed AND the share of posts
mentioning 'remote' differs by >= 5 percentage points between 2019 and 2021.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re

import pandas as pd

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

BASE = "https://hn.algolia.com/api/v1"
LICENCE = "Public Hacker News content via Algolia API: derived features for personal analysis, do not redistribute raw text"
TITLE_RE = re.compile(r"^Ask HN: Who is hiring\?\s*\((\w+)\s+(\d{4})\)", re.I)
I = re.IGNORECASE

# name -> list of (regex, flags); any match = 1. Simple keyword rules: they miss negations
# ("no remote") and context, so treat shares as indicators, not exact counts.
FLAGS = {
    "remote": [(r"\bremote\b", I)],
    "onsite": [(r"\bon-?\s?site\b", I)],
    "hybrid": [(r"\bhybrid\b", I)],
    "junior": [(r"\b(junior|interns?|internships?|entry[- ]level|new grad|graduates?)\b", I)],
    "senior": [(r"\b(senior|staff|principal|lead)\b", I)],
    "visa": [(r"\b(visa|h-?1b|relocation)\b", I)],
    "ai_ml": [(r"\bAI\b|\bML\b|\bLLMs?\b", 0),
              (r"machine learning|deep learning|generative ai|\bgpt\b|\bnlp\b", I)],
    "games": [(r"\bunity\b|\bunreal\b|game ?(dev|develop|engine|play)|gameplay|\bgaming\b", I)],
}
SKILLS = {
    "python": [(r"\bpython\b", I)], "javascript": [(r"\bjavascript\b|\bnode\.?js\b", I)],
    "typescript": [(r"\btypescript\b", I)], "react": [(r"\breact(\.js|js)?\b", I)],
    "java": [(r"\bjava\b", I)], "golang": [(r"\bgolang\b", I)], "rust": [(r"\brust\b", I)],
    "cpp": [(r"c\+\+", I)], "csharp": [(r"c#|\.net\b", I)], "ruby": [(r"\bruby\b|\brails\b", I)],
    "php": [(r"\bphp\b", I)], "swift_ios": [(r"\bswift\b|\bios\b", I)], "kotlin_android": [(r"\bkotlin\b|\bandroid\b", I)],
    "scala": [(r"\bscala\b", I)], "elixir": [(r"\belixir\b", I)],
    "aws": [(r"\baws\b", I)], "gcp": [(r"\bgcp\b|google cloud", I)], "azure": [(r"\bazure\b", I)],
    "kubernetes": [(r"\bkubernetes\b|\bk8s\b", I)], "docker": [(r"\bdocker\b", I)],
    "terraform": [(r"\bterraform\b", I)], "postgres": [(r"\bpostgres(ql)?\b", I)],
    "sql": [(r"\bsql\b", I)], "graphql": [(r"\bgraphql\b", I)], "spark": [(r"\bspark\b", I)],
    "pytorch_tf": [(r"\bpytorch\b|\btensorflow\b", I)],
    "security": [(r"\bsecurity\b|\bappsec\b", I)], "blockchain": [(r"\bblockchain\b|\bcrypto\b|\bweb3\b", I)],
}
_COMPILED = {k: [re.compile(p, f) for p, f in v] for k, v in {**FLAGS, **SKILLS}.items()}


def clean_html(text: str | None) -> str:
    if not text:
        return ""
    t = re.sub(r"<\s*(p|br)\s*/?>", "\n", text, flags=I)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip()


def features(text: str) -> dict:
    out = {k: int(any(p.search(text) for p in pats)) for k, pats in _COMPILED.items()}
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    out["first_line"] = first[:200]
    out["company_guess"] = first.split("|")[0].strip()[:80] if "|" in first else ""
    out["text_len"] = len(text)
    return out


def _month(match, hit) -> dt.date:
    try:
        return dt.datetime.strptime(f"{match.group(1)} {match.group(2)}", "%B %Y").date()
    except ValueError:
        d = dt.datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
        return d.date().replace(day=1)


def list_threads(start_year: int) -> list[dict]:
    out, seen, page = [], set(), 0
    while True:
        raw = fetch(f"{BASE}/search_by_date",
                    params={"tags": "story,author_whoishiring", "hitsPerPage": 1000, "page": page},
                    max_age_days=1)
        j = json.loads(raw)
        for h in j.get("hits", []):
            m = TITLE_RE.match(h.get("title") or "")
            if not m or h["objectID"] in seen:
                continue
            seen.add(h["objectID"])
            month = _month(m, h)
            if month.year >= start_year:
                out.append({"id": h["objectID"], "month": month, "created": h["created_at"]})
        page += 1
        if page >= j.get("nbPages", 1):
            break
    return sorted(out, key=lambda t: t["month"])


def feasibility(df: pd.DataFrame) -> None:
    n = len(df)
    by_year = df.assign(year=df["thread_month"].str[:4]).groupby("year").agg(
        posts=("post_id", "size"), remote=("remote", "mean"), junior=("junior", "mean"), ai_ml=("ai_ml", "mean"))
    log.info("HN posts per year and share mentioning remote / junior / AI-ML:\n%s", by_year.round(3).to_string())
    try:
        jump = by_year.loc["2021", "remote"] - by_year.loc["2019", "remote"]
        ok = n >= 40_000 and abs(jump) >= 0.05
        log.info("FEASIBILITY TEST 3 (HN text): %s - %d posts (need 40,000), remote share 2021 vs 2019: %+.1f pp (need >= 5)",
                 "PASS" if ok else "FAIL", n, jump * 100)
    except KeyError:
        log.info("FEASIBILITY TEST 3: cannot evaluate (need 2019 and 2021 threads; use --start-year 2019 or earlier)")


def collect(start_year: int = 2015) -> list[dict]:
    ensure_dirs()
    threads = list_threads(start_year)
    log.info("HN: %d 'Who is hiring?' threads from %s", len(threads), start_year)
    rows, texts = [], []
    now = dt.datetime.now(dt.timezone.utc)
    for t in threads:
        age = (now - dt.datetime.fromisoformat(t["created"].replace("Z", "+00:00"))).days
        try:
            item = json.loads(fetch(f"{BASE}/items/{t['id']}", max_age_days=1 if age < 45 else 365, delay=0.6))
        except Exception as e:
            log.warning("HN thread %s (%s) failed: %s", t["id"], t["month"], e)
            continue
        n0 = len(rows)
        for c in item.get("children") or []:
            text = clean_html(c.get("text"))
            if not text:
                continue
            row = {"thread_id": t["id"], "thread_month": t["month"].isoformat(),
                   "post_id": c["id"], "created_at": c.get("created_at", ""), **features(text)}
            rows.append(row)
            texts.append({"post_id": c["id"], "text": text})
        log.debug("HN %s: %d posts", t["month"], len(rows) - n0)
    if not rows:
        return []
    df = pd.DataFrame(rows).drop_duplicates("post_id")
    out, out_t = RAW / "hn_whoishiring_posts.csv", RAW / "hn_whoishiring_text.csv"
    df.to_csv(out, index=False)
    pd.DataFrame(texts).drop_duplicates("post_id").to_csv(out_t, index=False)
    log.info("HN: %d posts -> %s", len(df), out)
    feasibility(df)
    return [record("Hacker News 'Who is hiring?' (features)", out, BASE, LICENCE),
            record("Hacker News 'Who is hiring?' (text)", out_t, BASE, LICENCE)]
