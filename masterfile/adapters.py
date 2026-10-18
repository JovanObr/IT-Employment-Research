"""One adapter per source: raw/processed file -> rows in the master schema.

Every adapter returns a DataFrame with schema.COLUMNS (or an empty one if its file is
missing). Values are kept 'as reported'; no indexing, scaling beyond unit conversion,
or gap filling happens here.
"""
from __future__ import annotations

import calendar
import logging

import pandas as pd

from collectors.common import PROCESSED, RAW
from . import schema as S

log = logging.getLogger("covid_it_data")

ICT_DATASETS = ["isoc_sks_itspt", "isoc_sks_itsps", "isoc_sks_itspa", "isoc_sks_itspe"]
EU_META = {"value", "flag", "geo", "geo_label", "time", "unit", "freq", "nace_r2", "nace_r2_label"}
TOTAL_CODES = {"T", "TOTAL", "Y15-74"}  # 'everyone' categories: no breakdown label needed
UNIT_MAP = {
    "THS_PER": ("employment_level", "thousand persons"),
    "PC_EMP": ("employment_share_pct", "% of total employment"),
}


def _missing(path) -> bool:
    if not path.exists():
        log.warning("master: %s not found - skipped", path)
        return True
    return False


def _long(df: pd.DataFrame, metrics: dict[str, tuple[pd.Series, str]]) -> pd.DataFrame:
    """Stack several metric Series (same index as df) into long format."""
    parts = []
    for name, (values, unit) in metrics.items():
        p = df.copy()
        p["metric"], p["value"], p["unit"] = name, pd.to_numeric(values, errors="coerce"), unit
        parts.append(p)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------- Eurostat
def eurostat(seg_map, unmapped) -> pd.DataFrame:
    frames = []
    for code in ICT_DATASETS + ["lfsa_egan22d"]:
        path = RAW / f"eurostat_{code}.csv"
        if _missing(path):
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        dims = [c for c in df.columns if c not in EU_META and not c.endswith("_label")]
        parts = [[("" if (v in TOTAL_CODES or v == "") else f"{d}={v}") for v in df[d]] for d in dims]
        df["breakdown"] = [";".join(p for p in row if p) for row in zip(*parts)] if dims else ""

        geo = df["geo"].replace(S.ISO_FIX)
        df["country"] = geo
        df["area_level"] = geo.map(lambda g: "country" if len(g) == 2 else "aggregate")
        df["region"] = "Europe"
        df["date"] = df["time"].str[:4] + "-01-01"
        df["frequency"] = "A"
        df["dataset"] = f"eurostat_{code}"
        df["source"] = "Eurostat"
        df["quality_flag"] = df["flag"]

        if code == "lfsa_egan22d":
            df["industry_code"] = df["nace_r2"]
            df = S.apply_segments(df, seg_map, "EUROSTAT_NACE", "industry_code", unmapped)
        else:
            df["industry_code"] = ""
            df["_k"] = "*"
            df = S.apply_segments(df, seg_map, "EUROSTAT_ICT", "_k", unmapped)
        df["notes"] = S.join_notes(df.index, df["_map_notes"],
                                   "Eurostat flags: b = break in series, e = estimated, u = low reliability, d = definition differs" if (df["flag"] != "").any() else "")

        mm = df["unit"].map(lambda u: UNIT_MAP.get(u, (f"other_{u.lower()}", u)))
        df["metric"], df["unit"] = [m[0] for m in mm], [m[1] for m in mm]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        frames.append(S.finish(df))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=S.COLUMNS)


# --------------------------------------------------------------------------- BLS CES
def bls_ces(seg_map, unmapped) -> pd.DataFrame:
    path = RAW / "bls_ces_employment.csv"
    if _missing(path):
        return pd.DataFrame(columns=S.COLUMNS)
    df = pd.read_csv(path, dtype={"series_id": str})
    df["industry_code"] = df["series_id"]
    df = S.apply_segments(df, seg_map, "CES", "industry_code", unmapped)
    df = df.assign(frequency="M", region="US", country="US", area_level="country",
                   metric="employment_level", unit="thousand persons", breakdown="",
                   source="US BLS", dataset="bls_ces", quality_flag="",
                   value=pd.to_numeric(df["employees_thousands"], errors="coerce"))
    df["notes"] = S.join_notes(df.index, df["_map_notes"], "not seasonally adjusted")
    return S.finish(df)


