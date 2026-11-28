"""Eurostat tables for round 3 hypothesis G (docs/hypotheses/round3/G.md), through the existing JSON-stat collector.

    python collect.py --sources eurostat_g
        -> data/raw/eurostat_jvs_q_nace2.csv   job vacancy rate (JVR), quarterly, sections J and B-S, NSA and SA, all size classes "TOTAL"
        -> data/raw/eurostat_irt_st_m.csv      money market interest rates, monthly, 3-month rate (IRT_M3)

The filters keep each reply under Eurostat's size cap (the unfiltered vacancy table is refused with HTTP 413).
`collectors/eurostat.py` is not edited; only its `collect()` is called with these two datasets.
"""
from __future__ import annotations

from collectors import eurostat

DATASETS_G: dict[str, dict] = {
    "jvs_q_nace2": {"filters": {"freq": "Q", "indic_em": "JVR", "sizeclas": "TOTAL", "nace_r2": ["J", "B-S"]}},
    "irt_st_m": {"filters": {"freq": "M", "int_rt": "IRT_M3"}},
}

SOURCES = {"eurostat_g": lambda a: eurostat.collect(datasets=DATASETS_G)}
