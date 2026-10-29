"""QCEW helpers: area-code classification and the national / area split."""
import pandas as pd
import pytest

from collectors import qcew


@pytest.mark.parametrize("fips,level", [
    ("US000", "national"), ("US500", "us_aggregate"), ("USCMS", "us_aggregate"),
    ("C3108", "metro_or_combined_area"), ("06000", "state"), ("06037", "county"),
    ("ZZ", "other"), ("6037", "other"),
])
def test_area_level(fips, level):
    assert qcew.area_level(fips) == level


def _frame():
    return pd.DataFrame({
        "area_fips": ["US000", "US000", "US000", "06037", "C3108", "C3108"],
        "own_code": [5, 5, 1, 5, 5, 5],
        "size_code": [0, 1, 0, 0, 0, 0],
        "year": 2019, "qtr": 1, "industry_code": "5415",
        "qtrly_estabs": [10, 4, 12, 3, 5, 6], "month1_emplvl": 1, "month2_emplvl": 2, "month3_emplvl": 3,
        "total_qtrly_wages": 9, "avg_wkly_wage": 5, "disclosure_code": ["", "", "", "", "N", ""],
    })


def test_split_keeps_private_all_sizes_only():
    nat, areas = qcew.split_national_and_areas(_frame())
    assert len(nat) == 1 and nat.iloc[0]["qtrly_estabs"] == 10      # own_code 5, size_code 0
    assert "area_fips" not in nat.columns                            # national KEEP has no area column
    assert sorted(areas["area_fips"]) == ["06037", "C3108", "C3108"]
    assert set(areas["area_level"]) == {"county", "metro_or_combined_area"}


def test_split_works_without_size_code_column():
    df = _frame().drop(columns="size_code")
    nat, areas = qcew.split_national_and_areas(df)
    assert len(nat) == 2 and len(areas) == 3                          # no size filter possible


def test_area_columns_keep_disclosure_code():
    _, areas = qcew.split_national_and_areas(_frame())
    assert "disclosure_code" in areas.columns
