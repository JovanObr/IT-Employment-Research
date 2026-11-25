"""SURS (Statistični urad RS), SiStat table 0700921S: persons in employment by activity (SKD 2008), Slovenia, monthly (register SRDAP).

    python collect.py --sources surs        # -> data/raw/surs_0700921S.csv (activity, status, month, value)

The table is downloaded whole as a PC-Axis file and parsed here (no extra library). Used by round 3 hypothesis H
(docs/hypotheses/round3/H.md).
"""
from __future__ import annotations

import logging
import re
from itertools import product

import pandas as pd

from collectors.common import RAW, ensure_dirs, fetch, record

log = logging.getLogger("covid_it_data")
TABLE = "0700921S"
URLS = [f"https://pxweb.stat.si/SiStat/sl/Home/DownloadPxMatrix?pxMatrixName={TABLE}",
        f"https://pxweb.stat.si/SiStatData/Resources/PX/Databases/Data/{TABLE}.PX"]
LICENCE = "SURS: podatki so prosto dostopni; obvezno navajanje vira (Vir: SURS)"
MISSING = {".", "..", "...", "-", "....", "z", "M", "N"}


def _encoding(raw: bytes) -> str:
    m = re.search(rb'CODEPAGE\s*=\s*"([^"]+)"', raw[:4000])
    return m.group(1).decode("ascii") if m else "windows-1250"


def _strings(value: str) -> list[str]:
    """The quoted strings of a PX value ("a","b", possibly over several lines)."""
    return re.findall(r'"((?:[^"]|"")*)"', value)


def _statements(head: str) -> list[str]:
    """Split the header into KEY=VALUE statements at semicolons outside quotes."""
    out, buf, quoted = [], [], False
    for ch in head:
        if ch == '"':
            quoted = not quoted
        if ch == ";" and not quoted:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    return out


def parse_px(raw: bytes) -> pd.DataFrame:
    """Parse a PC-Axis file into one row per data cell, one column per variable plus `value` (NaN for missing marks).
    Cells are ordered as the STUB variables followed by the HEADING variables, the last one varying fastest."""
    text = raw.decode(_encoding(raw), errors="replace")
    head, sep, data = text.partition("DATA=")
    if not sep:
        raise ValueError("no DATA= section in the PX file")
    keys: dict[str, str] = {}
    for stmt in _statements(head):
        m = re.match(r'\s*([A-Z0-9\-]+)(\[[A-Za-z\-]+\])?(?:\("([^"]*)"\))?\s*=\s*(.*)\Z', stmt, re.S)
        if not m or m.group(2):                                  # KEY[en]=... is another language: skipped
            continue
        keys[m.group(1) + (f"|{m.group(3)}" if m.group(3) is not None else "")] = m.group(4)
    stub = _strings(keys.get("STUB", ""))
    heading = _strings(keys.get("HEADING", ""))
    variables = stub + heading
    values = [_strings(keys[f"VALUES|{v}"]) for v in variables]
    tokens = data.replace(";", " ").split()
    cells = []
    for t in tokens:
        t = t.strip('"')
        cells.append(float("nan") if (t in MISSING or t == "") else float(t))
    n = 1
    for v in values:
        n *= len(v)
    if len(cells) != n:
        raise ValueError(f"PX file has {len(cells)} data cells, expected {n} from the variables {variables}")
    df = pd.DataFrame(list(product(*values)), columns=variables)
    df["value"] = cells
    return df


def tidy(px: pd.DataFrame) -> pd.DataFrame:
    """Columns activity, status, month (YYYY-MM-01), value from table 0700921S."""
    cols = {c.upper(): c for c in px.columns}
    act = next(cols[c] for c in cols if "DEJAVNOST" in c)
    month = next(cols[c] for c in cols if "MESEC" in c)
    status = next(cols[c] for c in cols if "PREBIVALSTVO" in c)
    out = px.rename(columns={act: "activity", month: "month", status: "status"})[["activity", "status", "month", "value"]]
    out["month"] = pd.to_datetime(out["month"].str.replace("M", "-", regex=False) + "-01")
    return out


def collect() -> list[dict]:
    ensure_dirs()
    last = None
    for url in URLS:
        try:
            raw = fetch(url, max_age_days=30, cache_ok=lambda b: b"DATA=" in b)
            df = tidy(parse_px(raw))
            break
        except Exception as e:  # noqa: BLE001 - try the next address
            last = e
            log.warning("SURS %s: %s", url, e)
    else:
        raise RuntimeError(f"SURS {TABLE}: no address worked ({last})")
    out = RAW / f"surs_{TABLE}.csv"
    df.to_csv(out, index=False)
    log.info("SURS %s: %d rows -> %s", TABLE, len(df), out)
    return [record(f"SURS SiStat {TABLE}", out, url, LICENCE)]


SOURCES = {"surs": lambda a: collect()}
