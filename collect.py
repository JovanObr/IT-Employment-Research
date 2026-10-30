#!/usr/bin/env python3
"""Gather public data on IT employment before/after COVID-19 (US + Europe).

    python collect.py                       # everything
    python collect.py --sources eurostat indeed
    python collect.py --start-year 2016
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import pkgutil

import collectors
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


def _discover() -> dict:
    """NEW collectors register themselves: define `SOURCES = {"name": lambda args: [...]}` at module level in
    collectors/<module>.py (args has .start_year). No edit to this file is needed, so two people adding sources
    never collide here."""
    found = {}
    for m in pkgutil.iter_modules(collectors.__path__):
        if m.name == "common":
            continue
        try:
            mod = importlib.import_module(f"collectors.{m.name}")
        except Exception as e:  # a broken new collector must not break the others
            logging.warning("collectors/%s.py failed to import: %s", m.name, e)
            continue
        for name, fn in getattr(mod, "SOURCES", {}).items():
            if name in SOURCES or name in found:
                raise SystemExit(f"Duplicate source name {name!r} (collectors/{m.name}.py)")
            found[name] = fn
    return found


SOURCES.update(_discover())


def merge_manifest(old: list[dict], new: list[dict]) -> list[dict]:
    """Keep entries from earlier runs; a source that ran again replaces its own entries (matched by file path,
    with Windows and POSIX separators treated as the same). A partial run used to overwrite the whole manifest."""
    key = lambda e: str(e.get("file", "")).replace("\\", "/")
    merged = {key(e): e for e in old}
    merged.update({key(e): e for e in new})
    return list(merged.values())


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
    old = []
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            logging.warning("%s was unreadable; starting a new manifest", path)
    manifest = merge_manifest(old, manifest)
    path.write_text(json.dumps(manifest, indent=2))
    logging.info("Done. %d files recorded in %s (keep this for your attributions).", len(manifest), path)


if __name__ == "__main__":
    main()
