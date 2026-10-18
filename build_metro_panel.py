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


def _matched(piv: pd.DataFrame, ya: int, yb: int):
    """Quarter-matched means: only quarters reported in BOTH years. Returns (mean_a, mean_b, n_quarters, mask)."""
    A, B = piv[ya].align(piv[yb], join="inner", axis=1)
    mask = A.notna() & B.notna()
    return A.where(mask).mean(axis=1), B.where(mask).mean(axis=1), mask.sum(axis=1), mask


def _growth_inputs(piv: pd.DataFrame, ya: int, yb: int):
    """Prefer quarter-matched means (>= MIN_Q common quarters). Otherwise fall back to the mean of whatever
    quarters exist in each year (>= 1 per year): a small seasonal mismatch, flagged in `basis`."""
    m0, m1, n, mask = _matched(piv, ya, yb)
    f0, f1 = piv[ya].mean(axis=1), piv[yb].mean(axis=1)
    matched = n >= MIN_Q
    fallback = ~matched & f0.notna() & f1.notna()
    v0 = m0.where(matched, f0.where(fallback))
    v1 = m1.where(matched, f1.where(fallback))
    basis = pd.Series(np.where(matched, "matched", np.where(fallback, "unmatched", "none")), index=piv.index)
    return v0, v1, n, basis, mask, matched


def load_qcew() -> pd.DataFrame:
    a = pd.read_csv(RAW / "bls_qcew_areas_it_industries.csv",
                    dtype={"area_fips": str, "industry_code": str}, keep_default_na=False, low_memory=False)
    a = a[a["area_fips"].str.fullmatch(r"C\d{4}") & a["year"].isin([YPRE, Y0, Y1])
          & a["industry_code"].isin([IT, TOTAL])].copy()
    m = a[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].apply(_num)
    supp = (a["disclosure_code"] == "N") if "disclosure_code" in a else pd.Series(False, index=a.index)
    supp = supp | (_num(a["month3_emplvl"]) == 0)
    a["emp"] = m.mean(axis=1).where(~supp)            # employment and wages ARE withheld when suppressed...
    a["wage"] = _num(a["avg_wkly_wage"]).where(~supp)
    a["estabs"] = _num(a["qtrly_estabs"])             # ...but the establishment count is still reported
    piv = {v: a.pivot_table(index=["area_fips", "industry_code"], columns=["year", "qtr"], values=v, aggfunc="first")
           for v in ("emp", "estabs", "wage")}
    idx = piv["emp"].xs(IT, level="industry_code").index.union(piv["emp"].xs(TOTAL, level="industry_code").index)
    it = {v: piv[v].xs(IT, level="industry_code").reindex(idx) for v in piv}
    tot = piv["emp"].xs(TOTAL, level="industry_code").reindex(idx)

    out = pd.DataFrame(index=idx)
    # --- IT employment outcome: 2019 vs 2024
    e0, e1, n, basis, mask, matched = _growth_inputs(it["emp"], Y0, Y1)
    out["emp_it_2019"], out["emp_it_2024"], out["n_quarters"], out["emp_basis"] = e0, e1, n, basis
    w0 = np.where(matched, _matched(it["wage"], Y0, Y1)[0], it["wage"][Y0].mean(axis=1))
    w1 = np.where(matched, _matched(it["wage"], Y0, Y1)[1], it["wage"][Y1].mean(axis=1))
    usable_emp = e0.notna() & e1.notna()
    out["wage_it_2019"] = pd.Series(w0, index=idx).where(usable_emp)
    out["wage_it_2024"] = pd.Series(w1, index=idx).where(usable_emp)
    # --- establishments (never suppressed) and total employment (never suppressed): all-quarter means
    out["estabs_it_2019"], out["estabs_it_2024"] = it["estabs"][Y0].mean(axis=1), it["estabs"][Y1].mean(axis=1)
    out["estabs_it_2015"] = it["estabs"][YPRE].mean(axis=1)
    out["emp_total_2019"], out["emp_total_2024"] = tot[Y0].mean(axis=1), tot[Y1].mean(axis=1)
    # --- pre-trend (2015 -> 2019)
    p15, p19, npre, _, _, _ = _growth_inputs(it["emp"], YPRE, Y0)
    out["it_growth_pre_pct"] = (p19 / p15 - 1) * 100
    # the old rule (Q1 only), kept for comparison
    out["usable_q1_only"] = it["emp"][(Y0, 1)].notna() & it["emp"][(Y1, 1)].notna()
    out = out.reset_index()
    out["cbsa_code"] = out["area_fips"].str[1:] + "0"
    return out


def national_it_share() -> float:
    n = pd.read_csv(RAW / "bls_qcew_it_industries.csv", dtype={"industry_code": str})
    n = n[(n["year"] == Y0) & n["industry_code"].isin([IT, TOTAL])]
    emp = n.groupby("industry_code")[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].mean().mean(axis=1)
    return float(emp[IT] / emp[TOTAL] * 100)


