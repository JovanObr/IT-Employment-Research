"""Milestone figures, chapters 1-3 (and the data they need): Slovenian, interactive (plotly), casual audience.

Every figure function is pure: DataFrame/Series in, plotly Figure out, inputs untouched, no file reads. Numbers shown in
titles, labels and hover text are computed from the data passed in. `prepare_story_data()` runs the existing analyses
(analysis.causes, analysis.company_models) once and returns everything the figures need; it reads local files, so it
only works where the data exists. `python -m analysis.viz preview` writes every figure as an HTML file to reports/figures_sl/.

Chapter 1  fig_timeline, fig_layoff_calendar, fig_people_quarterly, fig_top_announcements   (several series on one axis; heatmap; people and share of staff)
Chapter 2  fig_event_windows, fig_leadlag_heatmap, fig_overbuild_quartiles   (small multiples; heatmap)
Chapter 3  fig_size_deciles, fig_company_scatter, fig_model_comparison, fig_size_group_lift
Chapter 6  fig_car_path, fig_car_distribution, fig_car_groups   (only when prices exist: story['stock'])
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
                 start: str = "2020-03-01", people: pd.Series | None = None) -> go.Figure:
    """Layoff announcements (or people laid off, via the dropdown), Fed rate, NASDAQ and (if given) the Hacker News remote and AI shares on
    ONE axis. Each line is rescaled to 0-100 over the period shown; hover shows the real value."""
    t0 = pd.Timestamp(start)
    series = [("napovedi odpuščanj na teden (4-tedensko povprečje)", weekly.rolling(4).mean(), "", PALETTE["red"], 1)]
    if people is not None:
        series.append(("odpuščeni ljudje na teden (4-tedensko povprečje)", people.rolling(4).mean(), " ljudi", PALETTE["red"], 0))
    series += [("obrestna mera Fed", macro["fedfunds"], " %", PALETTE["orange"], 1), ("borza NASDAQ", macro["nasdaq"], "", PALETTE["green"], 0)]
    if flags is not None and len(flags):
        f = flags.assign(month=pd.to_datetime(flags["month"]))
        for flag, name, col in (("remote", "objave z delom na daljavo", PALETTE["blue"]),
                                ("ai_ml", "objave z umetno inteligenco", PALETTE["purple"])):
            sub = f[f["flag"] == flag].set_index("month")["share"] * 100
            if len(sub):
                series.append((name, sub, " %", col, 1))
    fig = go.Figure()
    for name, s_, unit, col, digits in series:
        s_ = s_[s_.index >= t0].dropna()
        if s_.empty:
            continue
        fig.add_trace(go.Scatter(x=s_.index, y=_scaled(s_), name=name, mode="lines", line=dict(color=col, width=2),
                                 customdata=[f"{sl_num(v, digits)}{unit}" for v in s_],
                                 hovertemplate="%{customdata}<extra>" + name + "</extra>"))
    fig.update_layout(**base_layout("Odpuščanja, obrestne mere, borza in iskani delavci: vse na isti osi", height=540))
    fig.update_layout(hovermode="x unified", yaxis=dict(title="indeks (0 = najnižja, 100 = najvišja vrednost v obdobju)"),
                      xaxis=dict(rangeslider=dict(visible=True, thickness=0.06), tickformat="%Y", hoverformat=HOVER_DATE))
    is_people = [t.name.startswith("odpuščeni ljudje") for t in fig.data]
    is_events = [t.name.startswith("napovedi") for t in fig.data]
    if any(is_people):
        for t, hide in zip(fig.data, is_people):
            t.visible = not hide
        fig.update_layout(margin=dict(t=110), updatemenus=[dict(
            type="dropdown", direction="down", x=0, xanchor="left", y=1.13, yanchor="top", showactive=True,
            buttons=[dict(label="Merilo odpuščanj: število napovedi", method="update", args=[{"visible": [not p for p in is_people]}]),
                     dict(label="Merilo odpuščanj: število odpuščenih ljudi", method="update", args=[{"visible": [not e for e in is_events]}])])])
    add_event_lines(fig, keys=("fed", "chatgpt"))
    return fig


def _calendar_z(weekly: pd.Series) -> pd.DataFrame:
    iso = weekly.index.isocalendar()
    d = pd.DataFrame({"leto": iso["year"].to_numpy(), "teden": iso["week"].to_numpy(), "n": weekly.to_numpy()})
    return d.pivot_table(index="leto", columns="teden", values="n", aggfunc="sum")


def fig_layoff_calendar(weekly: pd.Series, people: pd.Series | None = None) -> go.Figure:
    """Heatmap: one row per year, one column per week of the year, colour = announcements that week (or, via the dropdown, people laid off;
    that colour scale stops at the 95th percentile so one huge week does not wash out the rest, the hover shows the real number)."""
    z = _calendar_z(weekly)
    fig = go.Figure(go.Heatmap(
        z=z.to_numpy(), x=z.columns, y=z.index.astype(str), colorscale="YlOrRd", xgap=1, ygap=1,
        colorbar=dict(title="napovedi<br>na teden"), hoverongaps=False,
        hovertemplate="leto %{y}, teden %{x}: %{z} napovedi<extra></extra>"))
    fig.update_layout(**base_layout("Koledar odpuščanj: kdaj so podjetja napovedovala odpuščanja", height=350))
    fig.update_layout(xaxis=dict(title="teden v letu", dtick=4), yaxis=dict(autorange="reversed"))
    if people is not None:
        zp = _calendar_z(people)
        pos = zp.to_numpy()[zp.to_numpy() > 0]
        zmax = float(np.percentile(pos, 95)) if len(pos) else 1.0
        fig.add_trace(go.Heatmap(z=zp.to_numpy(), x=zp.columns, y=zp.index.astype(str), colorscale="YlOrRd", xgap=1, ygap=1, zmin=0, zmax=zmax,
                                 colorbar=dict(title="odpuščeni<br>ljudje na teden"), hoverongaps=False, visible=False,
                                 hovertemplate="leto %{y}, teden %{x}: %{z:,.0f} ljudi<extra></extra>"))
        fig.update_layout(margin=dict(t=100), updatemenus=[dict(
            type="dropdown", direction="down", x=0, xanchor="left", y=1.25, yanchor="top", showactive=True,
            buttons=[dict(label="Število napovedi", method="update", args=[{"visible": [True, False]}]),
                     dict(label="Število odpuščenih ljudi", method="update", args=[{"visible": [False, True]}])])])
    return fig


def fig_people_quarterly(q: pd.DataFrame, min_share_n: int = 3) -> go.Figure:
    """Two panels sharing the quarters: people laid off per quarter (announcements with a known number; hover lists the biggest ones) and,
    below, the median share of the workforce per announcement (quarters with fewer than `min_share_n` known shares are left out)."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.62, 0.38])
    tops = ["<br>".join(f"{c}: {sl_num(n, 0)}" for c, n in t) for t in q["top"]]
    fig.add_trace(go.Bar(x=q["quarter"], y=q["people"], marker_color=PALETTE["red"], showlegend=False,
                         customdata=np.c_[q["events_with_people"], q["events"], tops],
                         hovertemplate="%{x}: %{y:,.0f} ljudi<br>število znano pri %{customdata[0]} od %{customdata[1]} napovedi<br>največje:<br>%{customdata[2]}<extra></extra>"),
                  row=1, col=1)
    m = q[q["n_share"] >= min_share_n]
    fig.add_trace(go.Scatter(x=m["quarter"], y=100 * m["median_share"], mode="lines+markers", line=dict(color=PALETTE["blue"], width=3),
                             showlegend=False, customdata=m["n_share"],
                             hovertemplate="%{x}: sredina %{y:.0f} % zaposlenih<br>delež znan pri %{customdata} napovedih<extra></extra>"), row=2, col=1)
    fig.update_layout(**base_layout("Koliko ljudi in kolikšen del zaposlenih so podjetja napovedala odpustiti", height=620))
    fig.update_yaxes(title_text="odpuščeni ljudje v četrtletju", row=1, col=1)
    fig.update_yaxes(title_text="sredina deleža zaposlenih (%)", rangemode="tozero", row=2, col=1)
    fig.update_xaxes(title_text="četrtletje", row=2, col=1)
    return fig


