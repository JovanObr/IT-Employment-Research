"""Eurostat via the official dissemination API (JSON-stat). No key needed.

Terms: Eurostat data may be reused free of charge with attribution.
"""
from __future__ import annotations

import json
import logging

import pandas as pd
import requests

from .common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
LICENCE = "Eurostat: free reuse with attribution (https://ec.europa.eu/eurostat/about-us/policies/copyright)"

# code -> {server-side filters, optional client-side NACE filter}
DATASETS: dict[str, dict] = {
    "isoc_sks_itspt": {},  # ICT specialists, total
    "isoc_sks_itsps": {},  # ... by sex
    "isoc_sks_itspa": {},  # ... by age
    "isoc_sks_itspe": {},  # ... by education
    # Employment by 2-digit NACE (J58 publishing, J62_J63 IT services, ...).
    # Server-side filters keep the response under Eurostat's size cap; NACE is
    # filtered locally because the exact J-codes differ between datasets.
    "lfsa_egan22d": {
        "filters": {"freq": "A", "unit": "THS_PER", "sex": "T", "age": "Y15-74"},
        "nace_keep": ("TOTAL", "J"),
    },
}


def jsonstat_to_df(js: dict, label_dims: tuple[str, ...] = ("geo", "nace_r2")) -> pd.DataFrame:
    """Flatten a JSON-stat 2.0 dataset into a tidy DataFrame (one row per value)."""
    ids, sizes = js["id"], js["size"]
    orders, labels = [], {}
    for d in ids:
        cat = js["dimension"][d]["category"]
        idx = cat["index"]
        order = sorted(idx, key=idx.get) if isinstance(idx, dict) else list(idx)
        orders.append(order)
        labels[d] = cat.get("label", {})

    strides = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    values = js.get("value", {})
    items = (
        ((i, v) for i, v in enumerate(values) if v is not None)
        if isinstance(values, list)
        else ((int(k), v) for k, v in values.items())
    )
    status = js.get("status", {}) or {}

    rows = []
    for flat, v in items:
        row = {d: orders[j][(flat // strides[j]) % sizes[j]] for j, d in enumerate(ids)}
        row["value"] = v
        row["flag"] = status.get(str(flat), status.get(flat, ""))
        rows.append(row)

    df = pd.DataFrame(rows)
    for d in label_dims:
        if d in df.columns:
            df[f"{d}_label"] = df[d].map(labels[d])
    return df


def _get(code: str, filters: dict) -> dict:
    params = {"format": "JSON", "lang": "EN", **filters}
    raw = fetch(f"{BASE}/{code}", params=params)
    return json.loads(raw)


def collect(datasets: dict[str, dict] | None = None) -> list[dict]:
    ensure_dirs()
    records = []
    for code, cfg in (datasets or DATASETS).items():
        try:
            try:
                js = _get(code, cfg.get("filters", {}))
            except requests.HTTPError as e:
                if cfg.get("filters"):
                    log.warning("Eurostat %s: filters rejected (%s); retrying unfiltered", code, e)
                    js = _get(code, {})
                else:
                    raise
            df = jsonstat_to_df(js)
            keep = cfg.get("nace_keep")
            if keep and "nace_r2" in df.columns:
                df = df[df["nace_r2"].str.startswith(keep)]
            out = RAW / f"eurostat_{code}.csv"
            df.to_csv(out, index=False)
            log.info("Eurostat %s: %d rows -> %s", code, len(df), out)
            records.append(record(f"Eurostat {code}", out, f"{BASE}/{code}", LICENCE))
        except Exception as e:  # keep going so one bad dataset doesn't kill the run
            log.error("Eurostat %s failed: %s", code, e)
    return records
