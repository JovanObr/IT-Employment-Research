"""Master-file schema, country handling and the editable segment map."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger("covid_it_data")

SEGMENT_MAP = Path(__file__).resolve().parent.parent / "config" / "segment_map.csv"

COLUMNS = [
    "date", "frequency", "region", "country", "area_level",
    "segment_group", "segment", "industry_code", "granularity",
    "metric", "value", "unit", "breakdown",
    "source", "dataset", "series_id", "quality_flag", "notes",
]

ISO_FIX = {"EL": "GR", "UK": "GB"}  # Eurostat codes -> ISO 3166

COUNTRY_ISO = {
    # Europe (same list the layoffs loader treats as Europe)
    "United Kingdom": "GB", "Germany": "DE", "France": "FR", "Spain": "ES", "Italy": "IT",
    "Netherlands": "NL", "Ireland": "IE", "Sweden": "SE", "Norway": "NO", "Denmark": "DK",
    "Finland": "FI", "Poland": "PL", "Portugal": "PT", "Belgium": "BE", "Switzerland": "CH",
    "Austria": "AT", "Estonia": "EE", "Lithuania": "LT", "Latvia": "LV", "Czech Republic": "CZ",
    "Czechia": "CZ", "Romania": "RO", "Bulgaria": "BG", "Greece": "GR", "Hungary": "HU",
    "Croatia": "HR", "Slovenia": "SI", "Slovakia": "SK", "Luxembourg": "LU", "Iceland": "IS",
    "Serbia": "RS", "Ukraine": "UA", "Malta": "MT", "Cyprus": "CY",
    # US and the rest of the world
    "United States": "US", "India": "IN", "Israel": "IL", "Canada": "CA", "Brazil": "BR",
    "Australia": "AU", "Singapore": "SG", "Indonesia": "ID", "Nigeria": "NG", "China": "CN",
    "Kenya": "KE", "New Zealand": "NZ", "Japan": "JP", "Mexico": "MX", "Chile": "CL",
    "United Arab Emirates": "AE", "Argentina": "AR", "Colombia": "CO", "South Africa": "ZA",
    "Egypt": "EG", "Turkey": "TR", "Hong Kong": "HK", "Thailand": "TH", "Malaysia": "MY",
    "Vietnam": "VN", "Philippines": "PH", "Pakistan": "PK", "Bangladesh": "BD",
    "South Korea": "KR", "Taiwan": "TW", "Saudi Arabia": "SA", "Qatar": "QA", "Ghana": "GH",
    "Uruguay": "UY", "Peru": "PE", "Russia": "RU", "Senegal": "SN", "Seychelles": "SC",
    "UAE": "AE", "Cayman Islands": "KY", "Bahrain": "BH", "Myanmar": "MM",
}
EUROPE_ISO = {
    "GB", "DE", "FR", "ES", "IT", "NL", "IE", "SE", "NO", "DK", "FI", "PL", "PT", "BE", "CH",
    "AT", "EE", "LT", "LV", "CZ", "RO", "BG", "GR", "HU", "HR", "SI", "SK", "LU", "IS", "RS",
    "UA", "MT", "CY",
}


def region_of(iso: str) -> str:
    return "US" if iso == "US" else "Europe" if iso in EUROPE_ISO else "Other"


def load_segment_map(path: Path = SEGMENT_MAP) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def apply_segments(df: pd.DataFrame, seg_map: pd.DataFrame, scheme: str, code_col: str,
                   unmapped: set) -> pd.DataFrame:
    """Attach segment_group / segment / granularity. Unknown codes stay visible as '(unmapped)'."""
    m = (seg_map[seg_map["scheme"] == scheme]
         [["code", "segment_group", "segment", "granularity", "notes"]]
         .rename(columns={"code": "_code", "notes": "_map_notes"}))
    out = df.assign(_code=df[code_col].astype(str)).merge(m, how="left", on="_code")
    missing = out["segment_group"].isna()
    if missing.any():
        for c in out.loc[missing, "_code"].unique():
            unmapped.add((scheme, c))
        out.loc[missing, "segment_group"] = "(unmapped)"
        out.loc[missing, "segment"] = out.loc[missing, "_code"]
        out.loc[missing, "granularity"] = "unknown"
    out["_map_notes"] = out["_map_notes"].fillna("")
    return out.drop(columns="_code")


def join_notes(index, *parts) -> pd.Series:
    """Join note fragments (Series aligned to index, or plain strings) with '; ', skipping blanks."""
    cols = [(p.fillna("").astype(str).tolist() if isinstance(p, pd.Series) else [p] * len(index))
            for p in parts]
    return pd.Series(["; ".join(x for x in row if x) for row in zip(*cols)], index=index)


def finish(df: pd.DataFrame) -> pd.DataFrame:
    """Add series_id, enforce column order, blank-fill text columns."""
    df = df.copy()
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df["series_id"] = (df["dataset"] + "|" + df["industry_code"].astype(str) + "|" + df["country"].astype(str)
                       + "|" + df["breakdown"].astype(str) + "|" + df["metric"].astype(str))
    text = [c for c in COLUMNS if c != "value"]
    df[text] = df[text].fillna("").astype(str)
    return df[COLUMNS]
