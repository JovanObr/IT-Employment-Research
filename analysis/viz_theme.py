"""Shared look for the milestone figures (notebook 08, Slovenian, casual audience).

Everyone who draws a figure for the milestone imports from here, so that all chapters look like one piece:

    from analysis.viz_theme import PALETTE, TOPIC_COLORS, DIVERGING, base_layout, add_event_lines, save_html

Changes to this file go through the Requests section of docs/STATUS.md (owner: Stream A).
Conventions: plotly figures, white background, Slovenian text, decimal comma (separators=",."), dates written
dd.mm.yyyy or mm/yyyy (plotly cannot print Slovenian month names without extra files).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIGURES_SL = ROOT / "reports" / "figures_sl"

PALETTE = {
    "blue": "#4C78A8", "orange": "#F58518", "red": "#E45756", "green": "#54A24B", "grey": "#9A9A9A",
    "light_grey": "#E5E5E5", "ink": "#222222", "teal": "#72B7B2", "purple": "#B279A2",
}
# Ten distinguishable colours (Tableau 10), one per Hacker News topic
TOPIC_COLORS = ["#4C78A8", "#F58518", "#E45756", "#72B7B2", "#54A24B", "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC"]
# Growth maps: red = decline, white = no change, blue = growth (the same convention as notebook 06)
DIVERGING = [[0.0, "#B2182B"], [0.5, "#F7F7F7"], [1.0, "#2166AC"]]

DATE_TICK = "%Y"             # axis ticks
HOVER_DATE = "%d.%m.%Y"      # hover text for dates
HOVER_MONTH = "%m/%Y"        # hover text for monthly data

# The dated moments used throughout the story: key -> (date, Slovenian label)
EVENTS = {
    "covid": (pd.Timestamp("2020-03-11"), "začetek pandemije"),
    "fed": (pd.Timestamp("2022-03-16"), "prvo zvišanje obrestne mere (Fed)"),
    "chatgpt": (pd.Timestamp("2022-11-30"), "ChatGPT"),
}


def base_layout(title: str | None = None, height: int = 480, **extra) -> dict:
    """Keyword arguments for `fig.update_layout(**base_layout("Naslov"))`. No fixed width: the figure fills its cell."""
    layout = dict(
        template="plotly_white",
        title=dict(text=title, x=0, xanchor="left") if title else None,
        height=height,
        font=dict(family="Arial, Helvetica, sans-serif", size=13, color=PALETTE["ink"]),
        margin=dict(l=60, r=30, t=70 if title else 30, b=60),
        separators=",.",                                   # decimal comma, thousands dot
        colorway=TOPIC_COLORS,
        hoverlabel=dict(namelength=-1),
        legend=dict(orientation="h", yanchor="top", y=-0.15, x=0),
    )
    layout.update(extra)
    return layout


def add_event_lines(fig, keys=("fed", "chatgpt"), xref: str = "x", label_size: int = 11):
    """Dashed vertical lines with a rotated label for the dated moments. Uses shapes and annotations (not
    `add_vline`, which fails on date axes in several plotly versions). `xref` is "x", "x2", ... for subplots."""
    for k in keys:
        date, label = EVENTS[k]
        x = date.strftime("%Y-%m-%d")
        fig.add_shape(type="line", xref=xref, yref="paper", x0=x, x1=x, y0=0, y1=1,
                      line=dict(color=PALETTE["ink"], width=1, dash="dash"))
        fig.add_annotation(xref=xref, yref="paper", x=x, y=1, text=label, showarrow=False, textangle=-90,
                           xanchor="right", yanchor="top", font=dict(size=label_size, color=PALETTE["ink"]))
    return fig


def save_html(fig, name: str, outdir: Path | None = None) -> Path:
    """Write one figure as a small standalone HTML file (plotly.js from the CDN, so it needs internet to open)."""
    outdir = Path(outdir) if outdir else FIGURES_SL
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{name}.html"
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)
    return path


def sl_num(x: float, digits: int = 1) -> str:
    """Number as Slovenian text: decimal comma, thousands dot (15.4 -> '15,4', 12345.6 -> '12.345,6')."""
    return f"{x:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sl_pct(share: float, digits: int = 0) -> str:
    """A share between 0 and 1 as Slovenian percent text (0.154 -> '15 %')."""
    return f"{sl_num(100 * share, digits)} %"
