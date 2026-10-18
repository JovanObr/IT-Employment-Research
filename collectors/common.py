"""Shared helpers: a polite, cached HTTP client and manifest records."""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("covid_it_data")

DATA = Path(os.environ.get("DATA_DIR", "data"))
CACHE = DATA / "cache"          # raw HTTP responses (so re-runs cost nothing)
RAW = DATA / "raw"              # tidy CSVs straight from each source
PROCESSED = DATA / "processed"  # cleaned / merged outputs
MANUAL = DATA / "manual"        # files you download by hand (see README)

_session: requests.Session | None = None


def ensure_dirs() -> None:
    for p in (CACHE, RAW, PROCESSED, MANUAL):
        p.mkdir(parents=True, exist_ok=True)


def session() -> requests.Session:
    """One shared session: retries with backoff + an honest User-Agent."""
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(
            total=4,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        s.mount("https://", HTTPAdapter(max_retries=retry))
        contact = os.environ.get("CONTACT_EMAIL", "")
        s.headers["User-Agent"] = (
            f"covid-it-employment-student-research/0.1 ({contact})".strip()
        )
        _session = s
    return _session


def fetch(
    url: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    cache_key: str | None = None,
    max_age_days: float = 7,
    delay: float = 0.5,
    cache_ok=None,
) -> bytes:
    """GET (or POST if json_body given) with an on-disk cache and a polite delay.
    cache_ok: optional function(bytes) -> bool; only replies it accepts are cached."""
    ensure_dirs()
    key = cache_key or f"{url}|{sorted((params or {}).items())}"
    path = CACHE / (hashlib.sha1(key.encode()).hexdigest() + ".bin")
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_days * 86400:
        return path.read_bytes()
    method = "POST" if json_body is not None else "GET"
    r = session().request(method, url, params=params, json=json_body, timeout=90)
    r.raise_for_status()
    # Never cache an empty reply, or one the caller says is not real data (e.g. an HTML error page):
    # it would stick for the whole cache lifetime and survive fixing the cause (like a missing API key).
    if r.content and (cache_ok is None or cache_ok(r.content)):
        path.write_bytes(r.content)
    time.sleep(delay)
    return r.content


def record(source: str, file: Path, url: str, licence: str) -> dict:
    """One manifest entry: where a file came from and how to credit it."""
    return {
        "source": source,
        "file": str(file),
        "url": url,
        "licence_or_terms": licence,
        "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
