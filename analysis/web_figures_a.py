"""Stream A's figures for the presentation website (web/CONTRACT.md). Needs the local data; writes web/figures/a/<name>.json.

    python -m analysis.web_figures_a

One message per chart: the title is the conclusion, one series is in colour and everything else is grey (analysis.web_theme).
The numbers in the chapter text (web/chapters/01-04, 07) come from `facts()`, printed by `main`, so text and charts can be checked
against each other after every re-run. Only aggregates reach the JSON files (no per-company rows).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis import web_theme as wt
from analysis.viz_theme import PALETTE, base_layout

log = logging.getLogger("covid_it_data")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "figures" / "a"
REPORTS = ROOT / "reports"
ALPHA = 0.05


def _fmt(x: float, d: int = 0) -> str:
    """Slovenian number: decimal comma, thousands dot."""
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _days(idx) -> list[str]:
    """Dates as text: plotly reads them as dates everywhere (traces, annotations), with no time-zone or number conversion."""
    return pd.DatetimeIndex(idx).strftime("%Y-%m-%d").tolist()


def _layout(fig: go.Figure, height: int = 480) -> go.Figure:
    fig.update_layout(**base_layout(None, height=height))
    return fig


# ---------------------------------------------------------------------------------------- data
def indeed_monthly(raw: Path | None = None, country: str = "US") -> pd.DataFrame:
    """Monthly mean of Indeed's daily postings index (1 Feb 2020 = 100): software development, and all postings (seasonally adjusted)."""
    raw = raw or ROOT / "data" / "raw"
    it = pd.read_csv(raw / "indeed_it_sector_postings.csv", parse_dates=["date"])
    it = it[(it["jobcountry"] == country) & (it["variable"] == "total postings") & (it["display_name"] == "Software Development")]
    ag = pd.read_csv(raw / "indeed_aggregate_postings.csv", parse_dates=["date"])
    ag = ag[(ag["jobcountry"] == country) & (ag["variable"] == "total postings")]
    out = pd.DataFrame({"software": it.set_index("date")["indeed_job_postings_index"].resample("MS").mean(),
                        "all": ag.set_index("date")["indeed_job_postings_index_SA"].resample("MS").mean()})
    return out.dropna(how="all")


def load_results() -> dict:
    """The hypothesis results files that exist (round 1: A, B, C, D; round 2: C2, E and, once Stream B delivers them, A2, F)."""
    out = {}
    for name in ("hypotheses_a_results", "hypotheses_b_results", "hypotheses2_a_results", "hypotheses2_b_results"):
        p = REPORTS / f"{name}.json"
        if p.exists():
            out.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if isinstance(v, dict) and "primary" in v})
    return out


def prepare_web_data() -> dict:
    """Run the parts of the analyses the site needs (about a minute; no stock prices, no model fitting)."""
    from analysis import causes as cs
    from analysis import comparisons as cp
    from analysis.compare_viz import load_headcount
    from collectors.common import PROCESSED
    d = cs.load_inputs()
    ev = d["events"]
    h2 = cs.run_h2(ev, d["fred"], d["jolts"])
    panel = pd.read_csv(PROCESSED / "company_panel.csv", dtype={"sic": str, "sic2": str})
    out = {"indeed": indeed_monthly(), "quarterly": cs.quarterly_layoffs(ev), "monthly": cs.monthly_layoffs(ev),
           "macro": cs.monthly_macro(d["fred"]), "studies": h2["studies"], "jolts": h2["jolts"],
           "panel": panel, "challenger": cp.challenger_compare(ev), "results": load_results()}
    heads = load_headcount()
    if heads is not None:
        boom = cs.run_h3(d["fin"], d["revenue"], d["universe"], d["matches"], ev)["used"]
        out["headcount"] = cp.headcount_overhiring(heads, boom, n_boot=50)    # only the quartile tables are used here
    return out


