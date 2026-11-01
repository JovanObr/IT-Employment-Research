"""Daily adjusted prices (Yahoo Finance via the `yfinance` package) for the layoff-announcement event study.

Terms: Yahoo's data is for personal / research use and must not be redistributed, so `data/raw/prices_daily.csv` stays local
(data/raw is not committed) and only our own aggregated results are published. yfinance is an unofficial client: it can be
rate-limited or break; if a batch fails the others still run, and a re-run only downloads tickers that are still missing.

Which tickers: companies matched to an SEC filer (data/raw/sec_company_matches.csv, column `ticker`; blank for delisted
companies, which therefore have no prices: this biases the study towards survivors), plus two benchmarks (^IXIC NASDAQ
Composite, ^GSPC S&P 500). Source name: `prices`.
"""
from __future__ import annotations

import logging
import time
import warnings

import pandas as pd

from .common import RAW, ensure_dirs, record

log = logging.getLogger("covid_it_data")

START = "2019-01-01"          # 250 trading days of history before the first tracker event (March 2020)
BENCHMARKS = ["^IXIC", "^GSPC"]
COLUMNS = ["ticker", "date", "adj_close", "volume"]
TERMS = "Yahoo Finance data: personal/research use only, do not redistribute (kept out of git)"


def yahoo_symbol(ticker: str) -> str:
    """SEC tickers use '.' for share classes where Yahoo uses '-' (BRK.B -> BRK-B)."""
    return str(ticker).strip().upper().replace(".", "-")


def event_tickers(matches: pd.DataFrame) -> list[str]:
    t = matches["ticker"].dropna().astype(str).str.strip()
    return sorted({yahoo_symbol(x) for x in t if x})


def _one(sub: pd.DataFrame, ticker: str) -> pd.DataFrame:
    close = "Close" if "Close" in sub.columns else "Adj Close"
    out = pd.DataFrame({"ticker": ticker, "date": pd.to_datetime(sub.index).tz_localize(None).normalize(),
                        "adj_close": pd.to_numeric(sub[close].to_numpy(), errors="coerce"),
                        "volume": pd.to_numeric(sub["Volume"].to_numpy(), errors="coerce") if "Volume" in sub.columns else float("nan")})
    return out.dropna(subset=["adj_close"])


def tidy(df: pd.DataFrame | None, tickers: list[str]) -> pd.DataFrame:
    """yfinance reply (one or many tickers, ticker level first or second, or flat for one ticker) -> long table."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLUMNS)
    if isinstance(df.columns, pd.MultiIndex):
        level = 0 if set(df.columns.get_level_values(0)) & set(tickers) else 1
        parts = [_one(df.xs(t, axis=1, level=level), t) for t in dict.fromkeys(df.columns.get_level_values(level))]
    else:
        parts = [_one(df, tickers[0])]
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS)


def _download(batch: list[str], start: str, end: str | None) -> pd.DataFrame:
    import yfinance as yf                          # imported here so tests and CI do not need it
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", module=r"yfinance.*")      # pandas deprecation noise from inside yfinance
        return yf.download(batch, start=start, end=end, auto_adjust=True, progress=False, group_by="ticker", threads=True)


def download_prices(tickers: list[str], start: str = START, end: str | None = None, batch: int = 40, pause: float = 1.0,
                    downloader=None) -> tuple[pd.DataFrame, list[str]]:
    """Long table of daily adjusted closes and the list of tickers that returned nothing."""
    parts = []
    dl = downloader or _download                    # looked up at call time so tests can replace it
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        try:
            parts.append(tidy(dl(chunk, start, end), chunk))
        except Exception as e:  # noqa: BLE001 - one failing batch must not stop the rest
            log.error("prices: batch %d-%d failed: %s", i, i + len(chunk), e)
        if downloader is None:
            time.sleep(pause)
        log.info("prices: %d / %d tickers requested", min(i + batch, len(tickers)), len(tickers))
    got = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS)
    return got, sorted(set(tickers) - set(got["ticker"]))


def collect(start_year: int = 2015) -> list[dict]:
    ensure_dirs()
    path = RAW / "sec_company_matches.csv"
    if not path.exists():
        log.warning("%s not found: run the sec step first", path)
        return []
    wanted = sorted(set(event_tickers(pd.read_csv(path))) | set(BENCHMARKS))
    out = RAW / "prices_daily.csv"
    have = pd.read_csv(out, parse_dates=["date"]) if out.exists() else pd.DataFrame(columns=COLUMNS)
    todo = [t for t in wanted if t not in set(have["ticker"])]
    log.info("prices: %d tickers wanted, %d already downloaded, %d to fetch", len(wanted), len(wanted) - len(todo), len(todo))
    new, missing = download_prices(todo)
    allp = pd.concat([have, new], ignore_index=True).drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"])
    allp.to_csv(out, index=False)
    log.info("prices: %d rows for %d tickers -> %s", len(allp), allp["ticker"].nunique(), out)
    if missing:
        log.info("prices: no data for %d tickers (delisted, renamed or blocked): %s", len(missing), ", ".join(missing[:40]))
    return [record("Yahoo Finance via yfinance: daily adjusted prices", out, "https://finance.yahoo.com/", TERMS)]


SOURCES = {"prices": lambda a: collect(a.start_year)}
