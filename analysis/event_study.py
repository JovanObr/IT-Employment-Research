"""Event study: how do share prices move around layoff announcements? (milestone chapter 6, notebook 07)

Method (the standard market model):
  1. Day 0 is the first trading day on or after the tracker date. The tracker gives a date, not a time, and many announcements come
     after the close, so the announcement window is days 0 and +1.
  2. For each event, fit  stock return = alpha + beta * market return  on the 220 trading days from -250 to -30 (needs 120+ valid days;
     market = NASDAQ Composite, ^IXIC).
  3. Abnormal return = actual return minus what the fit predicts. CAR(a, b) = sum of abnormal returns on days a..b.
  Windows: pre_5_2 (days -5..-2, a check for leaks or reverse causation), pre_1, ann_0_1 (the announcement), post_2_5 (drift afterwards).
  4. Test: mean CAR across events, with a 95 % interval from resampling whole CALENDAR DAYS (events on the same day share market news),
     a Patell Z, and a placebo check: the same test on random non-event dates must reject about 5 % of the time.
Limits that no code removes: layoffs are often announced together with earnings or guidance; delisted companies have no prices
(survivors only); the tracker date may be a day late; small samples per sub-group.

Run:  python -m analysis.event_study     (needs: sec, sec_universe, sec_fin, layoffs, prices)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from analysis.company_panel import qindex
from collectors.common import PROCESSED, RAW
from collectors.prices import yahoo_symbol

log = logging.getLogger("covid_it_data")

ESTIMATION = (-250, -30)
MIN_EST_OBS = 120
BENCH = "^IXIC"
WINDOWS = {"pre_5_2": (-5, -2), "pre_1": (-1, -1), "ann_0_1": (0, 1), "post_2_5": (2, 5)}
MAIN = "ann_0_1"


# ---------------------------------------------------------------------------------------- inputs
def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Wide table (date x ticker) of simple daily returns from adjusted closes."""
    p = prices.sort_values(["ticker", "date"]).copy()
    p["ret"] = p.groupby("ticker")["adj_close"].pct_change()
    return p.pivot(index="date", columns="ticker", values="ret").sort_index()


def extreme_daily_returns(returns: pd.DataFrame, k: int = 15) -> pd.DataFrame:
    """The k largest absolute daily returns in the whole table (ticker, date, return in per cent). Returns far beyond +-100 %
    in a day are usually data glitches (bad ticks, unadjusted splits) and distort averages."""
    r = returns.drop(columns=[c for c in returns.columns if str(c).startswith("^")], errors="ignore")
    s = r.stack().rename("ret_pct") * 100
    top = s.reindex(s.abs().sort_values(ascending=False).index).head(k).reset_index()
    top.columns = ["date", "ticker", "ret_pct"]
    return top[["ticker", "date", "ret_pct"]]


