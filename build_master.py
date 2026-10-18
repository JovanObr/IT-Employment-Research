#!/usr/bin/env python3
"""Merge every collected file into ONE tidy master CSV (long format, 'as reported').

    python build_master.py                 # US + Europe only
    python build_master.py --include-other # also keep Indeed CA/AU and layoffs outside US/Europe

Writes data/processed/it_employment_master.csv and data/processed/master_validation.txt.
Exit code 1 if a hard check fails (duplicates, mixed units, bad schema).
"""
from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from collectors.common import PROCESSED, RAW, ensure_dirs
from masterfile import adapters, schema as S

log = logging.getLogger("covid_it_data")


def build(include_other: bool) -> tuple[pd.DataFrame, set]:
    seg_map, unmapped = S.load_segment_map(), set()
    parts = {
        "eurostat": adapters.eurostat(seg_map, unmapped),
        "bls_ces": adapters.bls_ces(seg_map, unmapped),
        "bls_qcew": adapters.bls_qcew(seg_map, unmapped),
        "ons_bres": adapters.ons_bres(seg_map, unmapped),
        "indeed": adapters.indeed(seg_map, unmapped, include_other),
        "layoffs": adapters.layoffs(seg_map, unmapped, include_other),
        "hacker_news": adapters.hacker_news(),
    }
    for name, df in parts.items():
        log.info("%-9s %7d rows", name, len(df))
    master = pd.concat([d for d in parts.values() if len(d)], ignore_index=True)
    master = master.sort_values(["dataset", "series_id", "date"]).reset_index(drop=True)
    return master, unmapped


def _spot_checks(master: pd.DataFrame) -> list[tuple[bool, str]]:
    """Recompute a few values straight from the raw files and compare."""
    out = []

    def check(label, got, want):
        ok = got is not None and abs(float(got) - float(want)) < 1e-6
        out.append((ok, f"{label}: master={got} raw={want}"))

    p = RAW / "bls_ces_employment.csv"
    if p.exists():
        raw = pd.read_csv(p, dtype={"series_id": str}).iloc[100]
        m = master[(master.dataset == "bls_ces") & (master.industry_code == raw.series_id) & (master.date == raw.date)]
        check(f"CES {raw.series_id} {raw.date}", m.value.iloc[0] if len(m) else None, raw.employees_thousands)
    p = RAW / "nomis_bres_it_industries.csv"
    if p.exists():
        raw = pd.read_csv(p, dtype={"sic_code": str})
        r = raw[(raw.sic_code == "62011") & (raw.year == 2019) & (raw.employment_status == "Employment")]
        m = master[(master.dataset == "ons_bres") & (master.industry_code == "62011")
                   & (master.date == "2019-01-01") & (master.breakdown == "")]
        if len(r):
            check("BRES 62011 2019 Employment (thousands)", m.value.iloc[0] if len(m) else None, r.jobs.iloc[0] / 1000)
    p = RAW / "bls_qcew_it_industries.csv"
    if p.exists():
        raw = pd.read_csv(p, dtype={"industry_code": str}).iloc[len(pd.read_csv(p)) // 2]
        month = (int(raw.qtr) - 1) * 3 + 1
        d = f"{int(raw.year)}-{month:02d}-01"
        m = master[(master.dataset == "bls_qcew") & (master.industry_code == raw.industry_code)
                   & (master.date == d) & (master.metric == "establishments")]
        check(f"QCEW {raw.industry_code} {d} establishments", m.value.iloc[0] if len(m) else None, raw.qtrly_estabs)
    return out


def validate(master: pd.DataFrame, unmapped: set) -> tuple[list[str], int]:
    L, fails = [], 0

    def hard(ok: bool, msg: str):
        nonlocal fails
        L.append(("PASS  " if ok else "FAIL  ") + msg)
        fails += 0 if ok else 1

    hard(list(master.columns) == S.COLUMNS, "schema columns and order")
    hard(not master["date"].isin(["", "NaT"]).any(), "every row has a date")
    hard(master["metric"].ne("").all(), "every row has a metric")
    dups = master.duplicated(["series_id", "date"]).sum()
    hard(dups == 0, f"no duplicate (series_id, date) keys [{dups} duplicates]")
    units = master.groupby("metric")["unit"].nunique()
    hard((units == 1).all(), "one unit per metric" + ("" if (units == 1).all() else f" - mixed: {units[units > 1].to_dict()}"))
    for ok, msg in _spot_checks(master):
        hard(ok, "spot check " + msg)

    L.append("")
    L.append("Rows / date range / countries per dataset:")
    for ds, g in master.groupby("dataset"):
        L.append(f"  {ds:34s} {len(g):7d} rows  {g.date.min()} -> {g.date.max()}  "
                 f"{g.country.nunique():3d} areas  {g.series_id.nunique():5d} series")
    L.append("")
    nulls = master["value"].isna().groupby(master["dataset"]).sum()
    L.append("Missing values per dataset: " + (", ".join(f"{k}={v}" for k, v in nulls.items() if v) or "none"))
    flags = master[master.quality_flag != ""].groupby(["dataset", "quality_flag"]).size()
    L.append("Quality flags: " + (", ".join(f"{a}/{b}={n}" for (a, b), n in flags.items()) or "none"))
    L.append("")
    if unmapped:
        L.append("UNMAPPED CODES (add them to config/segment_map.csv, then rebuild):")
        L += [f"  {s}: {c}" for s, c in sorted(unmapped)]
    else:
        L.append("All codes are covered by config/segment_map.csv.")
    L.append("")
    L.append("Reminder: to sum within a segment_group, filter ONE dataset and granularity == 'detailed' "
             "(aggregate rows overlap their parts), and exclude area_level == 'aggregate'.")
    return L, fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-other", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    ensure_dirs()
    master, unmapped = build(a.include_other)
    out = PROCESSED / "it_employment_master.csv"
    master.to_csv(out, index=False)
    lines, fails = validate(master, unmapped)
    report = PROCESSED / "master_validation.txt"
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\nMaster file: {out}  ({len(master):,} rows)\nValidation report: {report}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
