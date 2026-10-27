"""Census Gazetteer parser (collectors/census_gazetteer). Synthetic file in the documented layout."""
import io
import zipfile

import pytest

from collectors import census_gazetteer as cg

HEADER = "GEOID\tCSAFP\tNAME\tLSAD\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG  "
ROWS = [
    "10180\t\tAbilene, TX\tMetropolitan Statistical Area\t1\t1\t2.5\t0.1\t32.45\t-99.74",
    "100\t\tShort, XX\tMicropolitan Statistical Area\t1\t1\t1.0\t0.1\t 40.0\t -100.5 ",     # code lost its leading zeros
    "99999\t\tBroken, XX\tMetropolitan Statistical Area\t1\t1\t1.0\t0.1\t\t-100.0",         # no latitude: dropped
]


def make_zip(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("2023_Gaz_cbsa_national.txt", text)
    return b.getvalue()


def test_zip_is_parsed_with_string_codes_and_float_coordinates():
    df = cg.parse(make_zip("\n".join([HEADER, *ROWS]) + "\n"))
    assert list(df.columns) == ["cbsa_code", "name", "lsad", "lat", "lon", "aland_sqmi"]
    assert df["cbsa_code"].tolist() == ["10180", "00100"]            # leading zeros restored, bad row dropped
    a = df.iloc[0]
    assert a["lat"] == pytest.approx(32.45) and a["lon"] == pytest.approx(-99.74)   # trailing header spaces tolerated
    assert df.iloc[1]["lat"] == pytest.approx(40.0) and df.iloc[1]["lon"] == pytest.approx(-100.5)


def test_plain_text_and_cp1252():
    txt = "\n".join([HEADER, "10100\t\tAño, TX\tMetropolitan Statistical Area\t1\t1\t2.5\t0.1\t32.45\t-99.74"]).encode("cp1252")
    df = cg.parse(txt)
    assert len(df) == 1 and df.iloc[0]["cbsa_code"] == "10100"


def test_missing_columns_raise_a_clear_error():
    with pytest.raises(ValueError, match="INTPTLAT"):
        cg.parse(make_zip("GEOID\tNAME\n10180\tx\n"))


def test_collect_writes_file_and_registers_source(data_dir, monkeypatch):
    monkeypatch.setattr(cg, "fetch", lambda url, **kw: make_zip("\n".join([HEADER, *ROWS]) + "\n"))
    rec = cg.SOURCES["gazetteer"](None)
    assert (data_dir / "raw" / "census_gazetteer_cbsa.csv").exists() and rec[0]["url"] == cg.URL