def fig_top_announcements(top: pd.DataFrame) -> go.Figure:
    """The biggest single announcements, as horizontal bars (people; hover adds the date and the share of the workforce when known)."""
    t = top.sort_values("people", ascending=False).reset_index(drop=True)
    labels = [f"{c} ({d.year})" for c, d in zip(t["company"], pd.to_datetime(t["date"]))]
    share = [sl_pct(x, 0) if pd.notna(x) else "ni podatka" for x in t["share"]]
    fig = go.Figure(go.Bar(y=labels, x=t["people"], orientation="h", marker_color=PALETTE["red"], text=[sl_num(v, 0) for v in t["people"]], textposition="outside",
                           customdata=np.c_[[pd.Timestamp(d).strftime("%d.%m.%Y") for d in t["date"]], share],
                           hovertemplate="%{y}<br>%{x:,.0f} ljudi<br>datum: %{customdata[0]}<br>delež zaposlenih: %{customdata[1]}<extra></extra>"))
    fig.update_layout(**base_layout(f"Največjih {len(t)} napovedi odpuščanj", height=140 + 38 * len(t)))
    fig.update_layout(xaxis=dict(title="napovedani odpuščeni ljudje"), yaxis=dict(autorange="reversed", automargin=True))
    return fig


# ---------------------------------------------------------------------------------------- chapter 2
def fig_event_windows(weekly: pd.Series, keys=("fed", "chatgpt"), before: int = 26, after: int = 26, people: pd.Series | None = None) -> go.Figure:
    """One column per dated moment, shared y axis per row: weekly announcements (top row) and, if given, people laid off (bottom row) before
    (grey) and after (blue) the date, with the two averages."""
    rows = [("napovedi", weekly, "napovedi odpuščanj na teden", 1)]
    if people is not None:
        rows.append(("ljudje", people, "odpuščeni ljudje na teden", 0))
    nc = len(keys)
    titles = [EVENTS[k][1][0].upper() + EVENTS[k][1][1:] for k in keys] + [""] * (nc * (len(rows) - 1))
    fig = make_subplots(rows=len(rows), cols=nc, shared_yaxes=True, horizontal_spacing=0.04, vertical_spacing=0.14, subplot_titles=titles)
    for r, (_, series, ylabel, digits) in enumerate(rows, 1):
        for j, k in enumerate(keys, 1):
            idx = (r - 1) * nc + j
            xa, ya = ("x", "y") if idx == 1 else (f"x{idx}", f"y{idx}")
            date, st = EVENTS[k][0], cs.event_study(series, EVENTS[k][0], before, after)
            w = series[(series.index >= date - pd.Timedelta(weeks=before + 1)) & (series.index < date + pd.Timedelta(weeks=after))]
            is_after = w.index >= date.normalize() - pd.Timedelta(days=date.weekday())
            fig.add_trace(go.Bar(x=w.index, y=w, marker_color=np.where(is_after, PALETTE["blue"], PALETTE["light_grey"]), showlegend=False,
                                 hovertemplate="%{x|" + HOVER_DATE + "}: %{y:,.0f} " + ("napovedi" if r == 1 else "ljudi") + "<extra></extra>"), row=r, col=j)
            for lvl, x0, x1 in ((st["before_mean"], w.index.min(), date), (st["after_mean"], date, w.index.max())):
                fig.add_shape(type="line", xref=xa, yref=ya, x0=x0, x1=x1, y0=lvl, y1=lvl, line=dict(color=PALETTE["ink"], width=2))
            fig.add_annotation(xref=f"{xa} domain", yref=f"{ya} domain", x=0.02, y=0.98, showarrow=False, xanchor="left", yanchor="top", align="left",
                               text=f"povprečno na teden:<br>pred {sl_num(st['before_mean'], digits)} → po {sl_num(st['after_mean'], digits)}")
        fig.update_yaxes(title_text=ylabel, row=r, col=1)
    for j, k in enumerate(keys, 1):
        add_event_lines(fig, keys=(k,), xref="x" if j == 1 else f"x{j}")
    fig.update_layout(**base_layout("Se je kaj spremenilo ob dveh znanih datumih?", height=420 if len(rows) == 1 else 720))
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


