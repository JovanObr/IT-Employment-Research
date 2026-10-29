"""analysis/geo: outline sanity, map building on synthetic metros, QCEW code-stability check."""
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
import pytest

from analysis import geo

CITIES_INSIDE = {"Denver": (-104.99, 39.74), "Dallas": (-96.8, 32.78), "Atlanta": (-84.39, 33.75),
                 "Chicago": (-87.63, 41.88), "Seattle": (-122.33, 47.61), "Boston": (-71.06, 42.36),
                 "Minneapolis": (-93.27, 44.98), "Phoenix": (-112.07, 33.45), "St. Louis": (-90.2, 38.63),
                 "Houston": (-95.37, 29.76), "Detroit": (-83.05, 42.33), "Los Angeles": (-118.24, 34.05),
                 "Kansas City": (-94.58, 39.1), "Nashville": (-86.78, 36.16)}
POINTS_OUTSIDE = {"Atlantic": (-68.0, 38.0), "Gulf": (-90.0, 26.0), "Pacific": (-130.0, 40.0),
                  "Canada": (-100.0, 52.0), "Mexico": (-102.0, 24.5), "Honolulu": (-157.86, 21.31),
                  "Anchorage": (-149.9, 61.2), "San Juan": (-66.1, 18.4)}


def test_outline_is_a_closed_ring_within_bounds():
    o = np.array(geo.US48_OUTLINE)
    assert tuple(o[0]) == tuple(o[-1])
    assert o[:, 0].min() >= -125.5 and o[:, 0].max() <= -66.0 and o[:, 1].min() >= 24.0 and o[:, 1].max() <= 49.8


@pytest.mark.parametrize("name", CITIES_INSIDE)
def test_big_cities_fall_inside_the_outline(name):
    assert geo.point_in_outline(*[[v] for v in CITIES_INSIDE[name]])[0]


@pytest.mark.parametrize("name", POINTS_OUTSIDE)
def test_sea_and_other_countries_fall_outside_the_outline(name):
    assert not geo.point_in_outline(*[[v] for v in POINTS_OUTSIDE[name]])[0]


def test_lower48_box_excludes_ak_hi_pr():
    xs = [CITIES_INSIDE["Denver"][0], -157.86, -149.9, -66.1]
    ys = [CITIES_INSIDE["Denver"][1], 21.31, 61.2, 18.4]
    assert geo.in_lower48(xs, ys).tolist() == [True, False, False, False]


def synthetic_geo():
    rows = [("10000", "Alpha-Beta, XX Metro Area", -104.99, 39.74, 50_000, 30.0, 20.0, 1e6),
            ("20000", "Chicago-Naperville, IL Metro Area", -87.63, 41.88, np.nan, np.nan, 10.0, 4e6),   # jobs growth withheld
            ("30000", "Smallville, TX Metro Area", -96.8, 32.78, 800, -20.0, np.nan, 3e4),
            ("40000", "Honolulu, HI Metro Area", -157.86, 21.31, 9_000, 5.0, 5.0, 4e5),
            ("50000", "Nowhere, ZZ Metro Area", np.nan, np.nan, 100, 1.0, 1.0, 1e4)]
    g = pd.DataFrame(rows, columns=["cbsa_code", "metro_name", "lon", "lat", "emp_it_2019", "it_growth_pct",
                                    "estab_growth_pct", "emp_total_2019"])
    g["emp_it_2019_reported"] = g["emp_it_2019"]
    g.loc[1, "emp_it_2019_reported"] = 65_000
    g["size_jobs"] = g["emp_it_2019"].fillna(g["emp_it_2019_reported"])
    return g


def test_coverage_report_counts_unplaced_and_non_lower48():
    c = geo.coverage_report(synthetic_geo())
    assert c["metros"] == 5 and c["without_centroid"] == 1 and c["outside_lower48"] == 1 and c["drawn"] == 3
    assert c["without_centroid_names"] == ["Nowhere, ZZ Metro Area"]


def test_make_maps_writes_two_figures(tmp_path):
    paths = geo.make_maps(synthetic_geo(), tmp_path)
    assert [p.name for p in paths] == ["06_map_it_employment_growth.png", "06_map_it_establishment_growth.png"]
    assert all(p.exists() and p.stat().st_size > 5_000 for p in paths)


def test_short_name():
    assert geo.short_name("Chicago-Naperville-Elgin, IL-IN-WI Metro Area") == "Chicago"
    assert geo.short_name("Abilene, TX Metro Area") == "Abilene"


def test_load_geo_panel_joins_on_string_codes_and_falls_back_for_old_panels(tmp_path):
    pd.DataFrame({"cbsa_code": ["10180", "100"], "metro_name": ["A", "B"], "emp_it_2019": [5.0, np.nan]}).to_csv(tmp_path / "p.csv", index=False)
    pd.DataFrame({"cbsa_code": ["10180", "00100"], "name": ["A", "B"], "lsad": ["m", "m"], "lat": [1.0, 2.0], "lon": [3.0, 4.0]}).to_csv(tmp_path / "g.csv", index=False)
    g = geo.load_geo_panel(tmp_path / "p.csv", tmp_path / "g.csv")
    assert g["lat"].tolist() == [1.0, 2.0]                 # 100 was zero-padded and matched
    assert g["size_jobs"].iloc[0] == 5.0


def areas(spec):
    rows = [{"area_fips": c, "year": y, "industry_code": i} for c, years in spec.items() for y in years for i in ("5415", "10")]
    return pd.DataFrame(rows)


def test_code_stability_lists_codes_in_only_one_year():
    a = areas({"C1018": range(2015, 2025), "C2222": range(2015, 2022), "C3333": range(2023, 2025), "C4444": [2019, 2024]})
    s = geo.code_stability(a)
    got = s.set_index("area_fips")["only_in"].to_dict()
    assert got == {"C1018": "", "C2222": "2019", "C3333": "2024", "C4444": ""}
    assert s.set_index("area_fips").loc["C2222", "cbsa_code"] == "22220"
    assert geo.only_one_year(s)["area_fips"].tolist() == ["C2222", "C3333"]


def test_code_stability_ignores_non_metro_codes_and_can_filter_by_industry():
    a = pd.concat([areas({"C1018": [2019, 2024], "06037": [2019]}),
                   pd.DataFrame([{"area_fips": "C5555", "year": 2019, "industry_code": "5415"}])])
    s = geo.code_stability(a)
    assert set(s["area_fips"]) == {"C1018", "C5555"}
    assert set(geo.code_stability(a, industry="10")["area_fips"]) == {"C1018"}   # C5555 only has an IT row
