"""FHFA parser: header-less file, '-' = not published, '(MSAD)' divisions."""
from collectors import fhfa

RAW = (
    '"Abilene, TX",10180,1995,1,100.00,0.00\n'
    '"Abilene, TX",10180,2019,1,150.25,1.10\n'
    '"Abilene, TX",10180,2019,2,-,-\n'
    '"New York-Jersey City-White Plains, NY-NJ (MSAD)",35614,2019,1,300.5,2.0\n'
    '"Weird, XX",99999,notayear,1,100,1\n'
)


def test_header_less_file_is_parsed_and_filtered_by_start_year():
    df = fhfa.parse(RAW.encode(), start_year=2015)
    assert list(df.columns) == ["place_name", "cbsa_code", "is_division", "year", "quarter", "hpi_nsa"]
    assert set(df["year"]) == {2019}                      # 1995 dropped, the junk year dropped
    assert df["year"].dtype.kind == "i" and df["quarter"].dtype.kind == "i"


def test_dash_becomes_missing_and_codes_stay_strings():
    df = fhfa.parse(RAW.encode(), start_year=2015)
    q2 = df[(df.cbsa_code == "10180") & (df.quarter == 2)].iloc[0]
    assert q2["hpi_nsa"] != q2["hpi_nsa"]                 # NaN
    q1 = df[(df.cbsa_code == "10180") & (df.quarter == 1)].iloc[0]
    assert q1["hpi_nsa"] == 150.25
    assert all(isinstance(c, str) for c in df["cbsa_code"])


def test_msad_flag():
    df = fhfa.parse(RAW.encode(), start_year=2015).set_index("cbsa_code")
    assert df.loc["35614", "is_division"] == 1
    assert df.loc["10180", "is_division"].tolist() == [0, 0]


def test_cp1252_fallback():
    raw = '"Ca\xf1on City, CO",15860,2019,1,200,1\n'.encode("cp1252")
    df = fhfa.parse(raw, start_year=2015)
    assert len(df) == 1 and "Ca" in df.iloc[0]["place_name"]
