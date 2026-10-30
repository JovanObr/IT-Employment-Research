"""Milestone figures, chapters 1-3 (and the data they need): Slovenian, interactive (plotly), casual audience.

Every figure function is pure: DataFrame/Series in, plotly Figure out, inputs untouched, no file reads. Numbers shown in
titles, labels and hover text are computed from the data passed in. `prepare_story_data()` runs the existing analyses
(analysis.causes, analysis.company_models) once and returns everything the figures need; it reads local files, so it
only works where the data exists. `python -m analysis.viz preview` writes every figure as an HTML file to reports/figures_sl/.

Chapter 1  fig_timeline, fig_layoff_calendar            (several series on one axis; heatmap)
Chapter 2  fig_event_windows, fig_leadlag_heatmap, fig_overbuild_quartiles   (small multiples; heatmap)
Chapter 3  fig_size_deciles, fig_model_comparison, fig_size_group_lift
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis import causes as cs
from analysis import company_models as cm
from analysis.viz_theme import (DIVERGING, EVENTS, HOVER_DATE, PALETTE, add_event_lines, base_layout, save_html, sl_num,
                                sl_pct)

log = logging.getLogger("covid_it_data")

MACRO_LABELS = {"fedfunds_chg12": "sprememba obrestne mere Fed (12 mes.)", "nasdaq_chg12": "sprememba borze NASDAQ (12 mes.)"}
MEASURE_LABELS = {"tracker events (3-month sum)": "število napovedi odpuščanj",
                  "tracker people laid off (3-month sum, log)": "število odpuščenih ljudi",
                  "JOLTS information layoff rate (%)": "uradna stopnja odpuščanj v informacijskem sektorju (JOLTS)"}
MODEL_LABELS = {"logit_size": "logistična regresija", "gb_size": "odločitveno drevo", "logit_nosize": "logistična, brez velikosti",
                "gb_nosize": "drevo, brez velikosti"}
MEASURE_QUARTILES = {"boom_growth": "rast prihodkov 2019-2021", "cost_growth": "rast stroškov 2019-2021",
                     "overbuild": "stroški rastejo hitreje od prihodkov"}


# ---------------------------------------------------------------------------------------- chapter 1
def _scaled(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) * 100 if hi > lo else s * 0


def fig_timeline(weekly: pd.Series, macro: pd.DataFrame, flags: pd.DataFrame | None = None,
                 start: str = "2020-03-01") -> go.Figure:
    """Layoff announcements, Fed rate, NASDAQ and (if given) the Hacker News remote and AI shares on ONE axis.
    Each line is rescaled to 0-100 over the period shown; hover shows the real value."""
    t0 = pd.Timestamp(start)
    series = [("napovedi odpuščanj na teden (4-tedensko povprečje)", weekly.rolling(4).mean(), "", PALETTE["red"], 1),
              ("obrestna mera Fed", macro["fedfunds"], " %", PALETTE["orange"], 1),
              ("borza NASDAQ", macro["nasdaq"], "", PALETTE["green"], 0)]
    if flags is not None and len(flags):
        f = flags.assign(month=pd.to_datetime(flags["month"]))
        for flag, name, col in (("remote", "objave z delom na daljavo", PALETTE["blue"]),
                                ("ai_ml", "objave z umetno inteligenco", PALETTE["purple"])):
            sub = f[f["flag"] == flag].set_index("month")["share"] * 100
            if len(sub):
                series.append((name, sub, " %", col, 1))
    fig = go.Figure()
    for name, s, unit, col, digits in series:
        s = s[s.index >= t0].dropna()
        if s.empty:
            continue
        fig.add_trace(go.Scatter(x=s.index, y=_scaled(s), name=name, mode="lines", line=dict(color=col, width=2),
                                 customdata=[f"{sl_num(v, digits)}{unit}" for v in s],
                                 hovertemplate="%{customdata}<extra>" + name + "</extra>"))
    fig.update_layout(**base_layout("Odpuščanja, obrestne mere, borza in iskani delavci: vse na isti osi", height=520))
    fig.update_layout(hovermode="x unified", yaxis=dict(title="indeks (0 = najnižja, 100 = najvišja vrednost v obdobju)"),
                      xaxis=dict(rangeslider=dict(visible=True, thickness=0.06), tickformat="%Y", hoverformat=HOVER_DATE))
    add_event_lines(fig, keys=("fed", "chatgpt"))
    return fig


def fig_layoff_calendar(weekly: pd.Series) -> go.Figure:
    """Heatmap: one row per year, one column per week of the year, colour = announcements that week."""
    iso = weekly.index.isocalendar()
    d = pd.DataFrame({"leto": iso["year"].to_numpy(), "teden": iso["week"].to_numpy(), "n": weekly.to_numpy()})
    z = d.pivot_table(index="leto", columns="teden", values="n", aggfunc="sum")
    fig = go.Figure(go.Heatmap(
        z=z.to_numpy(), x=z.columns, y=z.index.astype(str), colorscale="YlOrRd", xgap=1, ygap=1,
        colorbar=dict(title="napovedi<br>na teden"), hoverongaps=False,
        hovertemplate="leto %{y}, teden %{x}: %{z} napovedi<extra></extra>"))
    fig.update_layout(**base_layout("Koledar odpuščanj: kdaj so podjetja napovedovala odpuščanja", height=330))
    fig.update_layout(xaxis=dict(title="teden v letu", dtick=4), yaxis=dict(autorange="reversed"))
    return fig


# ---------------------------------------------------------------------------------------- chapter 2
def fig_event_windows(weekly: pd.Series, keys=("fed", "chatgpt"), before: int = 26, after: int = 26) -> go.Figure:
    """One panel per dated moment, shared y axis: weekly announcements before (grey) and after (blue) with the two averages."""
    studies = {k: cs.event_study(weekly, EVENTS[k][0], before, after) for k in keys}
    fig = make_subplots(rows=1, cols=len(keys), shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=[EVENTS[k][1][0].upper() + EVENTS[k][1][1:] for k in keys])
    for j, k in enumerate(keys, 1):
        date, st = EVENTS[k][0], studies[k]
        w = weekly[(weekly.index >= date - pd.Timedelta(weeks=before + 1)) & (weekly.index < date + pd.Timedelta(weeks=after))]
        is_after = w.index >= date.normalize() - pd.Timedelta(days=date.weekday())
        fig.add_trace(go.Bar(x=w.index, y=w, marker_color=np.where(is_after, PALETTE["blue"], PALETTE["light_grey"]),
                             showlegend=False, hovertemplate="%{x|" + HOVER_DATE + "}: %{y} napovedi<extra></extra>"), row=1, col=j)
        for lvl, x0, x1, lab in ((st["before_mean"], w.index.min(), date, "pred"), (st["after_mean"], date, w.index.max(), "po")):
            fig.add_shape(type="line", xref=f"x{j}", yref=f"y{j}" if j > 1 else "y", x0=x0, x1=x1, y0=lvl, y1=lvl,
                          line=dict(color=PALETTE["ink"], width=2))
        fig.add_annotation(xref="x domain" if j == 1 else f"x{j} domain", yref="paper", x=0.02, y=0.98, showarrow=False, xanchor="left", yanchor="top",
                           align="left", text=f"povprečno na teden:<br>pred {sl_num(st['before_mean'])} → po {sl_num(st['after_mean'])}")
        add_event_lines(fig, keys=(k,), xref=f"x{j}" if j > 1 else "x")
    fig.update_layout(**base_layout("Se je kaj spremenilo ob dveh znanih datumih?", height=420))
    fig.update_yaxes(title_text="napovedi odpuščanj na teden", row=1, col=1)
    return fig


def fig_leadlag_heatmap(tests: dict) -> go.Figure:
    """Rows = pairs (macro series, layoff measure), columns = lag in months, colour = correlation. A star marks the
    strongest lag. Positive lag = the macro series comes first."""
    rows, labels, stars = [], [], []
    for (x, y), r in tests.items():
        t = r["table"]
        rows.append(t["corr"].to_numpy())
        labels.append(f"{MACRO_LABELS.get(x, x)} → {MEASURE_LABELS.get(y, y)} (p = {sl_num(r['p_value'], 2)})")
        stars.append(r["best_lag"])
    lags = tests[next(iter(tests))]["table"]["lag_months"].to_numpy()
    fig = go.Figure(go.Heatmap(z=np.array(rows), x=lags, y=labels, colorscale=DIVERGING, zmid=0, zmin=-1, zmax=1, xgap=1, ygap=1,
                               colorbar=dict(title="korelacija"),
                               hovertemplate="zamik %{x} mes.: korelacija %{z:.2f}<extra>%{y}</extra>"))
    fig.add_trace(go.Scatter(x=stars, y=labels, mode="markers", marker=dict(symbol="star", size=12, color=PALETTE["ink"]),
                             showlegend=False, hoverinfo="skip"))
    fig.update_layout(**base_layout("Ali makro podatki prehitevajo odpuščanja? Korelacija po zamikih", height=140 + 60 * len(rows)))
    fig.update_layout(xaxis=dict(title="zamik v mesecih (pozitivno = makro podatek je prej)", dtick=2),
                      yaxis=dict(autorange="reversed", automargin=True), margin=dict(l=380))
    return fig


def fig_overbuild_quartiles(quartiles: dict[str, pd.DataFrame]) -> go.Figure:
    """Small multiples, shared y axis: share of companies with a layoff in 2022-2023 by quartile of each growth measure."""
    keys = [k for k in MEASURE_QUARTILES if k in quartiles]
    fig = make_subplots(rows=1, cols=len(keys), shared_yaxes=True, horizontal_spacing=0.05,
                        subplot_titles=[MEASURE_QUARTILES[k] for k in keys])
    names = ["1 (najnižja)", "2", "3", "4 (najvišja)"]
    for j, k in enumerate(keys, 1):
        q = quartiles[k]
        fig.add_trace(go.Bar(x=names[:len(q)], y=100 * q["rate"], marker_color=PALETTE["blue"], showlegend=False,
                             customdata=np.c_[q["companies"], q["laid_off"]],
                             hovertemplate="%{customdata[1]} od %{customdata[0]} podjetij<br>delež: %{y:.0f} %<extra></extra>",
                             text=[sl_pct(r) for r in q["rate"]], textposition="outside"), row=1, col=j)
    fig.update_layout(**base_layout("Kdo je kasneje odpuščal? Podjetja po hitrosti rasti v letih 2019-2021", height=430))
    fig.update_yaxes(title_text="delež podjetij z odpuščanji 2022-2023 (%)", row=1, col=1)
    return fig


# ---------------------------------------------------------------------------------------- chapter 3
def fig_size_deciles(panel: pd.DataFrame, n: int = 10) -> go.Figure:
    """Share of company-quarters followed by a layoff announcement, by size group (log assets)."""
    d = panel.dropna(subset=["log_assets"]).copy()
    d["skupina"] = pd.qcut(d["log_assets"], n, labels=False, duplicates="drop") + 1
    g = d.groupby("skupina").agg(vrstic=("y_next2q", "size"), pozitivnih=("y_next2q", "sum"), delez=("y_next2q", "mean"))
    fig = go.Figure(go.Bar(x=g.index, y=100 * g["delez"], marker_color=PALETTE["blue"],
                           customdata=np.c_[g["vrstic"], g["pozitivnih"]],
                           hovertemplate="velikostna skupina %{x}<br>%{customdata[1]} od %{customdata[0]} četrtletij: %{y:.1f} %<extra></extra>"))
    fig.update_layout(**base_layout("Večje kot je podjetje, pogosteje se znajde na seznamu odpuščanj", height=420))
    fig.update_layout(xaxis=dict(title="velikost podjetja (1 = najmanjših desetina, 10 = največjih desetina)", dtick=1),
                      yaxis=dict(title="delež četrtletij z napovedjo odpuščanj v naslednjih 2 četrtletjih (%)"))
    return fig


def model_comparison_table(sc: dict) -> pd.DataFrame:
    """PR-AUC rows for the figure from analysis.company_models.run_size_control(): baseline, size alone, four models."""
    o = sc["overall"].set_index("model")
    size_only = sc["with_size"]["baselines"].set_index("feature").loc["log_assets", "pr_auc"]
    rows = [("naključno (osnovna stopnja)", o.loc["constant (train base rate)", "pr_auc"], np.nan, np.nan),
            ("samo velikost podjetja", size_only, np.nan, np.nan)]
    for k, lab in MODEL_LABELS.items():
        rows.append((lab, o.loc[k, "pr_auc"], o.loc[k, "ci_lo"], o.loc[k, "ci_hi"]))
    return pd.DataFrame(rows, columns=["label", "pr_auc", "ci_lo", "ci_hi"])


def fig_model_comparison(table: pd.DataFrame) -> go.Figure:
    """Horizontal bars of PR-AUC with 95 % intervals; dashed line = the base rate (the first row)."""
    t = table.reset_index(drop=True)
    err_hi = (t["ci_hi"] - t["pr_auc"]).fillna(0)
    err_lo = (t["pr_auc"] - t["ci_lo"]).fillna(0)
    colors = [PALETTE["grey"], PALETTE["grey"], PALETTE["orange"], PALETTE["orange"], PALETTE["blue"], PALETTE["blue"]][:len(t)]
    fig = go.Figure(go.Bar(y=t["label"], x=t["pr_auc"], orientation="h", marker_color=colors,
                           error_x=dict(type="data", symmetric=False, array=err_hi, arrayminus=err_lo),
                           customdata=[sl_num(v, 3) for v in t["pr_auc"]],
                           hovertemplate="%{y}: %{customdata}<extra></extra>"))
    fig.add_vline(x=float(t["pr_auc"].iloc[0]), line=dict(color=PALETTE["ink"], dash="dash", width=1))
    fig.update_layout(**base_layout("Kako dobro napovemo, katera podjetja bodo napovedala odpuščanja?", height=420))
    fig.update_layout(xaxis=dict(title="kakovost razvrščanja (PR-AUC; višje je bolje; črtkano = osnovna stopnja)"),
                      yaxis=dict(autorange="reversed", automargin=True))
    return fig


def fig_size_group_lift(stratified: pd.DataFrame) -> go.Figure:
    """Grouped bars: how many times better than chance (lift) each model is inside the size groups that have enough positives."""
    d = stratified.dropna(subset=["lift"])
    names = {1: "najmanjša tretjina", 2: "srednja tretjina", 3: "največja tretjina"}
    fig = go.Figure()
    for k, lab in MODEL_LABELS.items():
        s = d[d["model"] == k]
        if s.empty:
            continue
        fig.add_trace(go.Bar(x=[names[g] for g in s["size_group"]], y=s["lift"], name=lab,
                             marker_color=PALETTE["orange"] if k.endswith("_size") else PALETTE["blue"],
                             marker_opacity=1.0 if k.startswith("logit") else 0.6,
                             hovertemplate="%{x}: %{y:.1f}-krat boljše od naključja<extra>" + lab + "</extra>"))
    fig.add_hline(y=1, line=dict(color=PALETTE["ink"], dash="dash", width=1))
    fig.update_layout(**base_layout("Ko držimo velikost približno enako, napoved skoraj izgine", height=430), barmode="group")
    fig.update_layout(yaxis=dict(title="kolikokrat boljše od naključja"))
    return fig


# ---------------------------------------------------------------------------------------- data and preview
def prepare_story_data(flags_path=None, n_boot: int = 300) -> dict:
    """Run the existing analyses once and return the inputs of the chapter 1-3 figures (reads local files)."""
    from collectors.common import PROCESSED
    d = cs.load_inputs()
    h1 = cs.run_h1(d["events"], d["fred"], d["jolts"])
    panel = pd.read_csv(PROCESSED / "company_panel.csv", dtype={"sic": str, "sic2": str})
    flags = None
    fp = flags_path or PROCESSED / "hn_flags_monthly.csv"
    if fp.exists():
        flags = pd.read_csv(fp)
    return {"weekly": cs.weekly_layoffs(d["events"]), "macro": h1["macro"], "tests": h1["tests"], "flags": flags,
            "quartiles": cs.run_h3(d["fin"], d["revenue"], d["universe"], d["matches"], d["events"])["quartiles"],
            "panel": panel, "size_control": cm.run_size_control(panel, embargo=True, n_boot=n_boot)}


def build_figures(story: dict) -> dict[str, go.Figure]:
    sc = story["size_control"]
    return {"1_casovnica": fig_timeline(story["weekly"], story["macro"], story["flags"]),
            "1_koledar": fig_layoff_calendar(story["weekly"]),
            "2_datumi": fig_event_windows(story["weekly"]),
            "2_zamiki": fig_leadlag_heatmap(story["tests"]),
            "2_rast": fig_overbuild_quartiles(story["quartiles"]),
            "3_velikost": fig_size_deciles(story["panel"]),
            "3_modeli": fig_model_comparison(model_comparison_table(sc)),
            "3_skupine": fig_size_group_lift(sc["stratified"])}


def main() -> None:
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if sys.argv[1:] != ["preview"]:
        raise SystemExit("usage: python -m analysis.viz preview")
    for name, fig in build_figures(prepare_story_data()).items():
        log.info("wrote %s", save_html(fig, f"preview_{name}"))


if __name__ == "__main__":
    main()
