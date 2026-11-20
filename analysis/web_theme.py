"""Web theme for the presentation website: one place that decides how every chart looks on the site.

The build calls `apply` on every figure, so chapter text and figure code never carry web styling. Changing the look of the whole
site means changing this file and `web/assets/theme.css` only (see web/CONTRACT.md).
"""
from __future__ import annotations

import plotly.graph_objects as go

from analysis.viz_theme import PALETTE, TOPIC_COLORS

FONT = "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
BASE_SIZE = 17
# Charts take their height from the page (web/assets/theme.css: about 60 % of the window), so a screen always fits on a projector.
# Plotly options for every chart on the site: fits its box, no toolbar (the audience does not need it), no plotly logo.
CONFIG = {"responsive": True, "displayModeBar": False, "displaylogo": False, "scrollZoom": False}


def apply(fig: go.Figure | dict) -> go.Figure:
    """Return a copy of the figure in the web style: larger text, transparent background, title on the left, legend below."""
    f = go.Figure(fig)
    title = f.layout.title.text if f.layout.title and f.layout.title.text else None
    f.update_layout(
        font=dict(family=FONT, size=BASE_SIZE, color=PALETTE["ink"]),
        title=dict(text=title, x=0, xanchor="left", font=dict(size=BASE_SIZE + 5)) if title else None,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        autosize=True, width=None, height=None,
        margin=dict(l=64, r=24, t=84 if title else 24, b=72),
        hoverlabel=dict(font=dict(family=FONT, size=BASE_SIZE - 1), namelength=-1),
        legend=dict(orientation="h", yanchor="top", y=-0.14, x=0, font=dict(size=BASE_SIZE - 2)),
        separators=",.",
    )
    if not f.layout.colorway:
        f.update_layout(colorway=TOPIC_COLORS)
    f.update_xaxes(gridcolor=PALETTE["light_grey"], zerolinecolor=PALETTE["grey"], title_font=dict(size=BASE_SIZE - 1))
    f.update_yaxes(gridcolor=PALETTE["light_grey"], zerolinecolor=PALETTE["grey"], title_font=dict(size=BASE_SIZE - 1))
    f.update_annotations(font_size=BASE_SIZE - 3)
    return f
