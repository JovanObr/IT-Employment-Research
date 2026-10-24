"""A3, part 1: the company-quarter panel for the layoff-risk model.

One row per (cik, quarter) for technology companies (SIC list from `sec_universe`). Every feature on a row
comes from the filing quarter `t - LAG` (default 1), so nothing from quarter t or later is used: reports for a
quarter arrive 1-2 months after it ends, so by the END of quarter t the report for t-1 is public, the one for t
is not. The label looks forward only:

    y_next2q = 1 if the company has at least one tracker layoff in quarter t+1 or t+2   (one positive per window)

Rows are kept only where the whole label window lies inside the tracker's observed period, because the tracker
says nothing about quarters before it started or after its last full quarter (silence there is not "no layoff").

Run:  python -m analysis.company_panel      (needs the sec, sec_fin, sec_universe and layoffs steps first)
"""
from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from collectors.common import PROCESSED, RAW

log = logging.getLogger("covid_it_data")

LAG = 1                       # quarters between the filing quarter and the row quarter
HORIZON = 2                   # label window: quarters t+1 .. t+HORIZON
SPLIT_LAST_TRAIN = "2022Q4"   # time split used by the models
FEATURES = ["rev_yoy", "rev_qoq", "gross_margin", "op_margin", "rnd_ratio", "sga_ratio", "cash_assets",
            "log_assets", "net_loss"]
FLOWS = ["net_income", "operating_income", "gross_profit", "rnd", "sga"]
INSTANTS = ["cash", "assets", "equity"]


# ---------------------------------------------------------------------------------------- quarter helpers
def qindex(period: str) -> int:
    """'CY2022Q3' or 'CY2022Q3I' -> 2022*4 + 2 (consecutive quarters differ by exactly 1)."""
    m = re.fullmatch(r"CY(\d{4})Q([1-4])I?", str(period))
    if not m:
        raise ValueError(f"not a quarterly period: {period!r}")
    return int(m.group(1)) * 4 + int(m.group(2)) - 1


def qlabel(qi: int) -> str:
    return f"{qi // 4}Q{qi % 4 + 1}"


def qindex_of_date(d: pd.Series) -> pd.Series:
    return d.dt.year * 4 + (d.dt.quarter - 1)


# ---------------------------------------------------------------------------------------- financials
def quarterly_table(fin: pd.DataFrame, revenue: pd.DataFrame) -> pd.DataFrame:
    """Wide table (one row per cik and filing quarter): revenue, flows, balance-sheet items. Annual rows are dropped."""
    f = fin[fin["kind"].isin(["quarter", "derived_q4", "instant"]) & fin["concept"].isin(FLOWS + INSTANTS)].copy()
    f["qi"] = f["period"].map(qindex)
    wide = f.pivot_table(index=["cik", "qi"], columns="concept", values="value", aggfunc="first")
    r = revenue[revenue["kind"].isin(["quarter", "derived_q4"])].copy()
    r["qi"] = r["period"].map(qindex)
    rev = r.drop_duplicates(["cik", "qi"]).set_index(["cik", "qi"])["revenue"]
    wide = wide.join(rev, how="outer")
    for c in FLOWS + INSTANTS:
        if c not in wide:
            wide[c] = np.nan
    return wide.reset_index()


