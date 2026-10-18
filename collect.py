#!/usr/bin/env python3
"""Gather public data on IT employment before/after COVID-19 (US + Europe).

    python collect.py                       # everything
    python collect.py --sources eurostat indeed
    python collect.py --start-year 2016
"""
from __future__ import annotations

import argparse
import json
import logging

from collectors import bls, census_acs, eurostat, fhfa, hn, indeed, layoffs, nomis, qcew, sec
from collectors.common import RAW, ensure_dirs

SOURCES = {
    "eurostat": lambda a: eurostat.collect(),
    "bls": lambda a: bls.collect(a.start_year),
    "qcew": lambda a: qcew.collect(a.start_year),
    "nomis": lambda a: nomis.collect(a.start_year),
    "hn": lambda a: hn.collect(a.start_year),
    "sec": lambda a: sec.collect(a.start_year),
    "fhfa": lambda a: fhfa.collect(a.start_year),
    "acs": lambda a: census_acs.collect("acs1"),
    "acs5": lambda a: census_acs.collect("acs5"),
    "indeed": lambda a: indeed.collect(),
    "layoffs": lambda a: layoffs.collect(),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES))
    ap.add_argument("--start-year", type=int, default=2015)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    ensure_dirs()

    manifest = []
    for name in args.sources:
        logging.info("=== %s ===", name)
        try:
            manifest += SOURCES[name](args)
        except Exception:
            logging.exception("%s failed", name)

    path = RAW.parent / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    logging.info("Done. %d files recorded in %s (keep this for your attributions).", len(manifest), path)


if __name__ == "__main__":
    main()
