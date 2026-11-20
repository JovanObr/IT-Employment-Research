"""Stream A's figures for the presentation website (web/CONTRACT.md). Needs the local data; writes web/figures/a/<name>.json.

    python -m analysis.web_figures_a
"""
from __future__ import annotations

import logging
from pathlib import Path

import plotly.graph_objects as go

log = logging.getLogger("covid_it_data")
OUT = Path(__file__).resolve().parent.parent / "web" / "figures" / "a"


def build_web_figures() -> dict[str, go.Figure]:
    """Every Stream A figure used on the site, by name. Phase 0: two figures reused from notebook 08 to prove the pipeline;
    chapters 1-4 and 7 get web versions with conclusion-first titles in phase 2."""
    from analysis import causes as cs
    from analysis import viz
    d = cs.load_inputs()
    ev = d["events"]
    return {"1_ljudje": viz.fig_people_quarterly(cs.quarterly_layoffs(ev)),
            "2_datumi": viz.fig_event_windows(cs.weekly_layoffs(ev), people=cs.weekly_people(ev))}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fig in build_web_figures().items():
        (OUT / f"{name}.json").write_text(fig.to_json(), encoding="utf-8")
        log.info("wrote %s", OUT / f"{name}.json")


if __name__ == "__main__":
    main()
