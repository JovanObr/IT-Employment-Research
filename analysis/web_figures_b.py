"""Stream B's figures for the presentation website (web/CONTRACT.md), chapters 5 and 6. Writes web/figures/b/<name>.json.

    python -m analysis.web_figures_b

Reads only committed files, so it runs without the raw data:
  data/processed/hn_flags_monthly.csv       (python -m analysis.hn_text flags)          remote and AI shares of Hacker News posts
  data/processed/indeed_remote_monthly.csv  (python -m analysis.compare_text_geo aggregates)  Indeed remote/hybrid share, software postings
  data/processed/metro_map_data.csv         (python -m analysis.geo mapdata)            IT job growth 2019-2024 by metro
  reports/hypotheses2_b_results.json        (python -m analysis.hypotheses2_b)         A2, F and the Slovenia check B1

One message per chart: the title is the conclusion, at most two coloured series (analysis.web_theme roles), everything else grey.
The numbers in the chapter text (web/chapters/05, 06) come from `facts()`, printed by `main`. Only aggregates reach the JSON files.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from analysis import web_theme as wt
from analysis.viz_theme import PALETTE, base_layout, sl_num

log = logging.getLogger("covid_it_data")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "figures" / "b"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
ROLE = wt.ROLE

# Muro & You (2022, Brookings) groups, as in notebook 09 (analysis/compare_text_geo.py STUDY_METROS)
SUPERSTARS = {"12420": "Austin", "14460": "Boston", "42660": "Seattle", "41860": "San Francisco", "41940": "San Jose",
              "35620": "New York", "47900": "Washington", "31080": "Los Angeles"}
RISING = {"12060": "Atlanta", "19100": "Dallas", "19740": "Denver", "33100": "Miami", "36740": "Orlando", "41740": "San Diego",
          "28140": "Kansas City", "41180": "St. Louis", "41620": "Salt Lake City"}


MONTHS_SL = ("januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober", "november", "december")


def _pct(x: float, d: int = 0) -> str:
    return f"{sl_num(x, d)} %"


def _spct(x: float, d: int = 0) -> str:
    """Signed percent with a real minus sign: +33 %, −2 %."""
    return ("+" if x > 0 else "−" if x < 0 else "") + _pct(abs(x), d)


def _partial(last_month: str) -> str:
    """'2026-10' -> 'leto 2026: januar do oktober' (the last year is not complete)."""
    y, m = last_month[:4], int(last_month[5:7])
    return f"leto {y}: januar do {MONTHS_SL[m - 1]}"


def _layout(fig: go.Figure, height: int = 480) -> go.Figure:
    fig.update_layout(**base_layout(None, height=height))
    return fig


# ---------------------------------------------------------------------------------------- data
def yearly_flags(flags: pd.DataFrame) -> pd.DataFrame:
    """Share of Hacker News posts with each flag per calendar year (posts weighted: sum of flagged posts / sum of posts)."""
    f = flags.assign(year=flags["month"].astype(str).str[:4].astype(int), k=flags["share"] * flags["n_posts"])
    y = f.groupby(["year", "flag"]).agg(k=("k", "sum"), n=("n_posts", "sum"), months=("month", "nunique")).reset_index()
    y["share"] = y["k"] / y["n"]
    return y.pivot(index="year", columns="flag", values="share").assign(months=y.groupby("year")["months"].max())


def yearly_indeed(indeed: pd.DataFrame, sector: str = "techsoftware") -> pd.Series:
    """Mean monthly share (%) of Indeed postings offering remote or hybrid work, per year."""
    i = indeed[indeed["sector"] == sector]
    return i.groupby(i["month"].astype(str).str[:4].astype(int))["remote_share_pct"].mean()


def study_metros(geo: pd.DataFrame) -> pd.DataFrame:
    """Growth 2019-2024 of the named superstar and rising-star metros; withheld ones kept with NaN (counted, not drawn)."""
    g = geo.assign(cbsa_code=geo["cbsa_code"].astype(str).str.zfill(5))
    g = g.assign(usable=g["usable"].astype(str).str.lower().isin(["true", "1"]))
    rows = [{"name": n, "group": grp, "growth": (float(r["it_growth_pct"].iloc[0]) if len(r) and r["usable"].iloc[0] else np.nan)}
            for grp, d in (("vzhajajoča", RISING), ("središče", SUPERSTARS)) for c, n in d.items() for r in [g[g["cbsa_code"] == c]]]
    return pd.DataFrame(rows)


def load_inputs() -> dict:
    flags = pd.read_csv(PROCESSED / "hn_flags_monthly.csv")
    indeed = pd.read_csv(PROCESSED / "indeed_remote_monthly.csv")
    geo = pd.read_csv(PROCESSED / "metro_map_data.csv", dtype={"cbsa_code": str})
    res = json.loads((REPORTS / "hypotheses2_b_results.json").read_text(encoding="utf-8"))
    return {"flags": yearly_flags(flags), "indeed": yearly_indeed(indeed), "metros": study_metros(geo), "results": res,
            "last_month": str(flags["month"].max())}


# ---------------------------------------------------------------------------------------- chapter 5
def fig_remote(fl: pd.DataFrame, indeed: pd.Series, last_month: str) -> go.Figure:
    s = fl["remote"] * 100
    peak = int(s.idxmax())
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.round(1), mode="lines+markers", name="Hacker News", line=dict(color=ROLE["main"], width=3),
                             hovertemplate="%{x}: %{y:.0f} % objav<extra>Hacker News</extra>"))
    fig.add_trace(go.Scatter(x=indeed.index, y=indeed.round(1), mode="lines+markers", name="Indeed, programerji",
                             line=dict(color=ROLE["contrast"], width=3),
                             hovertemplate="%{x}: %{y:.0f} % oglasov<extra>Indeed</extra>"))
    _layout(fig, 480)
    wt.direct_labels(fig)
    wt.callout(fig, peak, float(s[peak]), f"vrh {peak}: {_pct(s[peak])}", ax=-70, ay=10)
    wt.title(fig, f"Delo na daljavo je po vrhu {peak} upadlo, a ostaja precej pogostejše kot leta 2019",
             f"delež objav za delo, ki ponujajo delo na daljavo ({_partial(last_month)})")
    fig.update_layout(yaxis=dict(title="delež objav (%)", rangemode="tozero"), xaxis=dict(title="", dtick=1))
    return fig


def fig_ai(fl: pd.DataFrame, last_month: str) -> go.Figure:
    s = fl["ai_ml"] * 100
    last = int(s.index.max())
    fig = go.Figure(go.Bar(x=s.index, y=s.round(1), marker_color=[ROLE["main"] if y >= 2023 else ROLE["context"] for y in s.index],
                           hovertemplate="%{x}: %{y:.0f} % objav<extra></extra>"))
    _layout(fig, 460)
    wt.callout(fig, 2022, float(s[2022]), "ChatGPT, november 2022", ax=-40, ay=-70)
    wt.title(fig, f"Umetno inteligenco danes omenja {'več kot polovica' if s[last] > 50 else _pct(s[last])} objav za delo "
                  f"({last}: {_pct(s[last])}, 2019: {_pct(s[2019])})",
             f"delež objav na Hacker News, ki omenjajo umetno inteligenco ali strojno učenje ({_partial(last_month)})")
    fig.update_layout(yaxis=dict(title="delež objav (%)", rangemode="tozero"), xaxis=dict(title="", dtick=1), showlegend=False)
    return fig


# ---------------------------------------------------------------------------------------- chapter 6
def fig_regions(m: pd.DataFrame) -> go.Figure:
    d = m.dropna(subset=["growth"]).sort_values("growth")
    color = {"vzhajajoča": ROLE["main"], "središče": ROLE["contrast"]}
    fig = go.Figure()
    for grp, label in (("vzhajajoča", "hitro rastoča mesta"), ("središče", "velika tehnološka središča")):
        s = d[d["group"] == grp]
        fig.add_trace(go.Bar(x=s["growth"].round(1), y=s["name"], orientation="h", name=label, marker_color=color[grp],
                             hovertemplate="%{y}: %{x:.0f} %<extra>" + label + "</extra>"))
    _layout(fig, 520)
    med = d.groupby("group")["growth"].median()
    wt.title(fig, f"IT delovna mesta so rasla v hitro rastočih mestih (srednje {_spct(med['vzhajajoča'])}), "
                  f"v velikih središčih skoraj ne ({_spct(med['središče'])})",
             "sprememba števila delovnih mest v IT storitvah 2019 → 2024; skupini po študiji Brookings (2022)")
    fig.update_layout(xaxis=dict(title="sprememba (%)", zeroline=True), yaxis=dict(title="", categoryorder="array",
                      categoryarray=list(d["name"])), barmode="overlay", bargap=0.25,
                      legend=dict(orientation="h", y=-0.15, x=0))
    return fig


def fig_coasts(f: dict) -> go.Figure:
    m = pd.DataFrame(f["metros"])
    p = f["primary"]
    fig = go.Figure()
    for coast, name, color in (("west", "zahodna obala", ROLE["contrast"]), ("east", "vzhodna obala", ROLE["main"])):
        s = m[m["coast"] == coast]
        med = float(s["growth"].median())
        fig.add_trace(go.Box(x=s["growth"].clip(-75, 150).round(1), name=f"{name}<br>({len(s)} mest)", boxpoints="all", jitter=0.5,
                             pointpos=0, orientation="h", marker=dict(color=color, size=6, opacity=0.6), line=dict(color=color),
                             fillcolor="rgba(0,0,0,0)", text=[n.replace(" Metro Area", "").replace(" Micro Area", "") for n in s["name"]],
                             hovertemplate="%{text}: %{x:.0f} %<extra></extra>"))
        fig.add_annotation(x=med, y=f"{name}<br>({len(s)} mest)", text=f"srednje {_pct(med)}", showarrow=False, yshift=34,
                           font=dict(color=color))
    _layout(fig, 460)
    more = "počasneje" if p["diff_median"] < 0 else "hitreje"
    wt.title(fig, f"Zahodna obala je rasla {more} od vzhodne, a razlika je lahko naključje",
             "sprememba števila delovnih mest v IT storitvah 2019 → 2024 po mestih (odrezano pri −75 % in 150 %)")
    fig.update_layout(xaxis=dict(title="sprememba (%)", zeroline=True), yaxis=dict(title=""), showlegend=False)
    return fig


def fig_slovenia(b1: dict) -> go.Figure:
    s = pd.DataFrame(b1["series"])
    br = b1["break_year"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["year"], y=s["max"], mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=s["year"], y=s["min"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(229,229,229,0.7)",
                             name="druge države EU", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=s["year"], y=s["eu27"], mode="lines", line=dict(color=ROLE["contrast"], width=3), name="povprečje EU",
                             hovertemplate="EU %{x}: %{y:.1f} %<extra></extra>"))
    fig.add_trace(go.Scatter(x=s["year"], y=s["si"], mode="lines+markers", line=dict(color=ROLE["main"], width=3), name="Slovenija",
                             hovertemplate="Slovenija %{x}: %{y:.1f} %<extra></extra>"))
    _layout(fig, 480)
    wt.direct_labels(fig)
    low = s.loc[s["year"] > br].sort_values("si").iloc[0]
    wt.callout(fig, int(low["year"]), float(low["si"]), f"{int(low['year'])}: {sl_num(low['si'], 1)} %", ax=30, ay=40)
    fig.add_annotation(x=br - 0.5, y=1, yref="paper", text="nova metoda ankete", showarrow=False, xanchor="right", yanchor="top",
                       textangle=-90, font=dict(color=PALETTE["grey"]))
    fig.add_shape(type="line", x0=br - 0.5, x1=br - 0.5, y0=0, y1=1, yref="paper", line=dict(color=PALETTE["grey"], width=1, dash="dot"))
    r21 = s.loc[s["year"] == br].iloc[0]
    last = s.iloc[-1]
    head = (f"Slovenija je bila leta {br} nad povprečjem EU, nato je padla pod njega" if r21["si"] > r21["eu27"] and last["si"] < last["eu27"]
            else f"Slovenija je {'nad' if last['si'] > last['eu27'] else 'pod'} povprečjem EU")
    wt.title(fig, head, "delež strokovnjakov za informacijske tehnologije med vsemi zaposlenimi (%); siva: razpon drugih 26 držav")
    fig.update_layout(yaxis=dict(title="delež zaposlenih (%)"), xaxis=dict(title="", dtick=2))
    return fig


def fig_catch_up(a2: dict) -> go.Figure:
    v = pd.DataFrame(a2["values"]).T
    p, s = a2["primary"], a2["slovenia"]
    o = v.drop("SI")
    xs = np.array([v["start"].min(), v["start"].max()])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=p["intercept"] + p["b"] * xs, mode="lines", line=dict(color=ROLE["context"], width=2, dash="dash"),
                             name="skupni trend", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=o["start"].round(2), y=o["change"].round(2), mode="markers", marker=dict(color=ROLE["context"], size=10),
                             name="druge države EU", text=list(o.index), hovertemplate="%{text}: %{x:.1f} % → %{y:+.1f} točke<extra></extra>"))
    fig.add_trace(go.Scatter(x=[round(s["start"], 2)], y=[round(s["change"], 2)], mode="markers", marker=dict(color=ROLE["main"], size=14),
                             name="Slovenija", hovertemplate="Slovenija: %{x:.1f} % → %{y:+.1f} točke<extra></extra>"))
    _layout(fig, 480)
    wt.callout(fig, s["start"], s["change"], f"Slovenija: pričakovano {sl_num(s['predicted_change'], 1)}, dejansko {sl_num(s['change'], 1)}",
               ax=70, ay=30)
    weak = abs(p["r"]) < 0.2
    wt.title(fig, "Kje je država začela, skoraj ne vpliva na to, koliko je zrasla" if weak else
             ("Države z višjim izhodiščem so rasle počasneje" if p["b"] < 0 else "Države z višjim izhodiščem so rasle hitreje"),
             "vodoravno: delež strokovnjakov IT 2019-2020 (%); navpično: sprememba 2021 → 2024 (odstotne točke)")
    fig.update_layout(xaxis=dict(title="izhodišče (%)"), yaxis=dict(title="sprememba (točke)", zeroline=True), showlegend=False)
    return fig


# ---------------------------------------------------------------------------------------- all
def build_web_figures(data: dict | None = None) -> dict[str, go.Figure]:
    """Every Stream B figure used on the site, by name."""
    data = data or load_inputs()
    res = data["results"]
    return {"5w_daljava": fig_remote(data["flags"], data["indeed"], data["last_month"]),
            "5w_ui": fig_ai(data["flags"], data["last_month"]),
            "6w_regije": fig_regions(data["metros"]),
            **({"6w_obali": fig_coasts(res["F"])} if "F" in res else {}),
            **({"6w_slovenija": fig_slovenia(res["B1"])} if "B1" in res else {}),
            **({"6w_dohitevanje": fig_catch_up(res["A2"])} if "A2" in res else {})}


def facts(data: dict) -> dict:
    """The numbers the chapter text quotes, for checking the text after a re-run."""
    fl, ind, m, res = data["flags"], data["indeed"], data["metros"], data["results"]
    pct = lambda x: round(100 * float(x), 1)
    f = {"remote_hn": {int(y): pct(fl.at[y, "remote"]) for y in (2019, int(fl["remote"].idxmax()), int(fl.index.max()))},
         "remote_indeed_software": {int(y): round(float(ind[y]), 1) for y in (2019, int(ind.idxmax()), int(ind.index.max()))},
         "ai_hn": {int(y): pct(fl.at[y, "ai_ml"]) for y in (2019, 2022, 2023, int(fl.index.max()))},
         "last_month": data["last_month"],
         "metros_median": m.dropna().groupby("group")["growth"].median().round(1).to_dict(),
         "metros_withheld": m.loc[m["growth"].isna(), "name"].tolist(),
         "metros": m.dropna().set_index("name")["growth"].round(1).to_dict()}
    if "F" in res:
        p = res["F"]["primary"]
        f["F"] = {k: (round(p[k], 3) if isinstance(p[k], float) else p[k]) for k in
                  ("n_west", "n_east", "n_withheld_east", "n_withheld_west", "median_west", "median_east", "diff_median", "ci_lo", "ci_hi", "p")}
    if "A2" in res:
        p, s = res["A2"]["primary"], res["A2"]["slovenia"]
        f["A2"] = {"b": round(p["b"], 3), "ci": (round(p["ci_lo"], 3), round(p["ci_hi"], 3)), "p": round(p["p"], 3),
                   "si_start_rank": s["start_rank"], "si_predicted": round(s["predicted_change"], 2), "si_change": s["change"]}
    if "B1" in res:
        b1 = res["B1"]
        sr = pd.DataFrame(b1["series"]).set_index("year")
        f["B1"] = {"si": sr["si"].to_dict(), "eu27": sr["eu27"].to_dict(), "rank": b1["rank"], "change": b1["change_2021_2024"],
                   "earlier": b1["earlier_rise"], "thousands": {r["year"]: r["si"] for r in b1["thousands"]}}
    return f


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_inputs()
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
