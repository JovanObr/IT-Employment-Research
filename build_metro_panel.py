#!/usr/bin/env python3
"""Metro panel for the geography track: one row per US metro area (MSA).

Joins   QCEW (IT services = NAICS 5415, and all-industry total)   [bls_qcew_areas_it_industries.csv]
        Census ACS, 5-year if available else 1-year (work from home, education, income, housing)   (optional)
        FHFA house prices (growth, pre-trend, metro names)   [fhfa_hpi_metro_quarterly.csv]
into data/processed/metro_panel.csv, and prints how many metros are usable at each step.

Conventions
  * QCEW suppression hits quarters erratically (even big metros), so we do NOT rely on one quarter:
    growth compares only the quarters that are reported in BOTH years (e.g. Q2 and Q4 of 2019 vs 2024),
    and a metro needs at least MIN_Q such quarters. Employment = mean of the 3 months in each quarter.
  * 2019 = pre-COVID baseline, 2024 = latest full year, 2015 -> 2019 = pre-trend (also quarter-matched).
  * ACS end year = the latest of 2024/2023/2022 collected; baseline = 2019.
  * FHFA metropolitan divisions (NYC, LA, SF, Seattle, ...) are mapped to their parent MSA through
    config/msad_parent.csv and averaged, unweighted: an approximation, see hpi_areas_averaged.
  * QCEW area code 'C1018' = CBSA 10180 (C + first four digits).
Run:  python build_metro_panel.py
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from collectors.common import PROCESSED, RAW, ensure_dirs

CONFIG = Path(__file__).resolve().parent / "config"
log = logging.getLogger("covid_it_data")
Y0, Y1, YPRE = 2019, 2024, 2015
IT, TOTAL = "5415", "10"
MIN_Q = 2  # minimum number of quarters reported in both years


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _paired(piv: pd.DataFrame, ya: int, yb: int, mask: pd.DataFrame | None = None):
    """Mean over the quarters present in both years. Returns (mean_a, mean_b, n_quarters, mask)."""
    A, B = piv[ya], piv[yb]
    A, B = A.align(B, join="inner", axis=1)
    if mask is None:
        mask = A.notna() & B.notna()
    return A.where(mask).mean(axis=1), B.where(mask).mean(axis=1), mask.sum(axis=1), mask


def load_qcew() -> pd.DataFrame:
    a = pd.read_csv(RAW / "bls_qcew_areas_it_industries.csv",
                    dtype={"area_fips": str, "industry_code": str}, keep_default_na=False, low_memory=False)
    a = a[a["area_fips"].str.fullmatch(r"C\d{4}") & a["year"].isin([YPRE, Y0, Y1])
          & a["industry_code"].isin([IT, TOTAL])].copy()
    m = a[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].apply(_num)
    supp = (a["disclosure_code"] == "N") if "disclosure_code" in a else pd.Series(False, index=a.index)
    supp = supp | (_num(a["month3_emplvl"]) == 0)
    a["emp"] = m.mean(axis=1).where(~supp)
    a["estabs"] = _num(a["qtrly_estabs"]).where(~supp)
    a["wage"] = _num(a["avg_wkly_wage"]).where(~supp)
    piv = {v: a.pivot_table(index=["area_fips", "industry_code"], columns=["year", "qtr"], values=v, aggfunc="first")
           for v in ("emp", "estabs", "wage")}
    it = {v: piv[v].xs(IT, level="industry_code") for v in piv}
    tot = piv["emp"].xs(TOTAL, level="industry_code")

    idx = it["emp"].index.union(tot.index)  # keep metros with NO IT rows, so coverage shares are honest
    it = {v: it[v].reindex(idx) for v in it}
    out = pd.DataFrame(index=idx)
    # main comparison: 2019 vs 2024 on quarters reported in both years
    e0, e1, n, mask = _paired(it["emp"], Y0, Y1)
    out["emp_it_2019"], out["emp_it_2024"], out["n_quarters"] = e0, e1, n
    out["estabs_it_2019"] = _paired(it["estabs"], Y0, Y1, mask)[0]
    out["wage_it_2019"], out["wage_it_2024"] = _paired(it["wage"], Y0, Y1, mask)[:2]
    t0, t1, _, _ = _paired(tot.reindex(out.index), Y0, Y1, mask)
    out["emp_total_2019"], out["emp_total_2024"] = t0, t1
    # pre-trend: 2015 vs 2019 on their own matched quarters
    p15, p19, npre, _ = _paired(it["emp"], YPRE, Y0)
    out["it_growth_pre_pct"] = (p19 / p15 - 1) * 100
    out["n_quarters_pre"] = npre

    # total private employment is never suppressed: keep an all-quarter version that does NOT depend on
    # IT being usable, so coverage and "biggest metros" are measured on ALL metros
    out["emp_total_all_2019"] = tot.reindex(idx)[Y0].mean(axis=1)
    thin = out["n_quarters"] < MIN_Q
    out.loc[thin, [c for c in out.columns if c.startswith(("emp_it_", "emp_total_2", "estabs_", "wage_"))]] = np.nan
    out.loc[out["n_quarters_pre"] < MIN_Q, "it_growth_pre_pct"] = np.nan
    # the old rule (Q1 only), kept for comparison
    q1 = it["emp"]
    out["usable_q1_only"] = q1[(Y0, 1)].notna() & q1[(Y1, 1)].notna()
    out = out.reset_index()
    out["cbsa_code"] = out["area_fips"].str[1:] + "0"
    return out


def national_it_share() -> float:
    n = pd.read_csv(RAW / "bls_qcew_it_industries.csv", dtype={"industry_code": str})
    n = n[(n["year"] == Y0) & n["industry_code"].isin([IT, TOTAL])]
    emp = n.groupby("industry_code")[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].mean().mean(axis=1)
    return float(emp[IT] / emp[TOTAL] * 100)


def acs_path() -> Path | None:
    """Prefer the 5-year product (covers small metros); fall back to 1-year."""
    for f in ("census_acs5_metro.csv", "census_acs1_metro.csv"):
        if (RAW / f).exists():
            return RAW / f
    return None


def load_acs() -> pd.DataFrame:
    path = acs_path()
    log.info("Census file used: %s", path.name)
    d = pd.read_csv(path, dtype={"cbsa_code": str})
    d["cbsa_code"] = d["cbsa_code"].str.zfill(5)
    end = max([y for y in (2024, 2023, 2022) if y in set(d["year"])], default=None)
    if end is None or Y0 not in set(d["year"]):
        raise RuntimeError("ACS needs 2019 and one of 2022-2024; re-run collect.py --sources acs")
    keep = ["wfh_share_pct", "bachelors_plus_pct", "population", "median_hh_income", "median_gross_rent",
            "median_home_value", "median_age", "broadband_pct"]
    keep = [c for c in keep if c in d.columns]
    base = d[d["year"] == Y0].set_index("cbsa_code")[["name"] + keep].add_suffix("_acs2019").rename(columns={"name_acs2019": "name"})
    last = d[d["year"] == end].set_index("cbsa_code")[keep].add_suffix("_acs_end")
    out = base.join(last, how="left").reset_index()
    out["acs_end_year"] = end
    return out


def load_fhfa() -> pd.DataFrame:
    h = pd.read_csv(RAW / "fhfa_hpi_metro_quarterly.csv", dtype={"cbsa_code": str})
    h = h[(h["quarter"] == 1) & h["year"].isin([YPRE, Y0, Y1])].copy()
    # Big MSAs are published as divisions with their own codes: map division NAME -> parent MSA code
    pm = pd.read_csv(CONFIG / "msad_parent.csv", dtype=str)
    clean = lambda s: s.str.split().str.join(" ")
    pcode = dict(zip(clean(pm["msad_name"]), pm["parent_cbsa"]))
    pname = dict(zip(pm["parent_cbsa"], pm["parent_name"]))
    names = clean(h["place_name"])
    h["cbsa_code"] = h["cbsa_code"].where(h["is_division"] == 0, names.map(pcode))
    bad = sorted(h.loc[h["cbsa_code"].isna(), "place_name"].unique())
    if bad:
        log.warning("FHFA divisions without a parent MSA (add them to config/msad_parent.csv): %s", bad)
    h = h.dropna(subset=["cbsa_code"])
    h["metro_name"] = np.where(h["is_division"] == 1, h["cbsa_code"].map(pname), h["place_name"])
    w = h.groupby(["cbsa_code", "year"])["hpi_nsa"].mean().unstack("year")  # divisions averaged, unweighted
    out = pd.DataFrame({"hpi_growth_pre_pct": (w[Y0] / w[YPRE] - 1) * 100,
                        "hpi_growth_pct": (w[Y1] / w[Y0] - 1) * 100,
                        "hpi_areas_averaged": h.groupby("cbsa_code")["place_name"].nunique(),
                        "hpi_name": h.groupby("cbsa_code")["metro_name"].first()})
    return out.reset_index()


def build() -> tuple[pd.DataFrame, list[str]]:
    q = load_qcew()
    nat = national_it_share()
    q["it_growth_pct"] = (q["emp_it_2024"] / q["emp_it_2019"] - 1) * 100
    q["it_share_2019_pct"] = q["emp_it_2019"] / q["emp_total_2019"] * 100
    q["it_location_quotient_2019"] = q["it_share_2019_pct"] / nat
    q["total_growth_pct"] = (q["emp_total_2024"] / q["emp_total_2019"] - 1) * 100
    q["it_avg_estab_size_2019"] = q["emp_it_2019"] / q["estabs_it_2019"]
    q["it_wage_growth_pct"] = (q["wage_it_2024"] / q["wage_it_2019"] - 1) * 100
    q["usable"] = q["emp_it_2019"].notna() & q["emp_it_2024"].notna()

    p = q.merge(load_fhfa(), on="cbsa_code", how="left")
    have_acs = acs_path() is not None
    if have_acs:
        p = p.merge(load_acs(), on="cbsa_code", how="left")
        p["wfh_change_pp"] = p["wfh_share_pct_acs_end"] - p["wfh_share_pct_acs2019"]
        p["population_growth_pct"] = (p["population_acs_end"] / p["population_acs2019"] - 1) * 100
        p["metro_name"] = p["name"].fillna(p["hpi_name"])
    else:
        log.warning("census_acs1_metro.csv not found: building the panel WITHOUT Census features "
                    "(run `python collect.py --sources acs`; it needs a free CENSUS_API_KEY).")
        p["metro_name"] = p["hpi_name"]

    feats = ["it_growth_pre_pct", "it_location_quotient_2019", "it_avg_estab_size_2019", "wfh_share_pct_acs2019",
             "wfh_change_pp", "bachelors_plus_pct_acs2019", "population_acs2019", "median_hh_income_acs2019",
             "median_gross_rent_acs2019", "median_age_acs2019", "hpi_growth_pre_pct", "hpi_growth_pct"]
    feats = [f for f in feats if f in p]
    p["complete_case"] = p["usable"] & p[feats].notna().all(axis=1)
    allm = p["emp_total_all_2019"]
    big = p.loc[allm.nlargest(25).index]
    unusable_big = big[~big["usable"]]
    lines = [
        f"MSAs in QCEW area file:                       {len(p)}",
        f"IT employment usable (old rule, Q1 only):     {int(p['usable_q1_only'].sum())}",
        f"IT employment usable (quarter-matched, >= {MIN_Q}):   {int(p['usable'].sum())}",
        f"  share of ALL private employment in usable metros: {allm[p['usable']].sum() / allm.sum() * 100:.0f}%",
        f"  of the 25 biggest metros (all employment), usable: {int(big['usable'].sum())}",
        (f"  ... and matched to Census ACS:             {int((p['usable'] & p['name'].notna()).sum())}"
         if have_acs else "  ... Census ACS:                            NOT AVAILABLE (see warning)"),
        f"  ... and matched to FHFA house prices:      {int((p['usable'] & p['hpi_growth_pct'].notna()).sum())}",
        f"COMPLETE CASES for the regression:           {int(p['complete_case'].sum())}  ({len(feats)} candidate predictors)",
        f"Rule of thumb: 10-15 metros per predictor -> about {int(p['complete_case'].sum() // 12)} predictors supportable.",
        "Features: " + ", ".join(feats),
    ]
    if len(unusable_big):
        lines.append("BIGGEST METROS THAT ARE UNUSABLE (no quarter reported in both years): "
                     + "; ".join(unusable_big["metro_name"].fillna(unusable_big["cbsa_code"]).astype(str)))
    return p, lines


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    ensure_dirs()
    panel, lines = build()
    out = PROCESSED / "metro_panel.csv"
    panel.drop(columns=["area_fips"]).to_csv(out, index=False)
    print("\n".join(lines) + f"\n\nMetro panel: {out}")


if __name__ == "__main__":
    main()
