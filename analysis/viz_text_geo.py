"""Milestone figures, chapters 4 and 5 (Stream B): Slovenian, interactive (plotly), casual audience.

Chapter 4  what employers ask for (Hacker News "Who is hiring?")
           fig_topics_stacked_area, fig_topics_small_multiples, fig_topic_year_heatmap, fig_remote_ai_levels
Chapter 5  where (US metro areas, IT = NAICS 5415)
           fig_metro_map, fig_region_small_multiples

Every figure function is pure: DataFrame(s) in, plotly Figure out, inputs untouched, no file reads. Numbers in titles,
annotations and hover text are computed from the data passed in. Each figure has a companion `explain_<name>()` that returns
the four plain-language parts (kaj, zakaj, pomen, omejitve). The loaders read only the committed aggregate files:

  data/processed/hn_topics_monthly.csv   (python -m analysis.hn_text run)
  data/processed/hn_flags_monthly.csv    (python -m analysis.hn_text flags)
  data/processed/hn_change_points.csv    (python -m analysis.hn_text flags)
  data/processed/metro_map_data.csv      (python -m analysis.geo mapdata)

`build_chapter_4_5()` is the entry point for notebook 08; `python -m analysis.viz_text_geo preview` writes every figure to
reports/figures_sl/preview_<name>.html.
"""
from __future__ import annotations

import logging
import math
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.geo import LOWER48, US48_OUTLINE, in_lower48
from analysis.viz_theme import (DIVERGING, EVENTS, HOVER_MONTH, PALETTE, TOPIC_COLORS, add_event_lines, base_layout, save_html,
                                sl_num, sl_pct)
from collectors import common

log = logging.getLogger("covid_it_data")

# Slovenian names for the topic labels written by analysis.hn_text (label without the "T<n>: " prefix). Unknown labels
# (for example after the topic model is refitted) are shown as they are, so a new label never breaks a figure.
TOPIC_SL = {
    "company culture and mission": "kultura in poslanstvo podjetja",
    "data science and ML roles": "podatkovna znanost in strojno učenje",
    "San Francisco / Bay Area": "San Francisco in okolica",
    "web stack (React, Node, TypeScript)": "spletne tehnologije (React, Node, TypeScript)",
    "senior and product roles": "izkušeni razvijalci in produktne vloge",
    "enterprise development and systems": "razvoj poslovnih sistemov",
    "mobile (iOS, Android)": "mobilne aplikacije (iOS, Android)",
    "AI startups and agents": "zagonska podjetja z UI in agenti",
    "Ruby on Rails shops": "podjetja z Ruby on Rails",
    "open source": "odprta koda",
}
FLAG_SL = {"remote": ("delo na daljavo", PALETTE["blue"]), "ai_ml": ("umetna inteligenca (UI)", PALETTE["purple"])}
METRICS = {
    "it_growth_pct": dict(usable="usable", button="IT delovna mesta",
                          what="IT zaposlenosti", short="rast zaposlenosti v IT 2019-2024"),
    "estab_growth_pct": dict(usable="usable_estab", button="IT podjetja (obrati)",
                             what="števila IT podjetij", short="rast števila IT podjetij 2019-2024"),
}
REGIONS = {
    "severovzhod": "CT ME MA NH RI VT NJ NY PA",
    "srednji zahod": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "jug": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "zahod": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}
REGION_LOC = {"severovzhod": "na severovzhodu", "srednji zahod": "na srednjem zahodu", "jug": "na jugu", "zahod": "na zahodu"}
STATE_REGION = {st: reg for reg, states in REGIONS.items() for st in states.split()}
CHATGPT = EVENTS["chatgpt"][0]
_MONTH = pd.offsets.MonthBegin(1)


# ---------------------------------------------------------------------------------------- small helpers
def topic_name(label: str) -> str:
    """'T3: San Francisco / Bay Area' -> 'San Francisco in okolica' (unknown labels stay as they are, without the prefix)."""
    core = re.sub(r"^T\d+:\s*", "", str(label))
    return TOPIC_SL.get(core, core)


def _topic_order(labels) -> list[str]:
    def key(lab):
        m = re.match(r"^T(\d+):", str(lab))
        return (int(m.group(1)) if m else 10**6, str(lab))
    return sorted(pd.unique(pd.Series(labels)), key=key)


def _topics_wide(topics: pd.DataFrame) -> pd.DataFrame:
    """month (Timestamp) x topic (Slovenian name), values = share 0-1, columns in topic-number order."""
    t = topics.copy()
    t["month"] = pd.to_datetime(t["month"])
    order = _topic_order(t["topic"])
    w = t.pivot_table(index="month", columns="topic", values="share", aggfunc="mean").reindex(columns=order).sort_index()
    w.columns = [topic_name(c) for c in w.columns]
    return w


def _year_means(topics: pd.DataFrame) -> pd.DataFrame:
    w = _topics_wide(topics)
    return w.groupby(w.index.year).mean()


def _flag_series(flags: pd.DataFrame, flag: str) -> pd.Series:
    f = flags[flags["flag"] == flag]
    return pd.Series(f["share"].to_numpy(dtype=float), index=pd.to_datetime(f["month"]), name=flag).sort_index().dropna()