def clean_returns(returns: pd.DataFrame, max_abs: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Blank out daily returns beyond +-max_abs (default +-100 %: a price that doubles in a day) for every stock; benchmarks are left alone.
    Such values are almost always data glitches (bad ticks, unadjusted splits, delisting artefacts). A blanked day is treated as missing:
    the market-model fit skips it, and an event whose window contains one has no CAR for that window. Returns the cleaned table and a
    report (ticker, n_masked, largest) so nothing is hidden."""
    stocks = [c for c in returns.columns if not str(c).startswith("^")]
    bad = returns[stocks].abs() > max_abs
    cleaned = returns.copy()
    cleaned[stocks] = returns[stocks].mask(bad)
    n = bad.sum()
    rep = pd.DataFrame({"ticker": n[n > 0].index, "n_masked": n[n > 0].to_numpy(),
                        "largest_pct": [100 * float(returns[t][bad[t]].abs().max()) for t in n[n > 0].index]})
    return cleaned, rep.sort_values("n_masked", ascending=False).reset_index(drop=True)


def prepare_returns(prices: pd.DataFrame, max_abs: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily returns from prices with glitches blanked: the single entry point used by the analysis and the figures."""
    return clean_returns(daily_returns(prices), max_abs)


def drop_clustered(events: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """Keep the first event of a company and drop later ones within `days` calendar days of the last kept one (they are
    follow-ups of the same news, and their estimation window would contain the first event)."""
    keep = []
    for _, g in events.sort_values(["cik", "date"]).groupby("cik"):
        last = None
        for idx, d in g["date"].items():
            if last is None or (d - last).days >= days:
                keep.append(idx)
                last = d
    return events.loc[keep].sort_values("date").reset_index(drop=True)


def build_events(layoffs: pd.DataFrame, matches: pd.DataFrame, min_gap_days: int = 30) -> pd.DataFrame:
    """Tracker events of companies matched to an SEC filer with a ticker: columns event_id, cik, ticker, date."""
    m = matches.dropna(subset=["ticker"]).copy()
    m = m[m["ticker"].astype(str).str.strip() != ""]
    m["ticker"] = m["ticker"].map(yahoo_symbol)
    e = layoffs.dropna(subset=["date", "company"]).merge(m[["layoffs_company", "cik", "ticker"]],
                                                         left_on="company", right_on="layoffs_company")
    e = e.drop_duplicates(["cik", "date"])[["cik", "ticker", "date"]].reset_index(drop=True)
    e["date"] = pd.to_datetime(e["date"]).dt.normalize()
    e = drop_clustered(e, min_gap_days)
    e.insert(0, "event_id", range(len(e)))
    return e


# ---------------------------------------------------------------------------------------- one event
def event_position(date, days: pd.DatetimeIndex) -> int | None:
    """Index of the first trading day on or after `date` (a weekend or holiday event moves to the next trading day)."""
    pos = int(days.searchsorted(pd.Timestamp(date).normalize(), side="left"))
    return pos if pos < len(days) else None


def market_model(ri: np.ndarray, rm: np.ndarray, pos: int, est=ESTIMATION, min_obs: int = MIN_EST_OBS):
    """(alpha, beta, residual sd, n observations) fitted on the estimation window, or None if there is too little history."""
    lo, hi = pos + est[0], pos + est[1]
    if lo < 0:
        return None
    x, y = rm[lo:hi + 1], ri[lo:hi + 1]
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < min_obs or np.var(x[ok]) == 0:
        return None
    x, y = x[ok], y[ok]
    beta = np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1)
    alpha = y.mean() - beta * x.mean()
    sd = float(np.std(y - (alpha + beta * x), ddof=2))
    return float(alpha), float(beta), sd, n


def cars_at(ri: np.ndarray, rm: np.ndarray, pos: int, windows=WINDOWS, est=ESTIMATION) -> dict | None:
    """Model fit and CAR / standardised CAR for every window around day `pos`; None if the data do not reach."""
    fit = market_model(ri, rm, pos, est)
    tmin, tmax = min(w[0] for w in windows.values()), max(w[1] for w in windows.values())
    if fit is None or pos + tmin < 0 or pos + tmax >= len(ri):
        return None
    alpha, beta, sd, n = fit
    t = np.arange(tmin, tmax + 1)
    ar = ri[pos + tmin:pos + tmax + 1] - (alpha + beta * rm[pos + tmin:pos + tmax + 1])
    out = {"alpha": alpha, "beta": beta, "resid_sd": sd, "n_est": n}
    for name, (a, b) in windows.items():
        seg = ar[(t >= a) & (t <= b)]
        car = float(seg.sum()) if np.isfinite(seg).all() else np.nan
        out[f"car_{name}"] = car
        out[f"t_{name}"] = car / (sd * np.sqrt(b - a + 1)) if sd > 0 else np.nan
    return out


def run_event_study(events: pd.DataFrame, returns: pd.DataFrame, bench: str = BENCH, windows=WINDOWS) -> tuple[pd.DataFrame, dict]:
    """One row per usable event. Also returns how many events were lost and why."""
    if bench not in returns:
        raise KeyError(f"benchmark {bench} is missing from the returns table")
    rm_all = returns[bench]
    days = rm_all.dropna().index
    rm = rm_all.reindex(days).to_numpy(float)
    rows, lost = [], {"no_prices": 0, "after_last_day": 0, "too_little_history_or_window": 0}
    for e in events.itertuples(index=False):
        if e.ticker not in returns:
            lost["no_prices"] += 1
            continue
        pos = event_position(e.date, days)
        if pos is None:
            lost["after_last_day"] += 1
            continue
        ri = returns[e.ticker].reindex(days).to_numpy(float)
        res = cars_at(ri, rm, pos, windows)
        if res is None:
            lost["too_little_history_or_window"] += 1
            continue
        rows.append({"event_id": e.event_id, "cik": e.cik, "ticker": e.ticker, "date": e.date, "event_day": days[pos], **res})
    return pd.DataFrame(rows), lost


# ---------------------------------------------------------------------------------------- tests and groups
def _cluster_bootstrap_mean(values: np.ndarray, clusters: np.ndarray, n_boot: int, rng) -> tuple[float, float]:
    codes, inv = np.unique(clusters, return_inverse=True)
    sums = np.bincount(inv, weights=values, minlength=len(codes))
    cnt = np.bincount(inv, minlength=len(codes)).astype(float)
    idx = rng.integers(0, len(codes), (n_boot, len(codes)))
    means = sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize(cars: pd.DataFrame, window: str = MAIN, n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean and median CAR in per cent, share of events with a positive CAR, simple t, Patell Z and a 95 % interval that
    resamples whole calendar days."""
    d = cars.dropna(subset=[f"car_{window}"])
    v = d[f"car_{window}"].to_numpy(float)
    n = len(v)
    if n < 2:
        return {"window": window, "n": n}
    z_i = d[f"t_{window}"].to_numpy(float) / np.sqrt((d["n_est"].to_numpy(float) - 4) / (d["n_est"].to_numpy(float) - 2))
    lo, hi = _cluster_bootstrap_mean(v, d["event_day"].to_numpy(), n_boot, np.random.default_rng(seed))
    return {"window": window, "n": n, "mean_pct": 100 * v.mean(), "median_pct": 100 * np.median(v),
            "share_positive": float((v > 0).mean()), "t": float(v.mean() / (v.std(ddof=1) / np.sqrt(n))),
            "patell_z": float(np.nansum(z_i) / np.sqrt(np.isfinite(z_i).sum())),
            "ci_lo_pct": 100 * lo, "ci_hi_pct": 100 * hi}


def summary_table(cars: pd.DataFrame, windows=WINDOWS, **kw) -> pd.DataFrame:
    return pd.DataFrame([summarize(cars, w, **kw) for w in windows])


def group_summary(cars: pd.DataFrame, by: str, window: str = MAIN, min_n: int = 20, n_boot: int = 1000) -> pd.DataFrame:
    """Mean CAR per group (e.g. year, size group); groups with fewer than `min_n` events get no interval."""
    rows = []
    for g, part in cars.groupby(by, observed=True):
        s = summarize(part, window, n_boot=n_boot) if len(part) >= min_n else summarize(part, window, n_boot=2)
        if len(part) < min_n:
            s["ci_lo_pct"] = s["ci_hi_pct"] = np.nan
        rows.append({by: g, **s})
    return pd.DataFrame(rows)


def placebo_test(events_used: pd.DataFrame, returns: pd.DataFrame, n_rep: int = 200, seed: int = 0, window: str = MAIN,
                 bench: str = BENCH, exclude_days: int = 10, n_boot: int = 300) -> dict:
    """The same test on random non-event days of the same companies. If the method is sound the mean CAR is about 0 and
    |t| > 1.96 happens in about 5 % of repetitions."""
    rng = np.random.default_rng(seed)
    days = returns[bench].dropna().index
    rm = returns[bench].reindex(days).to_numpy(float)
    a, b = WINDOWS[window]
    per_event = []
    for e in events_used.itertuples(index=False):
        ri = returns[e.ticker].reindex(days).to_numpy(float)
        real = [event_position(d, days) for d in events_used.loc[events_used["ticker"] == e.ticker, "date"]]
        lo, hi = -ESTIMATION[0], len(days) - max(w[1] for w in WINDOWS.values()) - 1
        cand = np.array([p for p in range(lo, hi) if all(abs(p - r) > exclude_days for r in real if r is not None)])
        per_event.append((ri, cand))
    means, ts, zs, medians, boot_reject = [], [], [], [], []
    rng_b = np.random.default_rng(seed + 1)
    for _ in range(n_rep):
        v, z, dd = [], [], []
        for ri, cand in per_event:
            if not len(cand):
                continue
            p = int(rng.choice(cand))
            res = cars_at(ri, rm, p, {window: (a, b)})
            if res is not None and np.isfinite(res[f"car_{window}"]):
                v.append(res[f"car_{window}"])
                z.append(res[f"t_{window}"] / np.sqrt((res["n_est"] - 4) / (res["n_est"] - 2)))
                dd.append(days[p])
        v, z = np.array(v), np.array(z)
        lo_b, hi_b = _cluster_bootstrap_mean(v, np.array(dd), n_boot, rng_b)
        boot_reject.append(lo_b > 0 or hi_b < 0)
        means.append(v.mean())
        medians.append(np.median(v))
        ts.append(v.mean() / (v.std(ddof=1) / np.sqrt(len(v))))
        zs.append(np.nansum(z) / np.sqrt(np.isfinite(z).sum()))
    ts, zs = np.array(ts), np.array(zs)
    return {"n_rep": n_rep, "mean_of_means_pct": 100 * float(np.mean(means)), "sd_of_means_pct": 100 * float(np.std(means)),
            "sd_of_medians_pct": 100 * float(np.std(medians)),
            "false_positive_rate": float((np.abs(ts) > 1.96).mean()),
            "patell_false_positive_rate": float((np.abs(zs) > 1.96).mean()),
            "bootstrap_false_positive_rate": float(np.mean(boot_reject))}


# ---------------------------------------------------------------------------------------- robustness
def winsorize_cars(cars: pd.DataFrame, p: float = 0.01) -> pd.DataFrame:
    """Clip every CAR and standardised-CAR column at its p and 1-p quantiles, so a handful of extreme moves cannot decide the average."""
    out = cars.copy()
    for c in [c for c in out.columns if c.startswith(("car_", "t_"))]:
        lo, hi = out[c].quantile(p), out[c].quantile(1 - p)
        out[c] = out[c].clip(lo, hi)
    return out


def largest_moves(cars: pd.DataFrame, window: str = MAIN, k: int = 10) -> pd.DataFrame:
    """The k events with the biggest absolute CAR: look at these by hand for data errors, splits or takeover news."""
    d = cars.dropna(subset=[f"car_{window}"]).copy()
    d["car_pct"] = 100 * d[f"car_{window}"]
    return d.reindex(d["car_pct"].abs().sort_values(ascending=False).index).head(k)[["ticker", "date", "car_pct", "beta", "resid_sd"]]


def group_difference(cars: pd.DataFrame, by: str, a, b, window: str = MAIN, n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean CAR of group a minus group b (in per cent) with a 95 % interval from resampling calendar days jointly for both groups."""
    col = f"car_{window}"
    d = cars.dropna(subset=[col])
    A, B = d[d[by] == a], d[d[by] == b]
    days = np.unique(np.concatenate([A["event_day"].to_numpy(), B["event_day"].to_numpy()]))
    pos = {x: i for i, x in enumerate(days)}

    def per_day(g):
        idx = np.array([pos[x] for x in g["event_day"]])
        return (np.bincount(idx, weights=g[col].to_numpy(float), minlength=len(days)),
                np.bincount(idx, minlength=len(days)).astype(float))

    (sa, ca), (sb, cb) = per_day(A), per_day(B)
    draws = np.random.default_rng(seed).integers(0, len(days), (n_boot, len(days)))
    with np.errstate(invalid="ignore", divide="ignore"):
        diffs = sa[draws].sum(1) / ca[draws].sum(1) - sb[draws].sum(1) / cb[draws].sum(1)
    diffs = diffs[np.isfinite(diffs)]
    return {"group_a": a, "group_b": b, "n_a": len(A), "n_b": len(B),
            "diff_pct": 100 * (A[col].mean() - B[col].mean()),
            "ci_lo_pct": 100 * float(np.percentile(diffs, 2.5)), "ci_hi_pct": 100 * float(np.percentile(diffs, 97.5))}


def abnormal_path(ri: np.ndarray, rm: np.ndarray, pos: int, tmin: int = -5, tmax: int = 10, est=ESTIMATION) -> np.ndarray | None:
    """Abnormal return on each day tmin..tmax around day `pos` (None if the model cannot be fitted or the data stop)."""
    fit = market_model(ri, rm, pos, est)
    if fit is None or pos + tmin < 0 or pos + tmax >= len(ri):
        return None
    alpha, beta, _, _ = fit
    return ri[pos + tmin:pos + tmax + 1] - (alpha + beta * rm[pos + tmin:pos + tmax + 1])


def ar_paths(events: pd.DataFrame, returns: pd.DataFrame, bench: str = BENCH, tmin: int = -5, tmax: int = 10) -> pd.DataFrame:
    """One row per usable event: its event day and abnormal return on days tmin..tmax (columns are the day numbers)."""
    days = returns[bench].dropna().index
    rm = returns[bench].reindex(days).to_numpy(float)
    rows = []
    for e in events.itertuples(index=False):
        if e.ticker not in returns:
            continue
        pos = event_position(e.date, days)
        if pos is None:
            continue
        ar = abnormal_path(returns[e.ticker].reindex(days).to_numpy(float), rm, pos, tmin, tmax)
        if ar is not None and np.isfinite(ar).all():
            rows.append({"event_id": e.event_id, "event_day": days[pos], **dict(zip(range(tmin, tmax + 1), ar))})
    return pd.DataFrame(rows)


def path_summary(paths: pd.DataFrame, n_boot: int = 1000, seed: int = 0, winsor: float | None = 0.01) -> pd.DataFrame:
    """Average cumulative abnormal return (in per cent, counted from the first day of the path) for each day, with a 95 %
    interval that resamples whole calendar days. `winsor` clips each day's abnormal return so single extreme moves do not dominate."""
    tcols = [c for c in paths.columns if isinstance(c, (int, np.integer))]
    ar = paths[tcols].copy()
    if winsor:
        ar = ar.clip(ar.quantile(winsor), ar.quantile(1 - winsor), axis=1)
    cum = ar.cumsum(axis=1).to_numpy(float)
    rng = np.random.default_rng(seed)
    out = []
    for j, t in enumerate(tcols):
        lo, hi = _cluster_bootstrap_mean(cum[:, j], paths["event_day"].to_numpy(), n_boot, np.random.default_rng(seed))
        out.append({"t": t, "mean_pct": 100 * cum[:, j].mean(), "lo_pct": 100 * lo, "hi_pct": 100 * hi, "n": len(paths)})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------------------- company size
def _quarter_end(period: str) -> pd.Timestamp:
    qi = qindex(period)
    return pd.Timestamp(year=qi // 4, month=3 * (qi % 4) + 3, day=1) + pd.offsets.MonthEnd(0)


def attach_size(events: pd.DataFrame, fin: pd.DataFrame, filing_lag_days: int = 45) -> pd.DataFrame:
    """Add log total assets from the latest balance sheet that was public BEFORE the event (quarter end + lag)."""
    a = fin[(fin["concept"] == "assets") & (fin["kind"] == "instant") & (fin["value"] > 0)].copy()
    a["available"] = a["period"].map(_quarter_end) + pd.Timedelta(days=filing_lag_days)
    a["log_assets"] = np.log(a["value"])
    a = a.sort_values("available")[["cik", "available", "log_assets"]]
    e = events.sort_values("date")
    out = pd.merge_asof(e, a, left_on="date", right_on="available", by="cik", direction="backward")
    return out.drop(columns="available").sort_values("event_id").reset_index(drop=True)


def add_size_groups(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    out = df.copy()
    out["size_group"] = pd.qcut(out["log_assets"], n, labels=["najmanjša tretjina", "srednja tretjina", "največja tretjina"][:n]
                                if n == 3 else False)
    return out


# ---------------------------------------------------------------------------------------- run
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    need = {"layoffs": PROCESSED / "layoffs_clean.csv", "matches": RAW / "sec_company_matches.csv",
            "prices": RAW / "prices_daily.csv", "fin": RAW / "sec_financials_quarterly.csv"}
    missing = [str(p) for p in need.values() if not p.exists()]
    if missing:
        raise SystemExit("Missing inputs (run collect.py for layoffs, sec, sec_fin, prices): " + ", ".join(missing))
    layoffs = pd.read_csv(need["layoffs"], parse_dates=["date"])
    matches = pd.read_csv(need["matches"])
    prices = pd.read_csv(need["prices"], parse_dates=["date"])
    events = build_events(layoffs, matches)
    log.info("Events: %d tracker events at companies with a ticker (after dropping follow-ups within 30 days)", len(events))
    raw_returns = daily_returns(prices)
    ex = extreme_daily_returns(raw_returns)
    ex["ret_pct"] = ex["ret_pct"].round(1)
    log.info("Largest single-day returns in the raw price data (beyond +-100 %% is treated as a data glitch):\n%s", ex.to_string(index=False))
    returns, masked = clean_returns(raw_returns)
    log.info("Blanked %d daily returns beyond +-100 %% in %d tickers:\n%s", int(masked["n_masked"].sum()), len(masked),
             masked.head(15).round(0).to_string(index=False))
    cars, lost = run_event_study(events, returns)
    log.info("Usable events: %d | lost: %s | events whose announcement window contains a blanked day: %d", len(cars), lost,
             int(cars["car_ann_0_1"].isna().sum()))
    if cars.empty:
        raise SystemExit("No usable events: check data/raw/prices_daily.csv")
    log.info("Average abnormal return (CAR) around the announcement, in %%:\n%s",
             summary_table(cars).round(3).to_string(index=False))
    cars["year"] = cars["date"].dt.year
    log.info("By year (announcement window 0..+1):\n%s", group_summary(cars, "year").round(3).to_string(index=False))
    sized = add_size_groups(attach_size(cars, pd.read_csv(need["fin"])).dropna(subset=["log_assets"]))
    log.info("By company size (announcement window 0..+1; size = total assets before the event):\n%s",
             group_summary(sized, "size_group").round(3).to_string(index=False))
    lm = largest_moves(cars)
    lm[["car_pct", "beta", "resid_sd"]] = lm[["car_pct", "beta", "resid_sd"]].round(2)
    log.info("Biggest single moves around real events (check for data errors, splits, takeovers):\n%s", lm.to_string(index=False))
    log.info("Robustness, announcement window 0..+1:")
    log.info("  winsorised at 1 %%/99 %%:\n%s", summary_table(winsorize_cars(cars)).set_index("window").loc[[MAIN]].round(3).to_string())
    cars_sp, _ = run_event_study(events, returns, bench="^GSPC") if "^GSPC" in returns else (None, None)
    if cars_sp is not None and len(cars_sp):
        log.info("  S&P 500 instead of NASDAQ as the market:\n%s", pd.DataFrame([summarize(cars_sp)]).round(3).to_string(index=False))
    log.info("  without 2020 (pandemic volatility):\n%s", pd.DataFrame([summarize(cars[cars["year"] > 2020])]).round(3).to_string(index=False))
    g = sized["size_group"].astype(str)
    sized = sized.assign(size_group=g)
    diff = group_difference(sized, "size_group", "najmanjša tretjina", "največja tretjina")
    log.info("  smallest minus largest size third: %.2f %% (95 %% interval %.2f to %.2f)", diff["diff_pct"], diff["ci_lo_pct"], diff["ci_hi_pct"])
    paths = ar_paths(cars[["event_id", "ticker", "date"]], returns)
    log.info("Average cumulative abnormal return by day (winsorised, from day -5):\n%s", path_summary(paths).round(3).to_string(index=False))
    pl = placebo_test(cars[["event_id", "ticker", "date"]], returns, n_rep=300)
    log.info("Placebo (300 repetitions on random non-event dates, same companies): mean of means %.3f %%, sd of means %.3f %%, sd of medians %.3f %%",
             pl["mean_of_means_pct"], pl["sd_of_means_pct"], pl["sd_of_medians_pct"])
    log.info("  false-positive rate, each should be about 5 %% (+-2.5 points with 300 repetitions): simple t %.0f %%, Patell Z %.0f %%, "
             "day-clustered bootstrap interval (our main test) %.0f %%", 100 * pl["false_positive_rate"], 100 * pl["patell_false_positive_rate"],
             100 * pl["bootstrap_false_positive_rate"])
    out = PROCESSED / "event_study_events.csv"
    cars.to_csv(out, index=False)
    log.info("Per-event results -> %s (derived from Yahoo prices: keep local, do not commit)", out)


if __name__ == "__main__":
    main()
