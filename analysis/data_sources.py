"""Where the data in every figure comes from: the original source and the exact CSV files ("Viri podatkov" under each graph).

Three tables, all checked by tests/test_data_sources.py against the committed data/manifest.json:

* FIGURE_SOURCES  figure name -> the CSV files the figure reads (raw files, or derived files listed in DERIVED)
* DERIVED         a derived file in data/processed -> (the command that builds it, the files it is built from)
* SOURCE_LABELS   a file recorded in data/manifest.json -> the original source, in Slovenian, for a casual reader

Adding a figure without adding it to FIGURE_SOURCES makes `sources_markdown` raise, so the notebook cannot show a graph
without saying where its data comes from. Licences and full URLs stay in data/manifest.json and DATA_SOURCES.md.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"

# Original source of each file recorded in the manifest. Files with the same label are listed together under one source.
_BLS_QCEW = "ameriški statistični urad za delo (BLS), popis zaposlenih in podjetij QCEW"
_SEC = "SEC EDGAR, javna finančna poročila ameriških borznih podjetij"
_HN = "Hacker News, mesečne niti »Who is hiring?«, kjer podjetja objavljajo prosta delovna mesta"
_CENSUS_ACS = "ameriški urad za popis prebivalstva (Census), raziskava ACS"
_EUROSTAT = "Eurostat, statistični urad Evropske unije"
_INDEED = "Indeed Hiring Lab, oglasi za delo na portalu Indeed"
SOURCE_LABELS = {
    "data/processed/layoffs_clean.csv": "Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen)",
    "data/raw/fred_series.csv": "FRED, Zvezna rezervna banka St. Louis (obrestna mera Fed in borzni indeks NASDAQ)",
    "data/raw/bls_jolts.csv": "ameriški statistični urad za delo (BLS), raziskava JOLTS o odpuščanjih in prostih mestih",
    "data/raw/bls_ces_employment.csv": "ameriški statistični urad za delo (BLS), mesečna raziskava CES o zaposlenih",
    "data/raw/bls_qcew_it_industries.csv": _BLS_QCEW,
    "data/raw/bls_qcew_areas_it_industries.csv": _BLS_QCEW,
    "data/raw/sec_company_matches.csv": _SEC,
    "data/raw/sec_revenue_quarterly.csv": _SEC,
    "data/raw/sec_universe_sic.csv": _SEC,
    "data/raw/sec_revenue_universe.csv": _SEC,
    "data/raw/sec_financials_quarterly.csv": _SEC,
    "data/raw/sec_headcount.csv": "SEC EDGAR, letna poročila 10-K (število zaposlenih, prebrano iz besedila)",
    "data/raw/prices_daily.csv": "Yahoo Finance, dnevne cene delnic (prenesene s knjižnico yfinance)",
    "data/raw/hn_whoishiring_posts.csv": _HN,
    "data/raw/hn_whoishiring_text.csv": _HN,
    "data/raw/fhfa_hpi_metro_quarterly.csv": "ameriška agencija za stanovanjsko financiranje (FHFA), indeks cen stanovanj",
    "data/raw/census_acs1_metro.csv": _CENSUS_ACS,
    "data/raw/census_acs5_metro.csv": _CENSUS_ACS,
    "data/raw/census_gazetteer_cbsa.csv": "ameriški urad za popis prebivalstva (Census), lega mestnih območij (Gazetteer)",
    "data/raw/nomis_bres_it_industries.csv": "britanski statistični urad ONS, raziskava BRES (prek portala Nomis)",
    "data/raw/eurostat_isoc_sks_itspt.csv": _EUROSTAT,
    "data/raw/eurostat_isoc_sks_itsps.csv": _EUROSTAT,
    "data/raw/eurostat_isoc_sks_itspa.csv": _EUROSTAT,
    "data/raw/eurostat_isoc_sks_itspe.csv": _EUROSTAT,
    "data/raw/eurostat_lfsa_egan22d.csv": _EUROSTAT,
    "data/raw/indeed_aggregate_postings.csv": _INDEED,
    "data/raw/indeed_it_sector_postings.csv": _INDEED,
    # Stream B, Milestone 2
    "data/raw/indeed_remote_postings.csv": "Indeed Hiring Lab, delež oglasov v ZDA, ki ponujajo delo na daljavo ali hibridno delo",
}

# Derived files: how they are built and from what. Only the inputs whose numbers reach the file are listed.
_SEC_PANEL = ["data/raw/sec_financials_quarterly.csv", "data/raw/sec_revenue_universe.csv", "data/raw/sec_universe_sic.csv",
              "data/raw/sec_company_matches.csv", "data/processed/layoffs_clean.csv"]
DERIVED = {
    "data/processed/company_panel.csv": ("python -m analysis.company_panel", _SEC_PANEL),
    "data/processed/hn_flags_monthly.csv": ("python -m analysis.hn_text flags", ["data/raw/hn_whoishiring_posts.csv"]),
    "data/processed/hn_change_points.csv": ("python -m analysis.hn_text flags", ["data/raw/hn_whoishiring_posts.csv"]),
    "data/processed/hn_topics_monthly.csv": ("python -m analysis.hn_text run",
                                             ["data/raw/hn_whoishiring_posts.csv", "data/raw/hn_whoishiring_text.csv"]),
    "data/processed/metro_panel.csv": ("python build_metro_panel.py",
                                       ["data/raw/bls_qcew_areas_it_industries.csv", "data/raw/bls_qcew_it_industries.csv",
                                        "data/raw/fhfa_hpi_metro_quarterly.csv", "data/raw/census_acs5_metro.csv"]),
    "data/processed/event_study_events.csv": ("python -m analysis.event_study",
                                              ["data/processed/layoffs_clean.csv", "data/raw/sec_company_matches.csv", "data/raw/prices_daily.csv"]),
    # The map table keeps the QCEW job and establishment columns of metro_panel.csv plus the Gazetteer coordinates, and one ACS
    # column (wfh_share_pct_acs2019, kept for the chapter 4-5 brief; no figure draws it). Stream B 2026-11-10: ACS added below
    # because its numbers reach the file.
    "data/processed/metro_map_data.csv": ("python build_metro_panel.py, nato python -m analysis.geo mapdata",
                                          ["data/raw/bls_qcew_areas_it_industries.csv", "data/raw/census_gazetteer_cbsa.csv",
                                           "data/raw/census_acs5_metro.csv"]),
    # Stream B, Milestone 2
    "data/processed/indeed_remote_monthly.csv": ("python -m analysis.compare_text_geo aggregates",
                                                 ["data/raw/indeed_remote_postings.csv"]),
}

_LAYOFFS = "data/processed/layoffs_clean.csv"
_H3 = _SEC_PANEL                                        # causes.run_h3: revenue and cost growth 2019-2021 of tech companies
_STOCK = [_LAYOFFS, "data/raw/sec_company_matches.csv", "data/raw/prices_daily.csv"]
FIGURE_SOURCES = {
    # chapter 1
    "1_casovnica": [_LAYOFFS, "data/raw/fred_series.csv", "data/processed/hn_flags_monthly.csv"],
    "1_koledar": [_LAYOFFS],
    "1_ljudje": [_LAYOFFS],
    "1_najvecje": [_LAYOFFS],
    # chapter 2
    "2_datumi": [_LAYOFFS],
    "2_zamiki": [_LAYOFFS, "data/raw/fred_series.csv", "data/raw/bls_jolts.csv"],
    "2_rast": _H3,
    # chapter 3
    "3_velikost": ["data/processed/company_panel.csv"],
    "3_podjetja": _H3,
    "3_modeli": ["data/processed/company_panel.csv"],
    "3_skupine": ["data/processed/company_panel.csv"],
    # chapters 4-5 (Stream B: analysis/viz_text_geo.py)
    "4_teme_povrsina": ["data/processed/hn_topics_monthly.csv"],
    "4_teme_mali_grafi": ["data/processed/hn_topics_monthly.csv"],
    "4_teme_toplotna": ["data/processed/hn_topics_monthly.csv"],
    "4_daljava_ui": ["data/processed/hn_flags_monthly.csv", "data/processed/hn_change_points.csv"],
    "5_zemljevid": ["data/processed/metro_map_data.csv"],
    "5_regije": ["data/processed/metro_map_data.csv"],
    # chapter 6 (company size for the groups comes from the balance sheets)
    "6_pot": _STOCK,
    "6_porazdelitev": _STOCK,
    "6_skupine": _STOCK + ["data/raw/sec_financials_quarterly.csv"],
    # notebook 09, comparisons with published studies (Stream A: analysis/compare_viz.py); published numbers are named in the text
    "9a_challenger": [_LAYOFFS],
    "9a_borza_delez": ["data/processed/event_study_events.csv", _LAYOFFS, "data/raw/sec_company_matches.csv"],
    "9a_znotraj": ["data/processed/company_panel.csv"],
    "9a_zaposlovanje": ["data/raw/sec_headcount.csv"] + _H3,
    # notebook 10, pre-registered hypotheses (analysis/hypotheses_viz.py); A and B are drawn from Stream B's results file
    "10a_slovenija": ["data/raw/eurostat_isoc_sks_itspt.csv"],
    "10b_sf_austin": ["data/raw/bls_qcew_areas_it_industries.csv"],
    "10c_zaposleni": ["data/raw/sec_headcount.csv", "data/raw/sec_universe_sic.csv", _LAYOFFS, "data/raw/sec_company_matches.csv",
                      "data/processed/company_panel.csv"],
    "10d_borza": ["data/processed/event_study_events.csv", _LAYOFFS, "data/raw/sec_company_matches.csv"],
    # notebook 09, Stream B (analysis/compare_text_geo.py); published numbers are named in the text
    "9b_daljava_primerjava": ["data/processed/hn_flags_monthly.csv", "data/processed/indeed_remote_monthly.csv"],
    "9b_ui_primerjava": ["data/processed/hn_flags_monthly.csv"],
    "9b_mladi": ["data/processed/hn_flags_monthly.csv"],      # shown only once junior_v2 passed its validation (D1)
    "9b_regije_primerjava": ["data/processed/metro_map_data.csv"],
}


def norm(path: str) -> str:
    """'data\\raw\\x.csv' (Windows, as written by collect.py) and 'data/raw/x.csv' are the same file."""
    return str(path).replace("\\", "/").lstrip("./")


def load_manifest(path: Path | None = None) -> dict[str, dict]:
    """The manifest as {normalised file path: record}."""
    records = json.loads(Path(path or MANIFEST).read_text(encoding="utf-8"))
    return {norm(r["file"]): r for r in records}


def originals(files: list[str], derived: dict | None = None) -> list[str]:
    """The original (manifest) files behind `files`, following DERIVED, in first-seen order without duplicates."""
    derived = DERIVED if derived is None else derived
    out, seen = [], set()

    def walk(f: str, depth: int = 0) -> None:
        if depth > 10:
            raise ValueError(f"DERIVED has a cycle through {f}")
        if f in derived:
            for g in derived[f][1]:
                walk(g, depth + 1)
        elif f not in seen:
            seen.add(f)
            out.append(f)

    for f in files:
        walk(norm(f))
    return out


def intermediates(files: list[str], derived: dict | None = None) -> list[str]:
    """The derived files among `files` (and among their inputs), in first-seen order."""
    derived = DERIVED if derived is None else derived
    out = []

    def walk(f: str) -> None:
        if f in derived:
            if f not in out:
                out.append(f)
            for g in derived[f][1]:
                walk(g)

    for f in files:
        walk(norm(f))
    return out


def problems(manifest: dict[str, dict] | None = None, figures: dict | None = None, derived: dict | None = None,
             labels: dict | None = None) -> list[str]:
    """Everything that would make a source line wrong: a file that is neither in the manifest nor derived, a manifest file
    without a Slovenian label, a figure with no files. An empty list means every source line is complete."""
    manifest = load_manifest() if manifest is None else manifest
    figures = FIGURE_SOURCES if figures is None else figures
    derived = DERIVED if derived is None else derived
    labels = SOURCE_LABELS if labels is None else labels
    out = []
    for name, files in figures.items():
        if not files:
            out.append(f"{name}: no data files listed")
        for f in originals(files, derived):
            if f not in manifest:
                out.append(f"{name}: {f} is not in data/manifest.json (and not a derived file in DERIVED)")
            elif f not in labels:
                out.append(f"{name}: {f} has no entry in SOURCE_LABELS")
    for f, (_, inputs) in derived.items():
        if f in manifest:
            out.append(f"{f} is both in the manifest and in DERIVED")
        if not inputs:
            out.append(f"{f}: DERIVED lists no inputs")
    return out


def sources_markdown(name: str, figures: dict | None = None, derived: dict | None = None, labels: dict | None = None) -> str:
    """One Markdown paragraph for under a figure: original sources with their exact files, then the derived files it reads.
    Raises KeyError for a figure that is not in FIGURE_SOURCES (so a new graph cannot be shown without its sources)."""
    figures = FIGURE_SOURCES if figures is None else figures
    derived = DERIVED if derived is None else derived
    labels = SOURCE_LABELS if labels is None else labels
    if name not in figures:
        raise KeyError(f"figure '{name}' has no entry in analysis/data_sources.py FIGURE_SOURCES")
    groups: dict[str, list[str]] = {}
    for f in originals(figures[name], derived):
        groups.setdefault(labels.get(f, f), []).append(f)
    parts = [f"{label}: {', '.join(f'`{f}`' for f in files)}" for label, files in groups.items()]
    text = "**Viri podatkov:** " + "; ".join(parts) + "."
    mids = intermediates(figures[name], derived)
    if mids:
        text += " Graf bere obdelane datoteke " if len(mids) > 1 else " Graf bere obdelano datoteko "
        text += ", ".join(f"`{f}` (izdela jo `{derived[f][0]}`)" for f in mids) + "."
    return text


def main() -> None:
    issues = problems()
    for name in FIGURE_SOURCES:
        print(f"{name}\n  {sources_markdown(name)}\n")
    print("OK: every figure has complete sources" if not issues else "PROBLEMS:\n  " + "\n  ".join(issues))
    raise SystemExit(1 if issues else 0)


if __name__ == "__main__":
    main()
