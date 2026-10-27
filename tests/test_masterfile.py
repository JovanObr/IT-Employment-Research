"""Master-file schema: unmapped codes stay visible, and the duplicate-key check in build_master."""
import pandas as pd

import build_master
from masterfile import schema as S

SEG = pd.DataFrame([
    {"scheme": "naics", "code": "5415", "segment_group": "IT services", "segment": "Computer systems design",
     "granularity": "detailed", "notes": "n1"},
    {"scheme": "nace", "code": "J62", "segment_group": "IT services", "segment": "Programming",
     "granularity": "detailed", "notes": ""},
])


def test_apply_segments_maps_known_codes():
    unmapped = set()
    out = S.apply_segments(pd.DataFrame({"code": ["5415"], "v": [1]}), SEG, "naics", "code", unmapped)
    assert out.iloc[0]["segment_group"] == "IT services" and out.iloc[0]["granularity"] == "detailed"
    assert unmapped == set()


def test_unmapped_codes_are_kept_visible_not_dropped():
    unmapped = set()
    df = pd.DataFrame({"code": ["5415", "9999", "9999"], "v": [1, 2, 3]})
    out = S.apply_segments(df, SEG, "naics", "code", unmapped)
    assert len(out) == 3                                   # nothing silently dropped
    bad = out[out["code"] == "9999"]
    assert (bad["segment_group"] == "(unmapped)").all() and (bad["segment"] == "9999").all()
    assert (bad["granularity"] == "unknown").all()
    assert unmapped == {("naics", "9999")}


def test_scheme_is_respected():
    unmapped = set()
    out = S.apply_segments(pd.DataFrame({"code": ["J62"]}), SEG, "naics", "code", unmapped)
    assert out.iloc[0]["segment_group"] == "(unmapped)"    # J62 exists, but only under scheme 'nace'


def test_join_notes_skips_blanks():
    idx = pd.RangeIndex(2)
    out = S.join_notes(idx, pd.Series(["a", ""], index=idx), "x", pd.Series([None, "b"], index=idx))
    assert out.tolist() == ["a; x", "x; b"]


def _master(dates):
    rows = [{"date": d, "dataset": "bls_ces", "industry_code": "X", "country": "US", "breakdown": "",
             "metric": "employment_level", "value": 1.0, "unit": "thousand persons"} for d in dates]
    return S.finish(pd.DataFrame(rows))


def test_finish_builds_series_id_and_column_order():
    m = _master(["2020-01-01"])
    assert list(m.columns) == S.COLUMNS
    assert m.iloc[0]["series_id"] == "bls_ces|X|US||employment_level"


def test_build_master_validation_fails_on_duplicate_keys(data_dir):
    lines, fails = build_master.validate(_master(["2020-01-01", "2020-01-01"]), set())
    assert fails >= 1
    assert any(l.startswith("FAIL") and "duplicate" in l for l in lines)


def test_build_master_validation_passes_on_clean_data(data_dir):
    lines, fails = build_master.validate(_master(["2020-01-01", "2020-02-01"]), set())
    assert fails == 0
    assert any(l.startswith("PASS") and "duplicate" in l for l in lines)


def test_validation_lists_unmapped_codes(data_dir):
    lines, _ = build_master.validate(_master(["2020-01-01"]), {("naics", "9999")})
    assert any("UNMAPPED" in l for l in lines) and any("naics: 9999" in l for l in lines)
