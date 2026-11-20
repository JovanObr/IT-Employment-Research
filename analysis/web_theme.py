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
    right = max(24, int(f.layout.margin.r or 0)) if f.layout.margin else 24     # keep room reserved by direct_labels
    f.update_layout(
        font=dict(family=FONT, size=BASE_SIZE, color=PALETTE["ink"]),
        title=dict(text=title, x=0, xanchor="left", font=dict(size=BASE_SIZE + 5)) if title else None,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        autosize=True, width=None, height=None,
        margin=dict(l=64, r=right, t=96 if title else 24, b=72),
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


# ---------------------------------------------------------------------------------------- helpers for figure builders
# Colour roles (web/CONTRACT.md, "Theme"): one meaning per colour across the whole site.
ROLE = {"main": PALETTE["blue"],        # our data, the series the screen is about
        "contrast": PALETTE["orange"],  # the one series it is compared with (blue vs orange is safe for colour-blind viewers)
        "loss": PALETTE["red"],         # layoffs, declines; never paired with green as the only difference
        "context": PALETTE["grey"],     # everything else: comparison, background
        "muted": PALETTE["light_grey"]}


def title(fig: go.Figure, conclusion: str, subtitle: str | None = None) -> go.Figure:
    """Conclusion-first title ("Odpuščanja so se začela po zvišanju obrestne mere") with an optional small grey line saying what is shown."""
    text = conclusion if not subtitle else (f"{conclusion}<br><span style='font-size:0.72em;color:{PALETTE['grey']}'>{subtitle}</span>")
    fig.update_layout(title=dict(text=text, x=0, xanchor="left"))
    return fig


def direct_labels(fig: go.Figure, fmt=None) -> go.Figure:
    """Name each line at its last point, in its own colour, and hide the legend: the reader does not have to look things up."""
    for tr in fig.data:
        if tr.type != "scatter" or tr.x is None or not len(tr.x) or not tr.name:
            continue
        ys = [(x, y) for x, y in zip(tr.x, tr.y) if y is not None]
        if not ys:
            continue
        x, y = ys[-1]
        color = (tr.line.color if tr.line and tr.line.color else None) or (tr.marker.color if tr.marker and isinstance(tr.marker.color, str) else None)
        label = tr.name if fmt is None else fmt(tr.name, y)
        fig.add_annotation(x=x, y=y, xref=tr.xaxis or "x", yref=tr.yaxis or "y", text=f"<b>{label}</b>", showarrow=False,
                           xanchor="left", xshift=8, font=dict(color=color or PALETTE["ink"]))
    fig.update_layout(showlegend=False, margin=dict(r=170))
    return fig


def highlight(fig: go.Figure, keep: str | list[str], color: str | None = None) -> go.Figure:
    """Keep the named trace(s) in colour and grey out all others: one message per chart."""
    keep = [keep] if isinstance(keep, str) else keep
    for tr in fig.data:
        if tr.name in keep:
            if color and hasattr(tr, "line") and tr.line is not None:
                tr.line.color = color
            continue
        if hasattr(tr, "line") and tr.line is not None:
            tr.line.color = ROLE["muted"]
        if hasattr(tr, "marker") and tr.marker is not None:
            tr.marker.color = ROLE["muted"]
        tr.hoverinfo = "skip"
    return fig


def callout(fig: go.Figure, x, y, text: str, ax: int = -60, ay: int = -50, xref: str = "x", yref: str = "y") -> go.Figure:
    """A short note with an arrow pointing at one point of the chart (the place the speaker talks about)."""
    fig.add_annotation(x=x, y=y, xref=xref, yref=yref, text=text, showarrow=True, arrowhead=2, arrowwidth=1.5, arrowcolor=PALETTE["ink"],
                       ax=ax, ay=ay, bgcolor="rgba(255,255,255,0.9)", bordercolor=PALETTE["light_grey"], borderpad=4,
                       font=dict(color=PALETTE["ink"]), align="left")
    return fig