# --------------------------------------------------------------------------- BLS QCEW
def bls_qcew(seg_map, unmapped) -> pd.DataFrame:
    path = RAW / "bls_qcew_it_industries.csv"
    if _missing(path):
        return pd.DataFrame(columns=S.COLUMNS)
    df = pd.read_csv(path, dtype={"industry_code": str})
    month = (df["qtr"].astype(int) - 1) * 3 + 1
    df["date"] = pd.to_datetime({"year": df["year"], "month": month, "day": 1}).dt.strftime("%Y-%m-%d")
    df = S.apply_segments(df, seg_map, "QCEW", "industry_code", unmapped)
    df = df.assign(frequency="Q", region="US", country="US", area_level="country", breakdown="",
                   source="US BLS", dataset="bls_qcew")
    brk = (df["industry_code"] == "513210") & (df["date"] == "2022-01-01")
    df["quality_flag"] = brk.map({True: "series_break", False: ""})
    df["notes"] = S.join_notes(df.index, df["_map_notes"], "employment = mean of the 3 months in the quarter")
    emp = df[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].mean(axis=1) / 1000
    out = _long(df, {
        "employment_level": (emp, "thousand persons"),
        "establishments": (df["qtrly_estabs"], "count"),
        "avg_weekly_wage": (df["avg_wkly_wage"], "USD"),
    })
    return S.finish(out)


# --------------------------------------------------------------------------- ONS BRES (UK)
def ons_bres(seg_map, unmapped) -> pd.DataFrame:
    path = RAW / "nomis_bres_it_industries.csv"
    if _missing(path):
        return pd.DataFrame(columns=S.COLUMNS)
    df = pd.read_csv(path, dtype={"sic_code": str}, keep_default_na=False)
    df["industry_code"] = df["sic_code"].replace("", "TOTAL")
    df = S.apply_segments(df, seg_map, "BRES_SIC", "industry_code", unmapped)
    # 'Employment' (employees + working owners) is the 'everyone' concept -> blank breakdown,
    # comparable to Eurostat. Other statuses stay as labelled breakdowns.
    df["breakdown"] = df["employment_status"].map(
        lambda s: "" if s == "Employment" else f"employment_status={s}")
    df = df.assign(date=df["year"].astype(str) + "-01-01", frequency="A", region="Europe",
                   country="GB", area_level="country", source="ONS (via Nomis)",
                   dataset="ons_bres", quality_flag="",
                   metric="employment_level", unit="thousand persons",
                   value=pd.to_numeric(df["jobs"], errors="coerce") / 1000)
    df["notes"] = S.join_notes(df.index, df["_map_notes"], "Great Britain only (excl. N. Ireland)")
    return S.finish(df)


# --------------------------------------------------------------------------- Indeed
def _month_stats(df: pd.DataFrame, keys: list[str], col: str) -> pd.DataFrame:
    d = pd.to_datetime(df["date"])
    df = df.assign(_m=d.dt.to_period("M"), _dim=d.dt.days_in_month)
    g = df.groupby(keys + ["_m"], as_index=False).agg(value=(col, "mean"), _n=(col, "count"), _dim=("_dim", "first"))
    g["date"] = g["_m"].dt.start_time.dt.strftime("%Y-%m-%d")
    g["quality_flag"] = (g["_n"] < g["_dim"] - 3).map({True: "partial_month", False: ""})
    return g.drop(columns=["_m", "_n", "_dim"]).dropna(subset=["value"])


def indeed(seg_map, unmapped, include_other=False) -> pd.DataFrame:
    frames = []
    agg, sec = RAW / "indeed_aggregate_postings.csv", RAW / "indeed_it_sector_postings.csv"
    if not _missing(agg):
        df = pd.read_csv(agg)
        long = df.melt(id_vars=["date", "jobcountry", "variable"],
                       value_vars=["indeed_job_postings_index_SA", "indeed_job_postings_index_NSA"],
                       var_name="_adj", value_name="v")
        long["_adj"] = long["_adj"].str.replace("indeed_job_postings_index_", "", regex=False)
        long["breakdown"] = "variable=" + long["variable"] + ";seasonal=" + long["_adj"]
        m = _month_stats(long, ["jobcountry", "breakdown"], "v")
        m["industry_code"], m["dataset"] = "ALL", "indeed_aggregate"
        frames.append(m)
    if not _missing(sec):
        df = pd.read_csv(sec)
        df["breakdown"] = "variable=" + df["variable"]
        m = _month_stats(df, ["jobcountry", "display_name", "breakdown"], "indeed_job_postings_index")
        m["industry_code"], m["dataset"] = m["display_name"], "indeed_it_sector"
        frames.append(m.drop(columns="display_name"))
    if not frames:
        return pd.DataFrame(columns=S.COLUMNS)

    df = pd.concat(frames, ignore_index=True)
    df["country"] = df["jobcountry"].replace(S.ISO_FIX)
    df["region"] = df["country"].map(S.region_of)
    dropped = df[df["region"] == "Other"]
    if len(dropped) and not include_other:
        log.info("Indeed: dropped %d rows outside US/Europe (%s)", len(dropped),
                 ", ".join(sorted(dropped["country"].unique())))
        df = df[df["region"] != "Other"]
    df = S.apply_segments(df, seg_map, "INDEED", "industry_code", unmapped)
    df = df.assign(frequency="M", area_level="country", metric="job_postings_index",
                   unit="index (1 Feb 2020 = 100)", source="Indeed Hiring Lab")
    df["notes"] = S.join_notes(df.index, df["_map_notes"], "monthly mean of daily values")
    return S.finish(df)


