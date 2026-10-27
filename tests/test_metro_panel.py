"""build_metro_panel.load_qcew with the REAL suppression patterns seen in the data (AGENTS.md section 9, item 9).

  * Chicago (C1698): 2019 IT employment reported in all four quarters (~65,000 jobs); 2024 withheld in all four
    quarters (disclosure_code N, value 0) while establishments stay reported (6,406 to 6,633).
  * Washington DC (C4790): reported only in 2019 Q3, Q4 and 2024 Q1 (no quarter in common).
"""
import numpy as np
import pandas as pd
import pytest

import build_metro_panel as bmp

COLS = ["area_fips", "year", "qtr", "industry_code", "disclosure_code", "qtrly_estabs",
        "month1_emplvl", "month2_emplvl", "month3_emplvl", "avg_wkly_wage"]


def row(area, year, qtr, industry, emp, estabs, withheld=False, wage=2000):
    e = 0 if withheld else emp
    return {"area_fips": area, "year": year, "qtr": qtr, "industry_code": industry,
            "disclosure_code": "N" if withheld else "", "qtrly_estabs": estabs,
            "month1_emplvl": e, "month2_emplvl": e, "month3_emplvl": e, "avg_wkly_wage": 0 if withheld else wage}


def build_rows():
    rows = []
    for y in (2015, 2019, 2024):                      # the builder needs the pre-trend year too
        for q in (1, 2, 3, 4):
            # a well-behaved metro: Denver (C1974), everything reported
            rows += [row("C1974", y, q, "5415", 1000 + 100 * (y - 2015), 500 + (y - 2015)),
                     row("C1974", y, q, "10", 100000, 90000)]
            # Chicago: 2019 reported, 2024 withheld in all 4 quarters, establishments always reported
            if y == 2024:
                rows.append(row("C1698", y, q, "5415", 0, 6400 + 60 * q, withheld=True))
            else:
                rows.append(row("C1698", y, q, "5415", 65000, 6000 + 10 * q))
            rows.append(row("C1698", y, q, "10", 4_000_000, 300000))
            # Washington DC: reported only 2019 Q3, Q4 and 2024 Q1
            ok = (y == 2019 and q in (3, 4)) or (y == 2024 and q == 1) or y == 2015
            rows.append(row("C4790", y, q, "5415", {2015: 90000, 2019: 100000, 2024: 110000}[y],
                            7000, withheld=not ok))
            rows.append(row("C4790", y, q, "10", 2_800_000, 200000))
    return pd.DataFrame(rows, columns=COLS)


@pytest.fixture
def q(data_dir):
    build_rows().to_csv(data_dir / "raw" / "bls_qcew_areas_it_industries.csv", index=False)
    return bmp.load_qcew().set_index("area_fips")


def test_chicago_has_no_employment_outcome(q):
    c = q.loc["C1698"]
    assert c["emp_basis"] == "none"
    assert pd.isna(c["emp_it_2024"])                       # withheld 2024 must not appear as 0 jobs
    assert pd.isna(c["emp_it_2019"])                       # no growth can be formed, so no 2019 level is kept either
    assert not (c["emp_it_2019"] == c["emp_it_2019"] and c["emp_it_2024"] == c["emp_it_2024"])


def test_chicago_establishment_outcome_is_complete(q):
    c = q.loc["C1698"]
    assert c["estabs_it_2019"] == pytest.approx(6025)      # mean of 6010..6040
    assert c["estabs_it_2024"] == pytest.approx(np.mean([6460, 6520, 6580, 6640]))
    assert 6406 <= c["estabs_it_2024"] <= 6633
    assert c["estabs_it_2015"] == pytest.approx(6025)
    assert c["emp_total_2019"] == 4_000_000                # total employment is never withheld


def test_dc_is_rescued_with_unmatched_basis(q):
    d = q.loc["C4790"]
    assert d["n_quarters"] == 0                            # no quarter reported in both years
    assert d["emp_basis"] == "unmatched"
    assert d["emp_it_2019"] == pytest.approx(100000)       # mean of Q3 and Q4 only
    assert d["emp_it_2024"] == pytest.approx(110000)       # Q1 only


def test_fully_reported_metro_is_quarter_matched(q):
    m = q.loc["C1974"]
    assert m["emp_basis"] == "matched" and m["n_quarters"] == 4
    assert m["emp_it_2019"] == pytest.approx(1400) and m["emp_it_2024"] == pytest.approx(1900)
    assert m["it_growth_pre_pct"] == pytest.approx((1400 / 1000 - 1) * 100)


def test_cbsa_code_is_a_five_character_string(q):
    assert q.loc["C1698", "cbsa_code"] == "16980"
    assert q.loc["C4790", "cbsa_code"] == "47900"
    assert all(len(c) == 5 for c in q["cbsa_code"])


def test_withheld_wages_are_not_used(q):
    assert pd.isna(q.loc["C1698", "wage_it_2019"])         # unusable employment -> no wage either


def test_matched_requires_two_common_quarters():
    piv = pd.DataFrame({(2019, 1): [1.0, 1.0], (2019, 2): [1.0, np.nan], (2024, 1): [2.0, 2.0], (2024, 2): [2.0, 2.0]},
                       index=["a", "b"])
    piv.columns = pd.MultiIndex.from_tuples(piv.columns)
    v0, v1, n, basis, _, _ = bmp._growth_inputs(piv, 2019, 2024)
    assert basis.tolist() == ["matched", "unmatched"]      # b has only one common quarter
    assert n.tolist() == [2, 1]
    assert v1["b"] == pytest.approx(2.0)                   # fallback = plain mean of year B


def test_2019_level_is_kept_for_map_sizes_even_when_2024_is_withheld(q):
    assert q.loc["C1698", "emp_it_2019_reported"] == pytest.approx(65000)   # Chicago: level known, growth not
    assert q.loc["C1974", "emp_it_2019_reported"] == q.loc["C1974", "emp_it_2019"]