def fig_company_scatter(table: pd.DataFrame, ycap: float = 400.0) -> go.Figure:
    """One dot per tech company: size (assets at the end of 2019) against revenue growth 2019-2021; red = announced layoffs in 2022-2023."""
    d = table.dropna(subset=["boom_growth", "log_assets_start"]).copy()
    d["assets"] = np.exp(d["log_assets_start"])
    d["growth_pct"] = 100 * (np.exp(d["boom_growth"]) - 1)
    out = int((d["growth_pct"] > ycap).sum())
    fig = go.Figure()
    for flag, name, col, op in ((0, "brez odpuščanj 2022-2023", PALETTE["grey"], 0.45), (1, "napovedala odpuščanja 2022-2023", PALETTE["red"], 0.85)):
        s = d[d["y_layoff"] == flag]
        fig.add_trace(go.Scatter(x=s["assets"], y=s["growth_pct"], mode="markers", name=name, marker=dict(size=9, color=col, opacity=op),
                                 customdata=np.c_[s["name"].astype(str), s["assets"] / 1e6, s["growth_pct"]],
                                 hovertemplate="<b>%{customdata[0]}</b><br>sredstva: %{customdata[1]:,.0f} mio USD<br>rast prihodkov: %{customdata[2]:.0f} %<extra></extra>"))
    fig.add_vline(x=float(d["assets"].median()), line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.add_hline(y=float(d["growth_pct"].median()), line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.update_layout(**base_layout("Velika in hitro rastoča podjetja: kdo je napovedal odpuščanja?", height=560))
    fig.update_layout(xaxis=dict(title="velikost podjetja (sredstva konec 2019, lestvica se z vsako črto podeseteri)", type="log"),
                      yaxis=dict(title="rast prihodkov 2019 do 2021 (%)", range=[-60, ycap]))
    if out:
        fig.add_annotation(xref="paper", yref="paper", x=1, y=1, xanchor="right", yanchor="top", showarrow=False,
                           text=f"{out} podjetij z rastjo nad {sl_num(ycap, 0)} % je zunaj prikazanega območja")
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


# ---------------------------------------------------------------------------------------- chapter 6
def fig_car_path(path: pd.DataFrame) -> go.Figure:
    """Average cumulative abnormal return (counted from day -5) around the announcement, with its 95 % band."""
    p = path.sort_values("t")
    fig = go.Figure()
    fig.add_vrect(x0=-0.5, x1=1.5, fillcolor=PALETTE["light_grey"], opacity=0.6, line_width=0)
    fig.add_trace(go.Scatter(x=list(p["t"]) + list(p["t"])[::-1], y=list(p["hi_pct"]) + list(p["lo_pct"])[::-1], fill="toself",
                             fillcolor="rgba(76,120,168,0.20)", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=p["t"], y=p["mean_pct"], mode="lines+markers", line=dict(color=PALETTE["blue"], width=3), showlegend=False,
                             customdata=np.c_[p["lo_pct"], p["hi_pct"]],
                             hovertemplate="dan %{x}: %{y:.2f} %<br>negotovost od %{customdata[0]:.2f} % do %{customdata[1]:.2f} %<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.update_layout(**base_layout("Kaj naredi borza ob novici o odpuščanjih?", height=440))
    fig.update_layout(xaxis=dict(title="dnevi glede na objavo (0 = prvi trgovalni dan; sivo = dneva 0 in +1)", dtick=1),
                      yaxis=dict(title="povprečni nenavadni donos od dneva -5 (%)"))
    return fig


def fig_car_distribution(cars: pd.DataFrame, window: str = "ann_0_1", clip: float = 20.0) -> go.Figure:
    """How different single reactions are: histogram of the announcement-window abnormal return (per cent), extremes clipped."""
    v = 100 * cars[f"car_{window}"].dropna()
    out = int((v.abs() > clip).sum())
    fig = go.Figure(go.Histogram(x=v.clip(-clip, clip), nbinsx=41, marker_color=PALETTE["blue"],
                                 hovertemplate="%{x:.1f} %: %{y} objav<extra></extra>"))
    lines = [(v.mean(), "povprečje", PALETTE["red"]), (v.median(), "mediana", PALETTE["orange"])]
    left_first = sorted(lines, key=lambda t: t[0])                          # the smaller value is labelled to the left of its line
    for rank, (val, lab, col) in enumerate(left_first):
        fig.add_shape(type="line", xref="x", yref="paper", x0=val, x1=val, y0=0, y1=1, line=dict(color=col, width=2))
        fig.add_annotation(xref="x", yref="paper", x=val, y=1.0 - 0.07 * lines.index((val, lab, col)), showarrow=False,
                           xanchor="right" if rank == 0 else "left", xshift=-6 if rank == 0 else 6, yanchor="top",
                           text=f"{lab} {sl_num(val, 1)} %", font=dict(color=col, size=12), bgcolor="rgba(255,255,255,0.8)")
    fig.update_layout(**base_layout("Posamezne objave se zelo razlikujejo", height=420))
    fig.update_layout(xaxis=dict(title=f"nenavadni donos v dneh 0 in +1 (%; skrajnosti skrčene na ±{sl_num(clip, 0)} %)"),
                      yaxis=dict(title="število objav"), bargap=0.05)
    if out:
        fig.add_annotation(xref="paper", yref="paper", x=1, y=1, xanchor="right", yanchor="top", showarrow=False,
                           text=f"{out} objav je zunaj prikazanega območja")
    return fig


def fig_car_groups(by_size: pd.DataFrame, by_year: pd.DataFrame, min_n: int = 10) -> go.Figure:
    """Average abnormal return with 95 % intervals by company size (left) and by year (right); groups below `min_n` events are left out."""
    order = ["najmanjša tretjina", "srednja tretjina", "največja tretjina"]
    sz = by_size.assign(k=by_size["size_group"].astype(str)).set_index("k").reindex(order).dropna(subset=["n"])
    yr = by_year[by_year["n"] >= min_n].sort_values("year")
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.06, subplot_titles=["po velikosti podjetja", "po letu objave"])
    for j, (x, d) in enumerate(((sz.index.astype(str), sz), (yr["year"].astype(str), yr)), 1):
        up = (d["ci_hi_pct"] - d["mean_pct"]).fillna(0).to_numpy()
        dn = (d["mean_pct"] - d["ci_lo_pct"]).fillna(0).to_numpy()
        fig.add_trace(go.Scatter(x=list(x), y=d["mean_pct"], mode="markers", marker=dict(size=11, color=PALETTE["blue"]),
                                 error_y=dict(type="data", symmetric=False, array=up, arrayminus=dn), showlegend=False,
                                 customdata=d["n"], hovertemplate="%{x}: %{y:.2f} %<br>%{customdata} objav<extra></extra>"), row=1, col=j)
        fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"), row=1, col=j)
    fig.update_layout(**base_layout("Ali je odziv borze odvisen od velikosti podjetja ali leta?", height=430))
    fig.update_yaxes(title_text="povprečni nenavadni donos v dneh 0 in +1 (%)", row=1, col=1)
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
    h3 = cs.run_h3(d["fin"], d["revenue"], d["universe"], d["matches"], d["events"])
    people = {"people_weekly": cs.weekly_people(d["events"]), "quarterly": cs.quarterly_layoffs(d["events"]),
              "top": cs.top_announcements(d["events"]), "coverage": cs.people_coverage(d["events"])}
    return {**people, "weekly": cs.weekly_layoffs(d["events"]), "macro": h1["macro"], "tests": h1["tests"], "flags": flags, "stock": prepare_stock_data(),
            "quartiles": h3["quartiles"], "boom_table": h3["used"],
            "panel": panel, "size_control": cm.run_size_control(panel, embargo=True, n_boot=n_boot)}


def prepare_stock_data(n_boot: int = 1000) -> dict | None:
    """Chapter 6 inputs from the event study, or None if prices have not been downloaded (python collect.py --sources prices)."""
    from analysis import event_study as es
    from collectors.common import PROCESSED, RAW
    need = [PROCESSED / "layoffs_clean.csv", RAW / "sec_company_matches.csv", RAW / "prices_daily.csv", RAW / "sec_financials_quarterly.csv"]
    if not all(p.exists() for p in need):
        log.info("chapter 6 skipped: missing %s", [p.name for p in need if not p.exists()])
        return None
    layoffs = pd.read_csv(need[0], parse_dates=["date"])
    events = es.build_events(layoffs, pd.read_csv(need[1]))
    returns, _ = es.prepare_returns(pd.read_csv(need[2], parse_dates=["date"]))
    cars, _ = es.run_event_study(events, returns)
    cars["year"] = cars["date"].dt.year
    sized = es.add_size_groups(es.attach_size(cars, pd.read_csv(need[3])).dropna(subset=["log_assets"]))
    sized["size_group"] = sized["size_group"].astype(str)
    paths = es.ar_paths(cars[["event_id", "ticker", "date"]], returns)
    placebo = es.placebo_test(cars[["event_id", "ticker", "date"]], returns, n_rep=100)
    return {"cars": cars, "summary": es.summarize(cars, n_boot=n_boot), "path": es.path_summary(paths, n_boot=n_boot), "placebo": placebo,
            "by_size": es.group_summary(sized, "size_group", n_boot=n_boot), "by_year": es.group_summary(cars, "year", n_boot=n_boot),
            "diff": es.group_difference(sized, "size_group", "najmanjša tretjina", "največja tretjina", n_boot=n_boot)}


def build_figures(story: dict) -> dict[str, go.Figure]:
    sc = story["size_control"]
    pw = story.get("people_weekly")
    return {"1_casovnica": fig_timeline(story["weekly"], story["macro"], story["flags"], people=pw),
            "1_koledar": fig_layoff_calendar(story["weekly"], people=pw),
            **({"1_ljudje": fig_people_quarterly(story["quarterly"])} if story.get("quarterly") is not None else {}),
            **({"1_najvecje": fig_top_announcements(story["top"])} if story.get("top") is not None else {}),
            "2_datumi": fig_event_windows(story["weekly"], people=pw),
            "2_zamiki": fig_leadlag_heatmap(story["tests"]),
            "2_rast": fig_overbuild_quartiles(story["quartiles"]),
            "3_velikost": fig_size_deciles(story["panel"]),
            "3_modeli": fig_model_comparison(model_comparison_table(sc)),
            "3_skupine": fig_size_group_lift(sc["stratified"]),
            **({"3_podjetja": fig_company_scatter(story["boom_table"])} if story.get("boom_table") is not None else {}),
            **({"6_pot": fig_car_path(story["stock"]["path"]), "6_porazdelitev": fig_car_distribution(story["stock"]["cars"]),
                "6_skupine": fig_car_groups(story["stock"]["by_size"], story["stock"]["by_year"])} if story.get("stock") else {})}


def main() -> None:
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if sys.argv[1:] != ["preview"]:
        raise SystemExit("usage: python -m analysis.viz preview")
    for name, fig in build_figures(prepare_story_data()).items():
        log.info("wrote %s", save_html(fig, f"preview_{name}"))


if __name__ == "__main__":
    main()