def national_estab_density() -> float:
    """IT establishments per 1,000 private workers, US, 2019 (all quarters)."""
    n = pd.read_csv(RAW / "bls_qcew_it_industries.csv", dtype={"industry_code": str})
    n = n[(n["year"] == Y0) & n["industry_code"].isin([IT, TOTAL])]
    est = n.groupby("industry_code")["qtrly_estabs"].mean()
    emp = n.groupby("industry_code")[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].mean().mean(axis=1)
    return float(est[IT] / (emp[TOTAL] / 1000))


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
    nat, nat_dens = national_it_share(), national_estab_density()
    # outcome A: IT employment (can be suppressed)
    q["it_growth_pct"] = (q["emp_it_2024"] / q["emp_it_2019"] - 1) * 100
    q["it_share_2019_pct"] = q["emp_it_2019"] / q["emp_total_2019"] * 100
    q["it_location_quotient_2019"] = q["it_share_2019_pct"] / nat
    q["total_growth_pct"] = (q["emp_total_2024"] / q["emp_total_2019"] - 1) * 100
    q["it_avg_estab_size_2019"] = q["emp_it_2019"] / q["estabs_it_2019"]
    q["it_wage_growth_pct"] = (q["wage_it_2024"] / q["wage_it_2019"] - 1) * 100
    q["usable"] = q["emp_it_2019"].notna() & q["emp_it_2024"].notna()
    # outcome B: IT establishments (never suppressed, so every metro with IT firms is included)
    q["estab_growth_pct"] = (q["estabs_it_2024"] / q["estabs_it_2019"] - 1) * 100
    q["estab_growth_pre_pct"] = (q["estabs_it_2019"] / q["estabs_it_2015"] - 1) * 100
    q["it_estabs_per_1000_workers_2019"] = q["estabs_it_2019"] / (q["emp_total_2019"] / 1000)
    q["it_estab_quotient_2019"] = q["it_estabs_per_1000_workers_2019"] / nat_dens
    q["usable_estab"] = q["estab_growth_pct"].notna() & q["it_estab_quotient_2019"].notna()

    p = q.merge(load_fhfa(), on="cbsa_code", how="left")
    have_acs = acs_path() is not None
    if have_acs:
        p = p.merge(load_acs(), on="cbsa_code", how="left")
        p["wfh_change_pp"] = p["wfh_share_pct_acs_end"] - p["wfh_share_pct_acs2019"]
        p["population_growth_pct"] = (p["population_acs_end"] / p["population_acs2019"] - 1) * 100
        p["metro_name"] = p["name"].fillna(p["hpi_name"])
    else:
        log.warning("No Census ACS file found: building the panel WITHOUT Census features "
                    "(run `python collect.py --sources acs5`; it needs a free CENSUS_API_KEY).")
        p["metro_name"] = p["hpi_name"]

    common = ["wfh_share_pct_acs2019", "wfh_change_pp", "bachelors_plus_pct_acs2019", "population_acs2019",
              "median_hh_income_acs2019", "median_gross_rent_acs2019", "median_age_acs2019",
              "hpi_growth_pre_pct", "hpi_growth_pct"]
    feats = [f for f in ["it_growth_pre_pct", "it_location_quotient_2019", "it_avg_estab_size_2019"] + common if f in p]
    feats_e = [f for f in ["estab_growth_pre_pct", "it_estab_quotient_2019"] + common if f in p]
    p["complete_case"] = p["usable"] & p[feats].notna().all(axis=1)
    p["complete_case_estab"] = p["usable_estab"] & p[feats_e].notna().all(axis=1)

    allm = p["emp_total_2019"]
    big = p.loc[allm.nlargest(25).index]
    lines = [
        f"MSAs in QCEW area file:                        {len(p)}",
        f"--- Outcome A: IT EMPLOYMENT growth 2019-2024 (employment is sometimes withheld) ---",
        f"  usable, quarter-matched:                     {int((p['emp_basis'] == 'matched').sum())}",
        f"  usable, quarters not matched (fallback):     {int((p['emp_basis'] == 'unmatched').sum())}",
        f"  usable in total:                             {int(p['usable'].sum())}   (old Q1-only rule: {int(p['usable_q1_only'].sum())})",
        f"  share of ALL private employment covered:     {allm[p['usable']].sum() / allm.sum() * 100:.0f}%",
        f"  of the 25 biggest metros, usable:            {int(big['usable'].sum())}",
        f"  COMPLETE CASES: {int(p['complete_case'].sum())}  ({len(feats)} candidate predictors; ~{int(p['complete_case'].sum() // 12)} supportable)",
        f"--- Outcome B: IT ESTABLISHMENT growth 2019-2024 (never withheld) ---",
        f"  usable:                                      {int(p['usable_estab'].sum())}",
        f"  share of ALL private employment covered:     {allm[p['usable_estab']].sum() / allm.sum() * 100:.0f}%",
        f"  of the 25 biggest metros, usable:            {int(big['usable_estab'].sum())}",
        f"  COMPLETE CASES: {int(p['complete_case_estab'].sum())}  ({len(feats_e)} candidate predictors; ~{int(p['complete_case_estab'].sum() // 12)} supportable)",
        "Census file: " + (acs_path().name if have_acs else "NOT AVAILABLE"),
    ]
    miss = big[~big["usable"]]
    if len(miss):
        lines.append("Biggest metros with NO usable IT employment: "
                     + "; ".join(miss["metro_name"].fillna(miss["cbsa_code"]).astype(str)))
    return p, lines


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    ensure_dirs()
    panel, lines = build()
    out = PROCESSED / "metro_panel.csv"
    try:
        panel.drop(columns=["area_fips"]).to_csv(out, index=False)
    except PermissionError:  # typically the old file is open in Excel
        out = out.with_name("metro_panel_new.csv")
        panel.drop(columns=["area_fips"]).to_csv(out, index=False)
        print("NOTE: metro_panel.csv is open in another program (Excel?), so the new panel was saved as", out.name)
    print("\n".join(lines) + f"\n\nMetro panel: {out}")


if __name__ == "__main__":
    main()
