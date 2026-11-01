import numpy as np
import pandas as pd

from collectors import prices


def frame(tickers, ticker_first=True, tz=None):
    idx = pd.date_range("2022-01-03", periods=4, freq="B", tz=tz)
    cols = [(t, f) if ticker_first else (f, t) for t in tickers for f in ("Close", "Volume")]
    df = pd.DataFrame(np.arange(len(idx) * len(cols), dtype=float).reshape(len(idx), len(cols)) + 1,
                      index=idx, columns=pd.MultiIndex.from_tuples(cols))
    return df


def test_symbols_and_ticker_list():
    assert prices.yahoo_symbol("brk.b ") == "BRK-B"
    m = pd.DataFrame({"ticker": ["MSFT", None, "", "brk.b", "MSFT"]})
    assert prices.event_tickers(m) == ["BRK-B", "MSFT"]


def test_tidy_handles_both_column_layouts_and_timezones():
    for first in (True, False):
        for tz in (None, "America/New_York"):
            out = prices.tidy(frame(["AAA", "BBB"], first, tz), ["AAA", "BBB"])
            assert set(out["ticker"]) == {"AAA", "BBB"} and len(out) == 8 and out["date"].dt.tz is None
            assert list(out.columns) == prices.COLUMNS


def test_tidy_flat_single_ticker_and_empty():
    flat = pd.DataFrame({"Close": [1.0, 2.0], "Volume": [10, 20]}, index=pd.date_range("2022-01-03", periods=2, freq="B"))
    assert list(prices.tidy(flat, ["ZZZ"])["ticker"]) == ["ZZZ", "ZZZ"]
    assert prices.tidy(pd.DataFrame(), ["A"]).empty and prices.tidy(None, ["A"]).empty


def test_tidy_drops_rows_without_a_price():
    df = frame(["AAA"])
    df.iloc[1, 0] = np.nan
    assert len(prices.tidy(df, ["AAA"])) == 3


def test_download_survives_a_failing_batch_and_reports_missing():
    calls = []

    def fake(batch, start, end):
        calls.append(list(batch))
        if "BAD" in batch:
            raise RuntimeError("rate limited")
        return frame([t for t in batch if t != "GONE"])

    got, missing = prices.download_prices(["AAA", "BBB", "BAD", "GONE"], batch=2, downloader=fake)
    assert calls == [["AAA", "BBB"], ["BAD", "GONE"]]
    assert set(got["ticker"]) == {"AAA", "BBB"} and missing == ["BAD", "GONE"]


def test_collect_only_fetches_missing_tickers_and_merges(data_dir, monkeypatch):
    raw = data_dir / "raw"
    monkeypatch.setattr(prices, "RAW", raw)
    pd.DataFrame({"ticker": ["AAA", "BBB"], "cik": [1, 2]}).to_csv(raw / "sec_company_matches.csv", index=False)
    old = pd.DataFrame({"ticker": "AAA", "date": pd.date_range("2022-01-03", periods=2, freq="B"), "adj_close": [1.0, 2.0], "volume": [1, 1]})
    old.to_csv(raw / "prices_daily.csv", index=False)
    asked = []

    def fake(batch, start, end):
        asked.append(list(batch))
        return frame(batch)

    monkeypatch.setattr(prices, "_download", fake)
    monkeypatch.setattr(prices.time, "sleep", lambda s: None)
    out = prices.collect()
    saved = pd.read_csv(raw / "prices_daily.csv")
    assert set(saved["ticker"]) == {"AAA", "BBB", "^GSPC", "^IXIC"} and out[0]["file"].endswith("prices_daily.csv")
    assert asked == [["BBB", "^GSPC", "^IXIC"]]                          # AAA was already there


def test_source_registered():
    assert "prices" in prices.SOURCES
