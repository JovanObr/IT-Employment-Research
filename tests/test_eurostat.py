"""JSON-stat flattening (collectors/eurostat.jsonstat_to_df). Synthetic replies, no network."""
import pandas as pd

from collectors import eurostat


def _dim(codes, labels=None):
    return {"category": {"index": {c: i for i, c in enumerate(codes)}, "label": labels or {c: c.title() for c in codes}}}


def test_two_dimension_dataset_has_no_breakdown_columns():
    """Regression: a dataset with only geo and time (no sex/age/NACE) must not break or invent columns."""
    js = {"id": ["geo", "time"], "size": [2, 3],
          "dimension": {"geo": _dim(["SI", "DE"], {"SI": "Slovenia", "DE": "Germany"}),
                        "time": _dim(["2019", "2020", "2021"])},
          "value": {"0": 1.0, "1": 2.0, "2": 3.0, "3": 4.0, "5": 6.0}}
    df = eurostat.jsonstat_to_df(js)
    assert set(df.columns) == {"geo", "time", "value", "flag", "geo_label"}
    assert "nace_r2_label" not in df.columns
    assert len(df) == 5                                   # flat index 4 is missing, so no row
    row = df[(df.geo == "DE") & (df.time == "2021")].iloc[0]
    assert row["value"] == 6.0 and row["geo_label"] == "Germany"


def test_row_major_index_and_flags():
    js = {"id": ["nace_r2", "geo", "time"], "size": [2, 2, 2],
          "dimension": {"nace_r2": _dim(["TOTAL", "J"]), "geo": _dim(["SI", "DE"]), "time": _dim(["2020", "2021"])},
          "value": [10, 11, 12, 13, 14, None, 16, 17],
          "status": {"3": "b", "6": "e"}}
    df = eurostat.jsonstat_to_df(js)
    assert len(df) == 7                                    # the None is skipped
    r = df[(df.nace_r2 == "J") & (df.geo == "DE") & (df.time == "2021")].iloc[0]
    assert r["value"] == 17
    assert df[df["value"] == 13].iloc[0]["flag"] == "b"    # flat index 3
    assert df[df["value"] == 16].iloc[0]["flag"] == "e"
    assert df[df["value"] == 10].iloc[0]["flag"] == ""
    assert "nace_r2_label" in df.columns and "geo_label" in df.columns


def test_dimension_of_size_one_and_list_index():
    """Size-1 dimensions (unit, freq) and `index` given as a list instead of a dict."""
    js = {"id": ["unit", "geo", "time"], "size": [1, 2, 1],
          "dimension": {"unit": {"category": {"index": ["PC"], "label": {"PC": "Percent"}}},
                        "geo": {"category": {"index": ["SI", "AT"]}},
                        "time": {"category": {"index": ["2020"]}}},
          "value": [4.5, 5.5]}
    df = eurostat.jsonstat_to_df(js)
    assert df["unit"].tolist() == ["PC", "PC"] and df["geo"].tolist() == ["SI", "AT"]
    assert df["value"].tolist() == [4.5, 5.5]


def test_empty_dataset_returns_empty_frame():
    js = {"id": ["geo", "time"], "size": [1, 1],
          "dimension": {"geo": _dim(["SI"]), "time": _dim(["2020"])}, "value": {}}
    df = eurostat.jsonstat_to_df(js)
    assert isinstance(df, pd.DataFrame) and df.empty