def _ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den, undefined (NaN) when the denominator is missing or not positive."""
    return (num / den.where(den > 0)).replace([np.inf, -np.inf], np.nan)


def add_features(q: pd.DataFrame) -> pd.DataFrame:
    """Features of each FILING quarter (not yet lagged). Growth uses the quarter 1 or 4 steps back by quarter
    index, so a missing quarter gives NaN instead of silently comparing across a gap."""
    q = q.copy()
    for k, name in ((4, "rev_lag4"), (1, "rev_lag1")):
        prev = q[["cik", "qi", "revenue"]].assign(qi=lambda d, k=k: d["qi"] + k).rename(columns={"revenue": name})
        q = q.merge(prev, on=["cik", "qi"], how="left")
    q["rev_yoy"] = _ratio(q["revenue"], q["rev_lag4"]) - 1
    q["rev_qoq"] = _ratio(q["revenue"], q["rev_lag1"]) - 1
    q["gross_margin"] = _ratio(q["gross_profit"], q["revenue"])
    q["op_margin"] = _ratio(q["operating_income"], q["revenue"])
    q["rnd_ratio"] = _ratio(q["rnd"], q["revenue"])
    q["sga_ratio"] = _ratio(q["sga"], q["revenue"])
    q["cash_assets"] = _ratio(q["cash"], q["assets"])
    q["log_assets"] = np.log(q["assets"].where(q["assets"] > 0))
    q["net_loss"] = (q["net_income"] < 0).astype(float).where(q["net_income"].notna())
    return q.drop(columns=["rev_lag4", "rev_lag1"])


def lag_features(q: pd.DataFrame, lag: int = LAG) -> pd.DataFrame:
    """Row quarter t gets the features of filing quarter t-lag. Keep only rows where that filing quarter has revenue."""
    cols = ["cik", "qi", "revenue"] + FEATURES
    out = q.loc[q["revenue"].notna(), cols].copy()
    out["qi"] = out["qi"] + lag
    return out.rename(columns={"revenue": "revenue_lagged"})


# ---------------------------------------------------------------------------------------- labels
def tracker_window(events_all: pd.DataFrame) -> tuple[int, int]:
    """Quarters in which the tracker can be trusted to be complete: after the first and before the last
    quarter that contains any event (those two are only partly observed)."""
    qi = qindex_of_date(events_all["date"].dropna())
    return int(qi.min()) + 1, int(qi.max()) - 1


def add_labels(panel: pd.DataFrame, events: pd.DataFrame, first_full: int, last_full: int,
               horizon: int = HORIZON) -> pd.DataFrame:
    """y_next2q from events of the same company in t+1..t+horizon; drop rows whose window is not fully observed."""
    ev = events.dropna(subset=["cik", "date"]).copy()
    ev["eqi"] = qindex_of_date(ev["date"])
    ev_q = set(zip(ev["cik"].astype(int), ev["eqi"].astype(int)))
    p = panel.copy()
    p["y_next2q"] = [int(any((c, t + h) in ev_q for h in range(1, horizon + 1)))
                     for c, t in zip(p["cik"], p["qi"])]
    ok = (p["qi"] + 1 >= first_full) & (p["qi"] + horizon <= last_full)
    log.info("Panel: %d rows dropped because the label window leaves the tracker's observed period", int((~ok).sum()))
    return p[ok].reset_index(drop=True)


# ---------------------------------------------------------------------------------------- assemble
def build_panel(fin, revenue, universe, matches, events_all, lag: int = LAG) -> pd.DataFrame:
    tech = universe[universe["is_tech"]].copy()
    tech["sic"] = tech["sic"].astype(str).str.zfill(4)
    tech["sic2"] = tech["sic"].str[:2]
    feats = lag_features(add_features(quarterly_table(fin[fin["cik"].isin(tech["cik"])],
                                                      revenue[revenue["cik"].isin(tech["cik"])])), lag)
    panel = feats.merge(tech[["cik", "name", "ticker", "sic", "sic2"]], on="cik", how="inner")
    m = events_all.merge(matches[["layoffs_company", "cik"]], left_on="company", right_on="layoffs_company")
    first_full, last_full = tracker_window(events_all)
    panel = add_labels(panel, m[["cik", "date"]], first_full, last_full)
    panel["quarter"] = panel["qi"].map(qlabel)
    log.info("Tracker observed fully in %s .. %s", qlabel(first_full), qlabel(last_full))
    cols = ["cik", "quarter", "qi", "name", "ticker", "sic", "sic2", "revenue_lagged"] + FEATURES + ["y_next2q"]
    return panel[cols].sort_values(["cik", "qi"]).reset_index(drop=True)


def panel_report(panel: pd.DataFrame, n_universe: int | None = None) -> None:
    ever = panel.groupby("cik")["y_next2q"].max()
    log.info("Companies in the panel: %d | with at least one positive window: %d | NEVER positive (true negatives): %d%s",
             len(ever), int(ever.sum()), int((ever == 0).sum()),
             f" | tech universe: {n_universe}" if n_universe else "")
    log.info("Panel: %d rows, %d companies, %d positives (base rate %.2f%%)", len(panel), panel["cik"].nunique(),
             int(panel["y_next2q"].sum()), 100 * panel["y_next2q"].mean())
    train = panel["quarter"] <= SPLIT_LAST_TRAIN
    for name, part in (("train (<= %s)" % SPLIT_LAST_TRAIN, panel[train]), ("test (after)", panel[~train])):
        log.info("  %-14s %6d rows, %4d positives (%.2f%%), %d companies with a positive", name, len(part),
                 int(part["y_next2q"].sum()), 100 * part["y_next2q"].mean() if len(part) else float("nan"),
                 part.loc[part["y_next2q"] == 1, "cik"].nunique())
    by_year = panel.assign(year=panel["quarter"].str[:4]).groupby("year")["y_next2q"].agg(["size", "sum", "mean"])
    log.info("Rows, positives and base rate by year of the row quarter:\n%s", by_year.round(3).to_string())
    log.info("Share of missing values per feature:\n%s", panel[FEATURES].isna().mean().round(3).to_string())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    rev_file = RAW / "sec_revenue_universe.csv"       # tech comparison companies + matched layoff companies
    need = [RAW / "sec_financials_quarterly.csv", rev_file, RAW / "sec_universe_sic.csv",
            RAW / "sec_company_matches.csv", PROCESSED / "layoffs_clean.csv"]
    missing = [p for p in need if not p.exists()]
    if missing:
        raise SystemExit("Missing inputs (run collect.py for layoffs, sec, sec_universe, then sec_fin): "
                         + ", ".join(str(p) for p in missing))
    fin = pd.read_csv(need[0])
    revenue = pd.read_csv(need[1])
    universe = pd.read_csv(need[2], dtype={"sic": str})
    matches = pd.read_csv(need[3])
    events = pd.read_csv(need[4])
    events["date"] = pd.to_datetime(events["date"], errors="coerce")
    events = events[events["region"].isin(["US", "Europe"])].dropna(subset=["company"])
    panel = build_panel(fin, revenue, universe, matches, events)
    out = PROCESSED / "company_panel.csv"
    panel.to_csv(out, index=False)
    log.info("Company panel -> %s", out)
    panel_report(panel, int(universe["is_tech"].sum()))


if __name__ == "__main__":
    main()