def _mm(d: pd.Timestamp) -> str:
    return f"{d.month}/{d.year}"


def _direction(before: float, after: float, tol_pp: float = 1.0, up: str = "narasel", down: str = "padel",
               flat: str = "ostal skoraj enak") -> str:
    """Word chosen by the numbers (shares 0-1, tolerance in percentage points)."""
    if abs(after - before) * 100 < tol_pp:
        return flat
    return up if after > before else down


def _pp(x: float) -> str:
    """Change in percentage points with a sign, Slovenian decimal comma."""
    return f"{'+' if x >= 0 else '−'}{sl_num(abs(x), 1)} odstotne točke"


def _region(metro_name: str) -> str | None:
    """Census region from the first state code in a metro name ('Boston-Cambridge-Newton, MA-NH' -> severovzhod)."""
    parts = str(metro_name).split(",")
    if len(parts) < 2:
        return None
    code = parts[1].strip().split()[0].split("-")[0] if parts[1].strip() else ""
    return STATE_REGION.get(code)


def _short_metro(name: str) -> str:
    return str(name).split(",")[0].split("-")[0].strip()


def _metro_label(name: str) -> str:
    return re.sub(r"\s+(Metro|Micro) Area$", "", str(name))


def _clip_limit(values: pd.Series, q: float = 95.0) -> float:
    """Colour range ±lim: 95th percentile of |growth|, rounded up to a multiple of 10 (at least 10)."""
    v = values.dropna().abs()
    if v.empty:
        return 10.0
    return float(max(10.0, math.ceil(np.nanpercentile(v, q) / 10.0) * 10.0))


# ---------------------------------------------------------------------------------------- chapter 4: figures
def fig_topics_stacked_area(topics: pd.DataFrame) -> go.Figure:
    """Ten topics stacked over time (each month sums to 100 %), with the Fed and ChatGPT lines."""
    w = _topics_wide(topics)
    fig = go.Figure()
    for i, name in enumerate(w.columns):
        s = w[name] * 100
        fig.add_trace(go.Scatter(x=w.index, y=s, name=name, mode="lines", stackgroup="one",
                                 line=dict(width=0.5, color=TOPIC_COLORS[i % len(TOPIC_COLORS)]),
                                 hovertemplate=f"<b>{name}</b><br>%{{x|{HOVER_MONTH}}}: %{{y:.1f}} % objav<extra></extra>"))
    y0, y1 = w.index.min().year, w.index.max().year
    fig.update_layout(**base_layout(f"O čem pišejo delodajalci na Hacker Newsu: {len(w.columns)} tem, {y0}-{y1}", height=560))
    fig.update_layout(yaxis=dict(title="delež objav (%)", range=[0, 100]), xaxis=dict(tickformat="%Y"),
                      legend=dict(orientation="h", y=-0.12, x=0, font=dict(size=11)), margin=dict(b=150))
    add_event_lines(fig, keys=("fed", "chatgpt"))
    return fig