# --------------------------------------------------------------------------- Layoffs
def layoffs(seg_map, unmapped, include_other=False) -> pd.DataFrame:
    path = PROCESSED / "layoffs_clean.csv"
    if _missing(path):
        return pd.DataFrame(columns=S.COLUMNS)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["country_iso"] = df["country"].map(S.COUNTRY_ISO)
    bad = df.loc[df["country_iso"].isna(), "country"].dropna().unique()
    if len(bad):
        log.warning("Layoffs: countries missing from COUNTRY_ISO (kept by name): %s", list(bad))
    df["country_iso"] = df["country_iso"].fillna(df["country"].fillna("unknown"))
    df["region"] = [S.region_of(c) if c in S.COUNTRY_ISO.values() else r
                    for c, r in zip(df["country_iso"], df["region"])]
    if not include_other:
        n = int((df["region"] == "Other").sum())
        if n:
            log.info("Layoffs: dropped %d events outside US/Europe", n)
        df = df[df["region"] != "Other"]
    df["industry"] = df["industry"].fillna("Unknown")
    df["month"] = df["date"].dt.to_period("M").dt.start_time.dt.strftime("%Y-%m-%d")

    def agg(keys, label_group, label_seg):
        g = df.groupby(keys, as_index=False).agg(
            layoff_events=("date", "size"),
            layoff_headcount=("total_laid_off", lambda s: s.sum(min_count=1)),
            layoff_events_missing_headcount=("total_laid_off", lambda s: int(s.isna().sum())))
        if "industry" not in g:
            g["industry"] = "All tracker industries"
        g["segment_group"], g["segment"] = label_group, label_seg(g)
        return g

    g = pd.concat([
        agg(["region", "country_iso", "month", "industry"], "Layoffs tracker industries", lambda g: g["industry"]),
        agg(["region", "country_iso", "month"], "All industries", lambda g: g["industry"]),
    ], ignore_index=True)
    g = g.assign(date=g["month"], frequency="M", country=g["country_iso"], area_level="country",
                 industry_code=g["industry"], granularity="detailed", breakdown="",
                 source="Layoffs.fyi (manually downloaded CSV)", dataset="layoffs_tracker", quality_flag="",
                 notes="crowdsourced; only companies with reported layoffs; headcount often missing")
    g.loc[g["segment_group"] == "All industries", "granularity"] = "total"
    out = _long(g, {
        "layoff_events": (g["layoff_events"], "events"),
        "layoff_headcount": (g["layoff_headcount"], "persons"),
        "layoff_events_missing_headcount": (g["layoff_events_missing_headcount"], "events"),
    })
    return S.finish(out)


# --------------------------------------------------------------------------- Hacker News
def hacker_news() -> pd.DataFrame:
    """Monthly shares (% of posts) for each flag/skill, plus post counts, from the post-level file."""
    from collectors.hn import FLAGS, SKILLS
    path = RAW / "hn_whoishiring_posts.csv"
    if _missing(path):
        return pd.DataFrame(columns=S.COLUMNS)
    df = pd.read_csv(path)
    cols = [c for c in list(FLAGS) + list(SKILLS) if c in df.columns]
    g = df.groupby("thread_month")
    shares = g[cols].mean().mul(100).reset_index().melt(
        id_vars="thread_month", var_name="segment", value_name="value")
    shares["metric"], shares["unit"] = "hn_post_share", "% of posts"
    shares["segment_group"] = shares["segment"].map(lambda c: "HN post attributes" if c in FLAGS else "HN skills mentioned")
    shares["granularity"] = "detailed"
    posts = g.size().rename("value").reset_index()
    posts["segment"], posts["segment_group"], posts["granularity"] = "All posts", "Hacker News job posts", "total"
    posts["metric"], posts["unit"] = "hn_posts", "count"
    out = pd.concat([shares, posts], ignore_index=True)
    this_month = pd.Timestamp.today().strftime("%Y-%m-01")
    out = out.assign(date=out["thread_month"], frequency="M", region="Global", country="ALL",
                     area_level="global", industry_code=out["segment"], breakdown="",
                     source="Hacker News (Algolia API)", dataset="hn_whoishiring",
                     quality_flag=(out["thread_month"] == this_month).map({True: "partial_month", False: ""}),
                     notes="startup-skewed; keyword rules (no negation handling)")
    return S.finish(out.drop(columns="thread_month"))