def size_deciles(panel: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Share of company-quarters followed by a layoff announcement within two quarters, by size decile (log assets); as notebook 08."""
    d = panel.dropna(subset=["log_assets"]).copy()
    d["group"] = pd.qcut(d["log_assets"], n, labels=False, duplicates="drop") + 1
    return d.groupby("group").agg(rows=("y_next2q", "size"), positive=("y_next2q", "sum"), share=("y_next2q", "mean")).reset_index()


# ---------------------------------------------------------------------------------------- chapter 1
def fig_postings(ind: pd.DataFrame) -> go.Figure:
    s, a = ind["software"].dropna(), ind["all"].dropna()
    fig = go.Figure([
        go.Scatter(x=_days(a.index), y=a, name="vsi oglasi", mode="lines", line=dict(color=wt.ROLE["context"], width=2),
                   hovertemplate="%{x|%m/%Y}: %{y:.0f}<extra>vsi oglasi</extra>"),
        go.Scatter(x=_days(s.index), y=s, name="razvoj programske opreme", mode="lines", line=dict(color=wt.ROLE["main"], width=4),
                   hovertemplate="%{x|%m/%Y}: %{y:.0f}<extra>razvoj programske opreme</extra>")])
    fig.add_hline(y=100, line=dict(color=PALETTE["ink"], width=1, dash="dot"))
    _layout(fig)
    peak = s.idxmax()
    wt.title(fig, f"Oglasov za programerje je bilo leta 2022 {_fmt(s.max() / s.iloc[-1], 0)}-krat več kot danes",
             "oglasi za delo na Indeedu v ZDA, februar 2020 = 100")
    wt.direct_labels(fig, fmt=lambda name, y: "programerji" if name.startswith("razvoj") else name)
    wt.callout(fig, peak.strftime("%Y-%m-%d"), s.max(), f"vrh: {peak.month}/{peak.year}<br>{_fmt(s.max())}", ax=60, ay=-10)
    fig.update_yaxes(title_text="indeks (feb. 2020 = 100)", rangemode="tozero")
    fig.update_xaxes(range=[_days(a.index[:1])[0], _days(s.index[-1:] + pd.DateOffset(months=1))[0]])
    return fig


def fig_people(q: pd.DataFrame) -> go.Figure:
    peak = q.loc[q["people"].idxmax()]
    colors = [wt.ROLE["loss"] if k == peak.name else "rgba(228,87,86,0.55)" for k in q.index]
    fig = go.Figure(go.Bar(x=q["quarter"], y=q["people"], marker_color=colors, customdata=np.c_[q["events_with_people"], q["events"]],
                           hovertemplate="%{x}: %{y:,.0f} ljudi<br>število znano pri %{customdata[0]} od %{customdata[1]} napovedi<extra></extra>"))
    _layout(fig)
    wt.title(fig, f"Na vrhu, v začetku leta 2023, so v ZDA napovedali odpuščanje {_fmt(round(peak['people'], -3))} ljudi v treh mesecih",
             "ljudje v napovedih odpuščanj tehnoloških podjetij v ZDA, po četrtletjih (le napovedi s številom)")
    fig.update_yaxes(title_text="ljudje v četrtletju", tickformat=",.0f")
    fig.update_xaxes(tickangle=-45)
    return fig


# ---------------------------------------------------------------------------------------- chapter 2
def fig_rate_and_layoffs(macro: pd.DataFrame, monthly: pd.DataFrame, hike, chatgpt) -> go.Figure:
    m = monthly[monthly.index >= "2020-04-01"]
    r = macro.loc[macro.index >= "2020-04-01", "fedfunds"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.4, 0.6],
                        subplot_titles=["obrestna mera Fed (%)", "napovedi odpuščanj v ZDA na mesec"])
    fig.add_trace(go.Scatter(x=_days(r.index), y=r, mode="lines", line=dict(color=wt.ROLE["main"], width=3), showlegend=False,
                             hovertemplate="%{x|%m/%Y}: %{y:.2f} %<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=_days(m.index), y=m["events"], marker_color=wt.ROLE["loss"], showlegend=False,
                         hovertemplate="%{x|%m/%Y}: %{y} napovedi<extra></extra>"), row=2, col=1)
    for when, text, dash, side in ((hike, "prvo zvišanje<br>obrestne mere", "dash", "right"), (chatgpt, "ChatGPT", "dot", "left")):
        x = pd.Timestamp(when).strftime("%Y-%m-%d")
        fig.add_shape(type="line", x0=x, x1=x, xref="x", y0=0, y1=1, yref="paper", line=dict(color=PALETTE["ink"], width=1.5, dash=dash))
        fig.add_annotation(x=x, y=0.5, xref="x", yref="paper", text=text, showarrow=False, xanchor=side, xshift=-4 if side == "right" else 4,
                           yanchor="middle", align=side, font=dict(color=PALETTE["ink"]))
    _layout(fig, height=560)
    wt.title(fig, "Napovedi so poskočile nekaj mesecev po prvem zvišanju obrestne mere", "obrestna mera ameriške centralne banke (zgoraj) in število napovedi odpuščanj (spodaj)")
    return fig


def fig_before_after(studies: dict) -> go.Figure:
    """Mean announcements per week in the 26 weeks before and after each date."""
    names = {"first Fed hike 2022-03-16": "prvo zvišanje obrestne mere<br>(16. 3. 2022)", "ChatGPT 2022-11-30": "izid ChatGPT<br>(30. 11. 2022)"}
    keys = [k for k in names if k in studies]
    x = [names[k] for k in keys]
    before = [studies[k]["before_mean"] for k in keys]
    after = [studies[k]["after_mean"] for k in keys]
    fig = go.Figure([go.Bar(x=x, y=before, name="pol leta prej", marker_color=wt.ROLE["context"], text=[_fmt(v, 1) for v in before],
                            textposition="outside", hovertemplate="%{x}<br>pol leta prej: %{y:.1f} na teden<extra></extra>"),
                     go.Bar(x=x, y=after, name="pol leta potem", marker_color=wt.ROLE["loss"], text=[_fmt(v, 1) for v in after],
                            textposition="outside", hovertemplate="%{x}<br>pol leta potem: %{y:.1f} na teden<extra></extra>")])
    _layout(fig, height=460)
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0))
    s = studies.get("first Fed hike 2022-03-16")
    wt.title(fig, f"Po prvem zvišanju obrestne mere {_fmt(s['ratio'], 0)}-krat več napovedi, po ChatGPT enako kot prej" if s else "Pred in po",
             "povprečno število napovedi odpuščanj v ZDA na teden, 26 tednov pred in po datumu")
    fig.update_yaxes(title_text="napovedi na teden", rangemode="tozero")
    return fig


# ---------------------------------------------------------------------------------------- chapter 3
def fig_size(dec: pd.DataFrame) -> go.Figure:
    top, low = dec.iloc[-1], dec.iloc[0]
    colors = [wt.ROLE["main"] if g == top["group"] else wt.ROLE["context"] for g in dec["group"]]
    fig = go.Figure(go.Bar(x=dec["group"], y=100 * dec["share"], marker_color=colors, text=[_fmt(100 * v, 0) + " %" for v in dec["share"]],
                           textposition="outside", customdata=np.c_[dec["rows"], dec["positive"]],
                           hovertemplate="velikostna skupina %{x}<br>%{customdata[1]} od %{customdata[0]} četrtletij: %{y:.1f} %<extra></extra>"))
    _layout(fig, height=460)
    if low["share"] > 0:
        head = f"Največja podjetja so odpuščanja napovedala {_fmt(top['share'] / low['share'], 0)}-krat pogosteje kot najmanjša"
    else:
        head = f"Pri največjih podjetjih je napoved sledila vsakemu {_fmt(1 / top['share'], 0)}. četrtletju, pri najmanjših nobenemu"
    wt.title(fig, head,
             "delež četrtletij, ki jim v pol leta sledi napoved odpuščanj; javna tehnološka podjetja v ZDA po velikosti (premoženju)")
    fig.update_xaxes(title_text="velikost podjetja: 1 = najmanjša desetina, 10 = največja desetina", dtick=1)
    fig.update_yaxes(title_text="%", rangemode="tozero")
    return fig


def fig_hiring(h: dict) -> go.Figure:
    q = h["quartiles"]
    labels = ["najpočasneje", "2. četrtina", "3. četrtina", "najhitreje"]
    colors = [wt.ROLE["context"]] * (len(q) - 1) + [wt.ROLE["loss"]]
    fig = go.Figure(go.Bar(x=labels[:len(q)], y=100 * q["rate"], marker_color=colors, text=[_fmt(100 * v, 0) + " %" for v in q["rate"]],
                           textposition="outside", customdata=np.c_[q["laid_off"], q["companies"]],
                           hovertemplate="%{x}: %{y:.0f} %<br>%{customdata[0]} od %{customdata[1]} podjetij<extra></extra>"))
    _layout(fig, height=460)
    wt.title(fig, "Kdor je v pandemiji najhitreje zaposloval, je kasneje najpogosteje odpuščal",
             "delež podjetij z napovedjo odpuščanj 2022-2023, po rasti števila zaposlenih 2019-2021 (četrtine podjetij)")
    fig.update_xaxes(title_text="kako hitro je podjetje zaposlovalo 2019-2021")
    fig.update_yaxes(title_text="%", rangemode="tozero")
    return fig


# ---------------------------------------------------------------------------------------- chapter 4
def fig_c2(c2: dict) -> go.Figure:
    p = c2["primary"]
    vals = [100 * np.expm1(p["median_not"]), 100 * np.expm1(p["median_announced"])]
    names = [f"brez napovedi<br>({p['n_not']} podjetje-let)", f"z napovedjo odpuščanj<br>({p['n_announced']} podjetje-let)"]
    fig = go.Figure(go.Bar(x=names, y=vals, marker_color=[wt.ROLE["context"], wt.ROLE["loss"]],
                           text=[("+" if v > 0 else "") + _fmt(v, 1) + " %" for v in vals], textposition="outside",
                           hovertemplate="%{x}<br>srednja sprememba: %{y:.1f} %<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1))
    _layout(fig, height=460)
    wt.title(fig, "Kdor je napovedal odpuščanja, je imel konec leta res manj zaposlenih",
             "srednja sprememba števila zaposlenih v letu napovedi (letna poročila 10-K), tehnološka podjetja v ZDA, 2024 in 2025")
    lo = min(vals)
    fig.update_yaxes(title_text="sprememba zaposlenih (%)", range=[min(-6, lo * 1.5), max(3, max(vals) * 2.5)])
    return fig


def fig_e(e: dict) -> go.Figure:
    p = e["primary"]
    fig = go.Figure(go.Bar(y=["če bi bil datum naključen", "v resnici"], x=[p["expected"], p["observed"]], orientation="h",
                           marker_color=[wt.ROLE["context"], wt.ROLE["main"]], text=[_fmt(p["expected"]), _fmt(p["observed"])],
                           textposition="outside", hovertemplate="%{y}: %{x:.0f} napovedi<extra></extra>"))
    _layout(fig, height=380)
    wt.title(fig, f"Odpuščanja napovedo ob poročilu o poslovanju {_fmt(p['ratio'], 1)}-krat pogosteje kot po naključju",
             f"od {p['n']} napovedi: koliko jih je največ 3 delovne dni pred ali po četrtletnem poročilu podjetja")
    fig.update_xaxes(title_text="število napovedi", range=[0, p["observed"] * 1.25])
    fig.update_layout(margin=dict(l=220))
    return fig


# ---------------------------------------------------------------------------------------- chapter 7
# Every hypothesis in plain words: the question and what we expected (both streams; the table fills in as results arrive).
HYPOTHESES = {
    1: [("C", "Imajo podjetja z napovedjo odpuščanj 2021-2023 večji padec zaposlenih?"),
        ("D", "Borza ponovljene napovedi odpuščanj kaznuje bolj kot prve?"),
        ("A", "Slovenija: je delež strokovnjakov IKT 2021-2024 zrasel bolj kot v EU?"),
        ("B", "Je po zvišanju obrestne mere San Francisco izgubil proti Austinu?")],
    2: [("C2", "Se napoved odpuščanj 2024-2025 pokaže v številu zaposlenih?"),
        ("E", "Podjetja odpuščanja napovedo ob četrtletnih poročilih?"),
        ("A2", "So države EU z več IKT leta 2021 do 2024 rasle počasneje?"),
        ("F", "Je bila rast IT 2019-2024 na vzhodni obali drugačna kot na zahodni?")],
}


def hypothesis_table(results: dict) -> pd.DataFrame:
    """One row per hypothesis: round, question, Holm p within its round, answer. A round with missing results uses the bound
    m x p (m = 4, the full family), which is never smaller than Holm's, so an answer of "da" cannot change when the rest arrive."""
    from analysis.hypotheses import holm
    rows = []
    for rnd, items in HYPOTHESES.items():
        have = {k: results[k]["primary"]["p"] for k, _ in items if k in results and results[k]["primary"].get("p") is not None}
        complete = len(have) == len(items)
        h = holm(have).set_index("hypothesis")["p_holm"] if complete and have else None
        for k, q in items:
            if k not in have:
                rows.append({"krog": rnd, "oznaka": k, "vprasanje": q, "p_holm": np.nan, "odgovor": "še računamo"})
                continue
            p = have[k]
            ph = float(h.loc[k]) if h is not None else min(1.0, len(items) * p)
            sign = results[k]["primary"].get("predicted_sign")
            if ph < ALPHA and sign is not False:
                ans = "da"
            elif ph < ALPHA:
                ans = "ne, učinek je v nasprotni smeri"
            else:
                ans = "ne moremo trditi"
            rows.append({"krog": rnd, "oznaka": k, "vprasanje": q, "p_holm": ph, "odgovor": ans})
    return pd.DataFrame(rows)


def fig_hypotheses(t: pd.DataFrame) -> go.Figure:
    fill = {"da": "rgba(76,120,168,0.18)", "še računamo": "#FFFFFF"}
    colors = [fill.get(a, "rgba(154,154,154,0.12)") for a in t["odgovor"]]
    p = ["" if np.isnan(v) else ("< 0,001" if v < 0.001 else _fmt(v, 3)) for v in t["p_holm"]]
    label = [f"<b>{k}</b> ({r}. krog)" for k, r in zip(t["oznaka"], t["krog"])]
    answers = [f"<b>{a}</b>" if a == "da" else a for a in t["odgovor"]]
    fig = go.Figure(go.Table(
        columnwidth=[1.1, 5.2, 1.1, 1.9],
        header=dict(values=["", "<b>vprašanje</b>", "<b>p</b>", "<b>odgovor</b>"], align="left",
                    fill_color=PALETTE["light_grey"], font=dict(size=14, color=PALETTE["ink"]), height=28),
        cells=dict(values=[label, t["vprasanje"], p, answers], align="left", fill_color=[colors] * 4,
                   font=dict(size=14, color=PALETTE["ink"]), height=26)))
    _layout(fig, height=420)
    n_yes, n_done = int((t["odgovor"] == "da").sum()), int((t["odgovor"] != "še računamo").sum())
    wt.title(fig, f"Od {n_done} preverjenih hipotez sta {n_yes} potrjeni" if n_yes == 2 else f"Od {n_done} preverjenih hipotez potrjenih: {n_yes}",
             "p je po popravku za štiri teste v istem krogu (Holm); »da« pomeni p < 0,05 in smer, kot smo jo napovedali")
    fig.update_layout(margin=dict(l=10, r=10, t=84, b=0))
    return fig


# ---------------------------------------------------------------------------------------- all
def build_web_figures(data: dict | None = None) -> dict[str, go.Figure]:
    """Every Stream A figure used on the site, by name."""
    from analysis import causes as cs
    data = data or prepare_web_data()
    res = data["results"]
    hc = data.get("headcount") or {}
    return {"1w_oglasi": fig_postings(data["indeed"]), "1w_ljudje": fig_people(data["quarterly"]),
            "2w_obresti": fig_rate_and_layoffs(data["macro"], data["monthly"], cs.FED_HIKE, cs.CHATGPT),
            "2w_pred_po": fig_before_after(data["studies"]), "3w_velikost": fig_size(size_deciles(data["panel"])),
            **({"3w_rast": fig_hiring(hc)} if "quartiles" in hc else {}),
            **({"4w_zaposleni": fig_c2(res["C2"])} if "C2" in res else {}),
            **({"4w_porocila": fig_e(res["E"])} if "E" in res else {}),
            "7w_hipoteze": fig_hypotheses(hypothesis_table(res))}


def facts(data: dict) -> dict:
    """The numbers the chapter text quotes, for checking the text after a re-run."""
    ind, q, ch = data["indeed"]["software"].dropna(), data["quarterly"], data["challenger"].set_index("period")
    dec = size_deciles(data["panel"])
    f = {"postings_peak": (str(ind.idxmax().date()), round(ind.max())), "postings_last": (str(ind.index[-1].date()), round(ind.iloc[-1])),
         "people_peak": q.loc[q["people"].idxmax(), ["quarter", "people"]].tolist(), "people_total": float(q["people"].sum()),
         "challenger_2023": (ch.loc["2023", "challenger"], ch.loc["2023", "tracker_us"]),
         "studies": {k: (round(v["before_mean"], 1), round(v["after_mean"], 1), round(v["ratio"], 1), round(v["rank_share"], 3))
                     for k, v in data["studies"].items()},
         "jolts": {k: (round(v["information"]["before"], 2), round(v["information"]["after"], 2)) for k, v in data["jolts"].items()},
         "size": (round(dec["share"].iloc[0], 3), round(dec["share"].iloc[-1], 3))}
    if data.get("headcount") and "quartiles" in data["headcount"]:
        f["hiring_quartiles"] = [round(r, 3) for r in data["headcount"]["quartiles"]["rate"]]
    f["hypotheses"] = hypothesis_table(data["results"])[["oznaka", "p_holm", "odgovor"]].round(4).values.tolist()
    return f


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    data = prepare_web_data()
    figs = build_web_figures(data)
    for old in OUT.glob("*.json"):
        if old.stem not in figs:
            log.info("not built any more, left in place (delete by hand if unused): %s", old.name)
    for name, fig in figs.items():
        (OUT / f"{name}.json").write_text(fig.to_json(), encoding="utf-8")
        log.info("wrote %s", OUT / f"{name}.json")
    log.info("numbers quoted in the chapters:\n%s", json.dumps(facts(data), indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