def fig_topics_small_multiples(topics: pd.DataFrame, ncols: int = 5) -> go.Figure:
    """One panel per topic, shared y axis: monthly share (thin) and 12-month rolling mean (thick); ChatGPT line in every panel."""
    w = _topics_wide(topics)
    n = len(w.columns)
    ncols = max(1, min(ncols, n))
    nrows = math.ceil(n / ncols)
    titles = [name if len(name) <= 28 else name[:26].rstrip() + "…" for name in w.columns]
    fig = make_subplots(rows=nrows, cols=ncols, shared_yaxes="all", shared_xaxes="all", subplot_titles=titles,
                        horizontal_spacing=0.025, vertical_spacing=0.14 if nrows > 1 else 0.1)
    roll = (w.rolling(12, min_periods=12).mean()) * 100
    x_chat = CHATGPT.strftime("%Y-%m-%d")
    for i, name in enumerate(w.columns):
        r, c = i // ncols + 1, i % ncols + 1
        col = TOPIC_COLORS[i % len(TOPIC_COLORS)]
        fig.add_trace(go.Scatter(x=w.index, y=w[name] * 100, mode="lines", line=dict(color=col, width=0.8), opacity=0.45,
                                 name="mesečni delež", legendgroup="m", showlegend=i == 0,
                                 hovertemplate=f"<b>{name}</b><br>%{{x|{HOVER_MONTH}}}: %{{y:.1f}} %<extra></extra>"), row=r, col=c)
        fig.add_trace(go.Scatter(x=roll.index, y=roll[name], mode="lines", line=dict(color=col, width=2.6),
                                 name="povprečje zadnjih 12 mesecev", legendgroup="r", showlegend=i == 0,
                                 hovertemplate=f"<b>{name}</b><br>%{{x|{HOVER_MONTH}}}: 12-mesečno povprečje %{{y:.1f}} %<extra></extra>"),
                      row=r, col=c)
        k = "" if i == 0 else str(i + 1)
        fig.add_shape(type="line", xref=f"x{k}", yref=f"y{k} domain", x0=x_chat, x1=x_chat, y0=0, y1=1,
                      line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.add_annotation(xref="x", yref="y domain", x=x_chat, y=1, text="ChatGPT", showarrow=False, textangle=-90,
                       xanchor="right", yanchor="top", font=dict(size=10, color=PALETTE["ink"]))
    for a in fig.layout.annotations:
        if a.text in titles:
            a.font = dict(size=12)
    fig.update_layout(**base_layout("Vsaka tema posebej: kako se je spreminjal njen delež objav", height=260 * nrows + 120))
    fig.update_xaxes(tickformat="%Y", dtick="M48")
    fig.update_yaxes(ticksuffix=" %")
    fig.update_yaxes(title_text="delež objav", row=1, col=1)
    fig.update_layout(legend=dict(orientation="h", y=-0.08 if nrows > 1 else -0.2, x=0))
    return fig


def topic_change_table(topics: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """Per topic: mean share in the first k and last k years, and the change (sorted, largest increase first)."""
    ym = _year_means(topics)
    k = max(1, min(k, len(ym) // 2 or 1))
    first, last = ym.iloc[:k].mean(), ym.iloc[-k:].mean()
    out = pd.DataFrame({"first": first, "last": last, "change": last - first})
    out.attrs["first_years"] = (int(ym.index[0]), int(ym.index[k - 1]))
    out.attrs["last_years"] = (int(ym.index[-k]), int(ym.index[-1]))
    return out.sort_values("change", ascending=False)


def fig_topic_year_heatmap(topics: pd.DataFrame) -> go.Figure:
    """Rows = topics (biggest increase on top), columns = years, cell = mean share that year with the value printed."""
    ym = _year_means(topics)
    order = topic_change_table(topics).index.tolist()
    z = (ym[order].T * 100)
    text = [[sl_num(v, 1) if pd.notna(v) else "" for v in row] for row in z.to_numpy()]
    fig = go.Figure(go.Heatmap(z=z.to_numpy(), x=[str(y) for y in z.columns], y=z.index.tolist(), text=text,
                               texttemplate="%{text}", textfont=dict(size=11), colorscale="Blues", xgap=1, ygap=1,
                               colorbar=dict(title="delež<br>objav (%)"), hoverongaps=False,
                               hovertemplate="<b>%{y}</b><br>leto %{x}: %{text} % objav<extra></extra>"))
    y0, y1 = int(ym.index.min()), int(ym.index.max())
    fig.update_layout(**base_layout(f"Katere teme so se med letoma {y0} in {y1} okrepile in katere oslabile",
                                    height=140 + 40 * len(order)))
    fig.update_layout(xaxis=dict(title="leto", side="bottom", dtick=1), yaxis=dict(autorange="reversed", automargin=True))
    fig.add_annotation(xref="paper", yref="paper", x=0, y=1.0, yanchor="bottom", showarrow=False, font=dict(size=11),
                       text="zgoraj teme, ki so najbolj pridobile; spodaj tiste, ki so najbolj izgubile")
    return fig


def _segments(change_points: pd.DataFrame | None, flag: str) -> pd.DataFrame:
    if change_points is None or len(change_points) == 0:
        return pd.DataFrame(columns=["start", "end", "months", "mean_share"])
    s = change_points[change_points["flag"] == flag].copy()
    s["start"], s["end"] = pd.to_datetime(s["start"]), pd.to_datetime(s["end"])
    return s.dropna(subset=["start", "end", "mean_share"]).sort_values("start")


def fig_remote_ai_levels(flags: pd.DataFrame, change_points: pd.DataFrame | None = None) -> go.Figure:
    """Remote and AI/ML shares on one axis; flat steps = the average level between detected shifts; covid/Fed/ChatGPT lines."""
    fig = go.Figure()
    years = []
    for flag, (name, col) in FLAG_SL.items():
        s = _flag_series(flags, flag)
        if s.empty:
            continue
        years += [s.index.min().year, s.index.max().year]
        fig.add_trace(go.Scatter(x=s.index, y=s * 100, mode="lines", name=f"{name}: mesečno", line=dict(color=col, width=1.2),
                                 opacity=0.6, hovertemplate=f"<b>{name}</b><br>%{{x|{HOVER_MONTH}}}: %{{y:.1f}} % objav<extra></extra>"))
        seg = _segments(change_points, flag)
        if seg.empty:
            continue
        xs, ys, txt = [], [], []
        for r in seg.itertuples():
            end = r.end + _MONTH - pd.Timedelta(days=1)
            label = f"<b>{name}</b><br>{_mm(r.start)} do {_mm(r.end)}: povprečno {sl_pct(r.mean_share, 1)}"
            xs += [r.start, end, None]
            ys += [r.mean_share * 100, r.mean_share * 100, None]
            txt += [label, label, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=f"{name}: povprečje obdobja", line=dict(color=col, width=4),
                                 text=txt, hovertemplate="%{text}<extra></extra>", connectgaps=False))
    title = "Delež objav, ki omenjajo delo na daljavo ali umetno inteligenco"
    if years:
        title += f", {min(years)}-{max(years)}"
    fig.update_layout(**base_layout(title, height=500))
    fig.update_layout(yaxis=dict(title="delež objav (%)", rangemode="tozero"), xaxis=dict(tickformat="%Y"), hovermode="closest")
    add_event_lines(fig, keys=("covid", "fed", "chatgpt"))
    return fig


# ---------------------------------------------------------------------------------------- chapter 5: figures
def _map_parts(geo: pd.DataFrame, metric: str) -> dict:
    g = geo.copy()
    usable_col = METRICS[metric]["usable"]
    placed = g.dropna(subset=["lat", "lon"])
    placed = placed[in_lower48(placed["lon"], placed["lat"])]
    ok = placed[usable_col].fillna(False).astype(bool) & placed[metric].notna()
    return {"all": g, "placed": placed, "ok": placed[ok], "hidden": placed[~ok],
            "outside": int(g["lat"].notna().sum() - len(placed)), "no_xy": int(g["lat"].isna().sum())}


def _map_title(n_ok: int, metric: str) -> str:
    what = "je IT zaposlenost rasla in kje padala" if metric == "it_growth_pct" else "je število IT podjetij raslo in kje padlo"
    return f"Kje {what}, 2019-2024 ({n_ok} metro območij)"


def fig_metro_map(geo: pd.DataFrame, metric: str = "it_growth_pct", max_diameter: float = 46.0) -> go.Figure:
    """Bubble map of the lower 48: area ~ IT jobs 2019, colour = growth (DIVERGING, centred on 0, clipped), grey crosses = withheld.
    A dropdown switches between job growth and establishment growth (each with its own usable flag)."""
    if metric not in METRICS:
        raise ValueError(f"metric must be one of {list(METRICS)}")
    fig = go.Figure()
    ox, oy = zip(*US48_OUTLINE)
    fig.add_trace(go.Scatter(x=ox, y=oy, mode="lines", fill="toself", fillcolor="#F2F2F2", line=dict(color="#B0B0B0", width=1),
                             hoverinfo="skip", showlegend=False, name="obris"))
    ref = float(np.nanmax(geo["size_jobs"])) if geo["size_jobs"].notna().any() else 1.0
    titles, colorbars = {}, {}
    for m, spec in METRICS.items():
        p = _map_parts(geo, m)
        d = p["ok"].copy()
        lim = _clip_limit(d[m])
        jobs = d["size_jobs"]
        d["diam"] = np.where(jobs.notna(), np.sqrt(jobs.fillna(0).clip(lower=0) / ref) * max_diameter, 6.0)
        d["diam"] = d["diam"].clip(lower=5.0)
        d = d.sort_values("diam", ascending=False)                       # small bubbles drawn last, on top
        jobs_txt = [sl_num(v, 0) if pd.notna(v) else "podatek je skrit" for v in d["emp_it_2019"]]
        est_txt = [sl_num(v, 0) if pd.notna(v) else "ni podatka" for v in d["estabs_it_2019"]]
        hover = [f"<b>{_metro_label(nm)}</b><br>IT delovna mesta 2019: {j}<br>IT podjetja (obrati) 2019: {e}<br>"
                 f"{spec['short']}: {'+' if v >= 0 else '−'}{sl_num(abs(v), 1)} %"
                 for nm, j, e, v in zip(d["metro_name"], jobs_txt, est_txt, d[m])]
        fig.add_trace(go.Scatter(
            x=d["lon"], y=d["lat"], mode="markers", name=spec["button"], visible=m == metric, showlegend=False,
            text=hover, hovertemplate="%{text}<extra></extra>",
            marker=dict(size=d["diam"], color=d[m].clip(-lim, lim), colorscale=DIVERGING, cmin=-lim, cmax=lim, cmid=0,
                        opacity=0.88, line=dict(color="#444444", width=0.6),
                        colorbar=dict(title=dict(text=f"rast 2019-2024 (%)<br><sub>skrajnosti skrčene na ±{sl_num(lim, 0)} %</sub>"),
                                      ticksuffix=" %", len=0.75))))
        h = p["hidden"]
        fig.add_trace(go.Scatter(
            x=h["lon"], y=h["lat"], mode="markers", name=f"podatek je skrit ({len(h)})", visible=m == metric,
            marker=dict(symbol="x", size=7, color=PALETTE["grey"], line=dict(width=1)),
            text=[f"<b>{_metro_label(nm)}</b><br>podatek je skrit (ni enak nič)" for nm in h["metro_name"]],
            hovertemplate="%{text}<extra></extra>"))
        titles[m] = _map_title(len(d), m)
        colorbars[m] = lim
    keys = list(METRICS)
    buttons = []
    for m in keys:
        vis = [True] + [k == m for k in keys for _ in (0, 1)]
        buttons.append(dict(label=METRICS[m]["button"], method="update", args=[{"visible": vis}, {"title.text": titles[m]}]))
    p = _map_parts(geo, metric)
    foot = (f"Narisanih je {len(p['placed'])} od {len(p['all'])} metro območij (le celinski del ZDA; {p['outside']} jih leži na "
            f"Aljaski, Havajih ali v Portoriku, {p['no_xy']} brez koordinat). IT = svetovanje in računalniško programiranje po naročilu "
            "(NAICS 5415), brez založnikov programske opreme in velikih tehnoloških podjetij. Obris je poenostavljen.")
    fig.update_layout(**base_layout(titles[metric], height=620))
    fig.update_layout(
        xaxis=dict(range=list(LOWER48["lon"]), visible=False, fixedrange=False),
        yaxis=dict(range=list(LOWER48["lat"]), visible=False, scaleanchor="x", scaleratio=1.3),
        legend=dict(orientation="h", y=-0.02, x=0), hovermode="closest", margin=dict(l=10, r=10, t=90, b=90),
        updatemenus=[dict(type="dropdown", buttons=buttons, active=keys.index(metric), x=0, xanchor="left", y=1.08,
                          yanchor="bottom", showactive=True)],
        annotations=[dict(xref="paper", yref="paper", x=0, y=-0.1, xanchor="left", yanchor="top", showarrow=False, align="left",
                          font=dict(size=10, color="#555555"), text=foot)])
    fig.add_annotation(xref="paper", yref="paper", x=0.99, y=0.02, xanchor="right", yanchor="bottom", showarrow=False, align="right",
                       font=dict(size=10), bgcolor="rgba(255,255,255,0.8)",
                       text="velikost kroga = IT delovna mesta 2019<br>modro = rast, rdeče = upad")
    return fig


def fig_region_small_multiples(geo: pd.DataFrame, metric: str = "it_growth_pct", clip: float = 150.0) -> go.Figure:
    """Four panels (Census regions), shared y axis: one dot per metro (growth), box = middle half, line = median."""
    g = geo.copy()
    g["regija"] = g["metro_name"].map(_region)
    ok = g[METRICS[metric]["usable"]].fillna(False).astype(bool) & g[metric].notna() & g["regija"].notna()
    d = g[ok]
    regs = list(REGIONS)
    fig = make_subplots(rows=1, cols=len(regs), shared_yaxes=True, horizontal_spacing=0.03,
                        subplot_titles=[f"{r} ({int((d['regija'] == r).sum())})" for r in regs])
    n_out = int((d[metric].abs() > clip).sum())
    for j, r in enumerate(regs, 1):
        s = d[d["regija"] == r]
        if s.empty:
            continue
        y = s[metric].clip(-clip, clip)
        fig.add_trace(go.Box(y=y, boxpoints="all", jitter=0.5, pointpos=0, name=r, showlegend=False, fillcolor="rgba(76,120,168,0.15)",
                             line=dict(color=PALETTE["blue"]), marker=dict(color=PALETTE["blue"], size=5, opacity=0.6),
                             text=[f"<b>{_metro_label(nm)}</b><br>{METRICS[metric]['short']}: {sl_num(v, 1)} %"
                                   for nm, v in zip(s["metro_name"], s[metric])],
                             hovertemplate="%{text}<extra></extra>"), row=1, col=j)
        med = float(s[metric].median())
        k = "" if j == 1 else str(j)
        fig.add_annotation(xref=f"x{k} domain", yref=f"y{k}", x=0.98, y=float(np.clip(med, -clip, clip)), xanchor="right",
                           yanchor="bottom", showarrow=False, text=f"mediana {sl_num(med, 1)} %", font=dict(size=11, color=PALETTE["ink"]))
    for j in range(1, len(regs) + 1):
        fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"), row=1, col=j)
    fig.update_layout(**base_layout(f"Rast zaposlenosti v IT 2019-2024 po regijah ZDA ({len(d)} metro območij)", height=470))
    fig.update_yaxes(title_text="rast 2019-2024 (%)", row=1, col=1)
    fig.update_xaxes(showticklabels=False)
    if n_out:
        fig.add_annotation(xref="paper", yref="paper", x=1, y=-0.08, xanchor="right", showarrow=False, font=dict(size=10),
                           text=f"{n_out} območij z rastjo nad ±{sl_num(clip, 0)} % je narisanih na robu")
    return fig


# ---------------------------------------------------------------------------------------- chapter 4: explanations
_HN_LIMITS = ("Hacker News je kotiček trga, kjer prevladujejo zagonska podjetja (startupi) iz ZDA, zato ne predstavlja vseh delodajalcev. ")


def explain_topics_stacked_area(topics: pd.DataFrame) -> dict:
    w = _topics_wide(topics)
    first, last = w.iloc[:12].mean(), w.iloc[-12:].mean()
    diff = (last - first).sort_values()
    up, down = diff.index[-1], diff.index[0]
    top_first, top_last = first.idxmax(), last.idxmax()
    same = top_first == top_last
    return {
        "kaj": "Vsaka barvna plast je ena tema, ki jo je računalnik sam našel v besedilih oglasov za delo. Debelina plasti pove, "
               "kolikšen delež objav v tistem mesecu govori predvsem o tej temi; skupaj plasti vedno dajo 100 %. "
               "Ko miško premakneš na plast, vidiš ime teme in njen delež; črtkani črti označujeta prvo zvišanje obrestne mere in ChatGPT.",
        "zakaj": "Hoteli smo videti, ali se je spremenilo, o čem delodajalci pišejo, ko iščejo ljudi: o tehnologijah, o vrsti dela ali o podjetju.",
        "pomen": (f"V prvih 12 mesecih s podatki ({_mm(w.index[0])} do {_mm(w.index[min(11, len(w) - 1)])}) je bila najpogostejša tema "
                  f"»{top_first}« ({sl_pct(first[top_first], 0)} objav), v zadnjih 12 mesecih "
                  + (f"je še vedno na vrhu ({sl_pct(last[top_last], 0)}). " if same else f"pa »{top_last}« ({sl_pct(last[top_last], 0)}). ")
                  + f"Najbolj je {_direction(first[up], last[up], up='narasla', down='padla', flat='ostala skoraj enaka')} tema »{up}« "
                  f"(z {sl_pct(first[up], 0)} na {sl_pct(last[up], 0)}), najbolj je {_direction(first[down], last[down], up='narasla', down='padla', flat='ostala skoraj enaka')} "
                  f"»{down}« (z {sl_pct(first[down], 0)} na {sl_pct(last[down], 0)})."),
        "omejitve": _HN_LIMITS + "Teme je določil algoritem (vsaka objava je pripisana svoji najmočnejši temi), imena tem pa smo dali mi; "
                    "z drugim številom tem bi bila razdelitev nekoliko drugačna. Graf kaže, o čem se piše, ne koliko ljudi je zaposlenih.",
    }


def explain_topics_small_multiples(topics: pd.DataFrame) -> dict:
    w = _topics_wide(topics)
    pre = w[(w.index >= CHATGPT - pd.DateOffset(months=12)) & (w.index <= CHATGPT)].mean()
    post = w.iloc[-12:].mean()
    if w.index.max() <= CHATGPT or pre.isna().all():
        pomen = (f"Podatki segajo do {_mm(w.index.max())}, torej ne pokrivajo obdobja po izidu ChatGPT, zato primerjave pred in po ne moremo narediti.")
    else:
        d = (post - pre)
        n_up = int((d * 100 >= 1).sum())
        n_down = int((d * 100 <= -1).sum())
        best, worst = d.idxmax(), d.idxmin()
        pomen = (f"Primerjali smo 12 mesecev pred izidom ChatGPT z zadnjimi 12 meseci (do {_mm(w.index.max())}). "
                 f"Za vsaj eno odstotno točko je pridobilo {n_up} od {len(d)} tem, izgubilo pa {n_down}. "
                 f"Največ je pridobila »{best}« ({_pp(d[best] * 100)}), največ izgubila »{worst}« ({_pp(d[worst] * 100)}).")
    return {
        "kaj": f"Vsak mali graf je ena od {len(w.columns)} tem. Tanka črta je delež objav v posameznem mesecu, debela pa povprečje "
               "zadnjih 12 mesecev, ki skrije mesečno nihanje. Vsi grafi imajo enako navpično os, zato so velikosti neposredno primerljive. "
               "Črtkana črta je datum izida ChatGPT (30. 11. 2022).",
        "zakaj": "Na skupnem grafu se majhne teme izgubijo. Tukaj vidimo vsako posebej in lahko primerjamo, katera je rasla in katera padala.",
        "pomen": pomen,
        "omejitve": _HN_LIMITS + "Sprememba po datumu izida ChatGPT ne pomeni, da jo je povzročil ChatGPT: hkrati so se zviševale obrestne mere "
                    "in zmanjševalo zaposlovanje. Imena tem so naša, teme pa je določil algoritem.",
    }


def explain_topic_year_heatmap(topics: pd.DataFrame) -> dict:
    t = topic_change_table(topics)
    (a0, a1), (b0, b1) = t.attrs["first_years"], t.attrs["last_years"]
    span = lambda x, y: str(x) if x == y else f"{x}-{y}"
    up, down = t.index[0], t.index[-1]
    up_txt = (f"Najbolj je pridobila »{up}«: z {sl_pct(t.loc[up, 'first'], 1)} na {sl_pct(t.loc[up, 'last'], 1)} objav."
              if t.loc[up, "change"] > 0 else "Nobena tema ni pridobila.")
    down_txt = (f"Najbolj je izgubila »{down}«: z {sl_pct(t.loc[down, 'first'], 1)} na {sl_pct(t.loc[down, 'last'], 1)}."
                if t.loc[down, "change"] < 0 else "Nobena tema ni izgubila.")
    return {
        "kaj": "Vsaka vrstica je ena tema, vsak stolpec eno leto. Številka v polju je povprečen delež objav tistega leta v odstotkih; "
               "temnejše polje pomeni večji delež. Teme so razvrščene po spremembi: zgoraj tiste, ki so najbolj pridobile, spodaj tiste, ki so najbolj izgubile.",
        "zakaj": "Mesečne številke precej nihajo. Letna povprečja dajo bolj miren pregled, katere teme so v zadnjih letih dobile prostor.",
        "pomen": f"Primerjali smo prva leta ({span(a0, a1)}) z zadnjimi ({span(b0, b1)}). {up_txt} {down_txt}",
        "omejitve": _HN_LIMITS + "Zadnje leto je lahko nepopolno (podatki ne pokrivajo vseh mesecev), zato je njegovo povprečje manj zanesljivo. "
                    "Teme je določil algoritem, zato meje med njimi niso ostre.",
    }


def explain_remote_ai_levels(flags: pd.DataFrame, change_points: pd.DataFrame | None = None) -> dict:
    parts = []
    for flag, (name, _) in FLAG_SL.items():
        s = _flag_series(flags, flag)
        if s.empty:
            continue
        first, last = s.iloc[:12].mean(), s.iloc[-12:].mean()
        peak = s.idxmax()
        txt = (f"Omembe {'dela na daljavo' if flag == 'remote' else 'umetne inteligence'} so v prvih 12 mesecih zajemale {sl_pct(first, 0)} objav, "
               f"v zadnjih 12 mesecih {sl_pct(last, 0)} (delež je {_direction(first, last)}); vrh je bil {_mm(peak)} s {sl_pct(s.max(), 0)}.")
        seg = _segments(change_points, flag)
        if len(seg) > 1:
            shifts = ", ".join(_mm(x) for x in seg["start"].iloc[1:])
            txt += f" Večji premiki ravni so se zgodili {shifts}."
        parts.append(txt)
    pomen = " ".join(parts) if parts else "V podatkih ni mesecev z oznakami."
    return {
        "kaj": "Modra črta je delež objav, ki omenjajo delo na daljavo, vijolična delež objav, ki omenjajo umetno inteligenco ali strojno učenje. "
               "Debele vodoravne stopnice so povprečna raven med dvema premikoma: računalnik je poiskal mesece, ko se je raven najbolj spremenila "
               "(»premik skozi čas«). Črtkane črte označujejo začetek pandemije, prvo zvišanje obrestne mere in ChatGPT.",
        "zakaj": "Želeli smo videti, kdaj točno sta se spremenili dve stvari, o katerih se največ govori: delo na daljavo in umetna inteligenca.",
        "pomen": pomen,
        "omejitve": _HN_LIMITS + "Oznake temeljijo na iskanju ključnih besed: objava, ki napiše »no remote«, šteje kot omemba dela na daljavo. "
                    "Premiki skozi čas so ocena (iskali smo največ tri), ne dokaz, da se je kaj zgodilo prav tisti mesec, in ne povedo, zakaj.",
    }


# ---------------------------------------------------------------------------------------- chapter 5: explanations
_GEO_LIMITS = ("IT tukaj pomeni samo podjetja za svetovanje in programiranje po naročilu (NAICS 5415); založniki programske opreme in velika "
               "tehnološka podjetja niso všteti. Kjer je podatek skrit, to ni nič: urad ga ne objavi, da ne bi razkril posameznega podjetja. ")


def explain_metro_map(geo: pd.DataFrame) -> dict:
    p = _map_parts(geo, "it_growth_pct")
    d, h = p["ok"], p["hidden"]
    pe = _map_parts(geo, "estab_growth_pct")["ok"]
    med = float(d["it_growth_pct"].median()) if len(d) else float("nan")
    share_up = float((d["it_growth_pct"] > 0).mean()) if len(d) else float("nan")
    big = d.nlargest(min(25, len(d)), "size_jobs")
    sentences = []
    if len(d):
        sentences.append(f"Med {len(d)} metro območji z uporabnim podatkom se je IT zaposlenost povečala v {sl_pct(share_up, 0)} območij; "
                         f"pri tipičnem območju (mediana) je {'zrasla' if med > 0 else 'padla'} za {sl_num(abs(med), 1)} %.")
    if len(big) >= 2:
        b, wst = big.loc[big["it_growth_pct"].idxmax()], big.loc[big["it_growth_pct"].idxmin()]
        sentences.append(f"Med {len(big)} največjimi je najbolj {'zrasel' if b['it_growth_pct'] > 0 else 'padel'} {_short_metro(b['metro_name'])} "
                         f"({'+' if b['it_growth_pct'] >= 0 else '−'}{sl_num(abs(b['it_growth_pct']), 0)} %), najslabše se je odrezal "
                         f"{_short_metro(wst['metro_name'])} ({'+' if wst['it_growth_pct'] >= 0 else '−'}{sl_num(abs(wst['it_growth_pct']), 0)} %).")
    if len(pe):
        me = float(pe["estab_growth_pct"].median())
        sentences.append(f"Število IT podjetij je pri tipičnem območju {'zraslo' if me > 0 else 'padlo'} za {sl_num(abs(me), 0)} % "
                         f"(podatek imamo za {len(pe)} območij, ker se število podjetij ne skriva).")
    hidden_big = h.nlargest(min(5, len(h)), "size_jobs")["metro_name"].map(_short_metro).tolist()
    if len(h):
        sentences.append(f"Za {len(h)} območij je podatek o zaposlenosti skrit ali nepopoln" + (f", med njimi {', '.join(hidden_big)}." if hidden_big else "."))
    return {
        "kaj": "Vsak krog je eno metro območje v ZDA (mesto z okolico). Velikost kroga pove, koliko ljudi je tam leta 2019 delalo v IT, "
               "barva pa, ali se je število do leta 2024 povečalo (modro) ali zmanjšalo (rdeče); bela pomeni skoraj brez spremembe. "
               "Sivi križci so območja, kjer je podatek skrit. Z menijem levo zgoraj preklopiš na rast števila IT podjetij; ko miško premakneš na krog, vidiš ime in številke.",
        "zakaj": "Zanimalo nas je, ali se je IT delo po pandemiji preselilo: ali so velika tradicionalna središča izgubljala in manjša, cenejša mesta pridobivala.",
        "pomen": " ".join(sentences) if sentences else "Na zemljevidu ni območij z uporabnim podatkom.",
        "omejitve": _GEO_LIMITS + "Primerjamo le dve leti, zato zemljevid ne pokaže, kaj se je dogajalo vmes. Rast pri majhnih območjih je lahko velika "
                    "že zaradi enega podjetja. Zemljevid kaže, kje se je kaj spremenilo, ne pa zakaj.",
    }


def explain_region_small_multiples(geo: pd.DataFrame, metric: str = "it_growth_pct") -> dict:
    g = geo.copy()
    g["regija"] = g["metro_name"].map(_region)
    ok = g[METRICS[metric]["usable"]].fillna(False).astype(bool) & g[metric].notna() & g["regija"].notna()
    meds = g[ok].groupby("regija")[metric].agg(["median", "size"]).reindex(list(REGIONS)).dropna()
    if meds.empty:
        pomen = "Za nobeno regijo ni uporabnih podatkov."
    else:
        hi, lo = meds["median"].idxmax(), meds["median"].idxmin()
        listing = "; ".join(f"{r} {'+' if v >= 0 else '−'}{sl_num(abs(v), 1)} % ({int(n)} območij)" for r, (v, n) in meds.iterrows())
        pomen = (f"Mediana rasti po regijah: {listing}. Najvišja je {REGION_LOC[hi]}, najnižja {REGION_LOC[lo]}"
                 + (", vendar so razlike med regijami majhne v primerjavi z razlikami znotraj regij." if (meds["median"].max() - meds["median"].min()) < 10
                    else "; razlika med njima je " + sl_num(meds["median"].max() - meds["median"].min(), 1) + " odstotne točke."))
    return {
        "kaj": "Štirje grafi, po eden za vsako veliko regijo ZDA. Vsaka pika je eno metro območje, njena višina pa rast IT zaposlenosti "
               "med 2019 in 2024. Škatla zajame srednjo polovico območij, črta v njej in napis pa mediano (tipično območje). Ko miško premakneš na piko, vidiš ime.",
        "zakaj": "Zemljevid kaže posamezna mesta, tukaj pa preverimo, ali je celoten jug ali zahod rasel hitreje kot severovzhod in srednji zahod.",
        "pomen": pomen,
        "omejitve": _GEO_LIMITS + "Regijo določimo po prvi zvezni državi v imenu območja, kar pri območjih čez mejo držav ni povsem natančno. "
                    "Vsako območje šteje enako, ne glede na velikost.",
    }


# ---------------------------------------------------------------------------------------- loaders and entry point
def _read(name: str, hint: str, **kw) -> pd.DataFrame:
    path = common.PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"{path} manjka (missing). Create it with: {hint}")
    return pd.read_csv(path, **kw)


def load_topics() -> pd.DataFrame:
    return _read("hn_topics_monthly.csv", "python -m analysis.hn_text run")


def load_flags() -> pd.DataFrame:
    return _read("hn_flags_monthly.csv", "python -m analysis.hn_text flags")


def load_change_points() -> pd.DataFrame:
    return _read("hn_change_points.csv", "python -m analysis.hn_text flags")


def load_map_data() -> pd.DataFrame:
    g = _read("metro_map_data.csv", "python -m analysis.geo mapdata", dtype={"cbsa_code": str})
    g["cbsa_code"] = g["cbsa_code"].str.zfill(5)
    for c in ("usable", "usable_estab"):
        g[c] = g[c].map(lambda v: str(v).strip().lower() in ("true", "1", "1.0"))
    return g


def build_figures(topics, flags, change_points, geo) -> dict[str, go.Figure]:
    return {"4_teme_povrsina": fig_topics_stacked_area(topics),
            "4_teme_mali_grafi": fig_topics_small_multiples(topics),
            "4_teme_toplotna": fig_topic_year_heatmap(topics),
            "4_daljava_ui": fig_remote_ai_levels(flags, change_points),
            "5_zemljevid": fig_metro_map(geo),
            "5_regije": fig_region_small_multiples(geo)}


def build_explanations(topics, flags, change_points, geo) -> dict[str, dict]:
    return {"4_teme_povrsina": explain_topics_stacked_area(topics),
            "4_teme_mali_grafi": explain_topics_small_multiples(topics),
            "4_teme_toplotna": explain_topic_year_heatmap(topics),
            "4_daljava_ui": explain_remote_ai_levels(flags, change_points),
            "5_zemljevid": explain_metro_map(geo),
            "5_regije": explain_region_small_multiples(geo)}


def build_chapter_4_5() -> dict[str, tuple[go.Figure, dict]]:
    """Every chapter 4-5 figure with its four-part explanation, in display order. Raises FileNotFoundError if a CSV is missing."""
    data = (load_topics(), load_flags(), load_change_points(), load_map_data())
    figs, texts = build_figures(*data), build_explanations(*data)
    return {name: (figs[name], texts[name]) for name in figs}


def main() -> None:
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if sys.argv[1:] != ["preview"]:
        raise SystemExit("usage: python -m analysis.viz_text_geo preview")
    for name, (fig, _) in build_chapter_4_5().items():
        log.info("wrote %s", save_html(fig, f"preview_{name}"))


if __name__ == "__main__":
    main()
