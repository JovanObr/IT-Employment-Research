"""Notebook 09 (Stream B part): Hacker News (chapter 4) and geography (chapter 5) beside published studies.

Same shape as Stream A's analysis/compare_viz.py: every comparison is (figure, explanation, verdict)
* explanation: the four Slovenian parts kaj / zakaj / pomen / omejitve, numbers computed from the data, their number beside ours;
* verdict: one row {tema, studija, njihov_rezultat, nas_rezultat, ocena} for notebook 09's table, ocena chosen by a rule from the numbers.

Figures (names prefixed 9b_):
  9b_daljava_primerjava  remote work: our HN share and Indeed's US share indexed to 2019 = 1, beside Hansen et al. (2026) "more than 3x"
  9b_ui_primerjava       AI: HN AI/ML share and HN post count on one time axis, beside Bernard (2025): ML postings +59 %, software -49 %
  9b_mladi               junior hiring, ONLY when hn_flags_monthly.csv holds junior_v2 (i.e. it passed the D1 decision rule)
  9b_regije_primerjava   metros named by Bernard (2025) and Muro & You (2022): our IT job growth 2019-2024 beside their numbers

Published numbers were copied from the study pages on 2026-11-10 (see STUDIES); they are typed in, not read from a CSV.
Committed aggregates read here (no raw text):
  data/processed/hn_flags_monthly.csv      python -m analysis.hn_text flags
  data/processed/indeed_remote_monthly.csv python -m analysis.compare_text_geo aggregates   (from data/raw/indeed_remote_postings.csv)
  data/processed/metro_map_data.csv        python -m analysis.geo mapdata

    python -m analysis.compare_text_geo aggregates   # monthly Indeed remote shares (needs collect.py --sources indeed_remote)
    python -m analysis.compare_text_geo preview      # writes reports/figures_sl/preview_9b_*.html
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.viz_text_geo import _flag_series, _metro_label, _read, load_flags, load_map_data
from analysis.viz_theme import EVENTS, HOVER_MONTH, PALETTE, add_event_lines, base_layout, save_html, sl_num, sl_pct
from collectors import common

log = logging.getLogger("covid_it_data")
VERDICTS = ("se ujema", "delno", "se razlikuje", "ni primerljivo")
VERDICT_KEYS = ("tema", "studija", "njihov_rezultat", "nas_rezultat", "ocena")
CHATGPT = EVENTS["chatgpt"][0]

# ---------------------------------------------------------------------------------------- published numbers (checked 2026-11-10)
STUDIES = {
    "hansen": dict(
        cite="Hansen, Lambert, Bloom, Davis, Muvdi, Sadun in Taska (2026), »Remote Work Across Jobs, Companies and Space«, "
             "Dallas Fed WP 2629",
        url="https://doi.org/10.24149/wp2629",
        ratio_min=3.0,                       # "rose more than three-fold in the U.S." (2019 to 2026), remote = at least one day a week
    ),
    "bernard": dict(
        cite="Bernard (2025), Indeed Hiring Lab, »The US Tech Hiring Freeze Continues«",
        url="https://hiringlab.indeed.com/2025/07/30/the-us-tech-hiring-freeze-continues/",
        ml_pct=59.0,                         # Machine Learning Engineer postings, early 2025 vs early 2020
        swe_pct=-49.0,                       # software engineer postings, same periods
        tech_pct=-36.0,                      # all tech postings, early July 2025 vs early 2020
    ),
    "acemoglu": dict(cite="Acemoglu, Autor, Hazell in Restrepo (2022), »AI and Jobs: Evidence from Online Vacancies«, "
                          "Journal of Labor Economics"),
    "muro": dict(
        cite="Muro in You (2022), Brookings, »Superstars, rising stars, and the rest«",
        url="https://www.brookings.edu/articles/superstars-rising-stars-and-the-rest-pandemic-trends-and-shifts-in-the-geography-of-tech/",
    ),
    "stanford": dict(
        cite="Brynjolfsson, Chandar in Chen (2025, dopolnjeno 2026), »Canaries in the Coal Mine?«, Stanford Digital Economy Lab",
        url="https://digitaleconomy.stanford.edu/publications/canaries-in-the-coal-mine/",
        young_gap_pct=-19.0,                 # 22-25 year olds in AI-exposed jobs vs less exposed peers (page revised 12 Aug 2026)
    ),
}

# Metros named in the studies. indeed = tech postings change early 2020 -> early 2025 (Bernard 2025); bound = "fell more than 40 %"
# (Bernard names Seattle, Minneapolis and San Francisco without an exact number). group = Muro & You (2022) category.
SUPER, RISING = "superzvezda", "vzhajajoča zvezda"
STUDY_METROS = pd.DataFrame([
    # name,          cbsa,    indeed, bound, group
    ("Austin",        "12420", -28.0, False, SUPER),
    ("Boston",        "14460", -51.0, False, SUPER),
    ("Seattle",       "42660", -40.0, True, SUPER),
    ("San Francisco", "41860", -40.0, True, SUPER),
    ("San Jose",      "41940", np.nan, False, SUPER),
    ("New York",      "35620", np.nan, False, SUPER),
    ("Washington",    "47900", np.nan, False, SUPER),
    ("Los Angeles",   "31080", np.nan, False, SUPER),
    ("Minneapolis",   "33460", -40.0, True, None),
    ("Atlanta",       "12060", np.nan, False, RISING),
    ("Dallas",        "19100", np.nan, False, RISING),
    ("Denver",        "19740", np.nan, False, RISING),
    ("Miami",         "33100", np.nan, False, RISING),
    ("Orlando",       "36740", np.nan, False, RISING),
    ("San Diego",     "41740", np.nan, False, RISING),
    ("Kansas City",   "28140", np.nan, False, RISING),
    ("St. Louis",     "41180", np.nan, False, RISING),
    ("Salt Lake City", "41620", np.nan, False, RISING),
], columns=["name", "cbsa_code", "indeed_pct", "indeed_bound", "group"])

INDEED_SECTORS = {"all": "Indeed, vsi oglasi v ZDA", "techsoftware": "Indeed, oglasi za razvoj programske opreme"}


# ---------------------------------------------------------------------------------------- small helpers
def _mm(d: pd.Timestamp) -> str:
    return f"{d.month}/{d.year}"


def _signed(x: float, digits: int = 0, unit: str = " %") -> str:
    return f"{'+' if x >= 0 else '−'}{sl_num(abs(x), digits)}{unit}"


def _times(x: float) -> str:
    return f"{sl_num(x, 1)}-krat"


def _pairs(n: int) -> str:
    """Slovenian noun form after a number: 1 par, 2 para, 3 in 4 pari, 5 in več parov."""
    return f"{n} " + ("par" if n % 100 == 1 else "para" if n % 100 == 2 else "pari" if n % 100 in (3, 4) else "parov")


def _months_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return abs((a.year - b.year) * 12 + a.month - b.month)


def _year_mean(s: pd.Series, year: int) -> float:
    v = s[s.index.year == year]
    return float(v.mean()) if len(v) else float("nan")


def _window_mean(s: pd.Series, start: str, end: str) -> float:
    v = s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
    return float(v.mean()) if len(v) else float("nan")


def _pct_change(a: float, b: float) -> float:
    return (b / a - 1) * 100 if a and np.isfinite(a) and np.isfinite(b) else float("nan")


def check_verdict(row: dict) -> dict:
    missing = [k for k in VERDICT_KEYS if not str(row.get(k, "")).strip()]
    if missing or row["ocena"] not in VERDICTS:
        raise ValueError(f"verdict {row.get('tema')!r}: missing {missing} or bad ocena {row.get('ocena')!r}")
    return row


# ---------------------------------------------------------------------------------------- aggregates (Indeed remote tracker)
def indeed_remote_monthly(raw: pd.DataFrame, sectors=tuple(INDEED_SECTORS)) -> pd.DataFrame:
    """Daily US shares (data/raw/indeed_remote_postings.csv) -> month (YYYY-MM), sector, remote_share_pct (mean of the days), n_days."""
    d = raw[raw["sector"].isin(sectors)].copy()
    d["month"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m")
    out = d.groupby(["sector", "month"])["remote_share_pct"].agg(["mean", "size"]).reset_index()
    out.columns = ["sector", "month", "remote_share_pct", "n_days"]
    return out[["month", "sector", "remote_share_pct", "n_days"]].sort_values(["sector", "month"]).reset_index(drop=True)


def write_aggregates() -> Path:
    src = common.RAW / "indeed_remote_postings.csv"
    if not src.exists():
        raise FileNotFoundError(f"{src} manjka (missing). Create it with: python collect.py --sources indeed_remote")
    out = common.PROCESSED / "indeed_remote_monthly.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    indeed_remote_monthly(pd.read_csv(src)).to_csv(out, index=False)
    return out


def load_indeed_remote() -> pd.DataFrame:
    return _read("indeed_remote_monthly.csv", "python collect.py --sources indeed_remote, then python -m analysis.compare_text_geo aggregates")


def _indeed_series(indeed: pd.DataFrame | None, sector: str) -> pd.Series:
    if indeed is None or len(indeed) == 0:
        return pd.Series(dtype=float)
    d = indeed[indeed["sector"] == sector]
    return pd.Series(d["remote_share_pct"].to_numpy(dtype=float) / 100, index=pd.to_datetime(d["month"]), name=sector).sort_index().dropna()


# ---------------------------------------------------------------------------------------- 1. remote work
def remote_summary(flags: pd.DataFrame, indeed: pd.DataFrame | None, base_year: int = 2019) -> dict:
    """Per series (hn, Indeed sectors): share in base_year, in the last calendar year with data, ratio, peak month and value."""
    out = {}
    series = {"hn": _flag_series(flags, "remote")}
    series.update({k: _indeed_series(indeed, k) for k in INDEED_SECTORS})
    for k, s in series.items():
        if s.empty:
            continue
        last_year = int(s.index.max().year)
        b, e = _year_mean(s, base_year), _year_mean(s, last_year)
        out[k] = {"series": s, "base": b, "end": e, "end_year": last_year, "ratio": e / b if b and np.isfinite(b) else float("nan"),
                  "peak": s.idxmax(), "peak_share": float(s.max()), "base_year": base_year}
    return out


def fig_remote_compare(flags: pd.DataFrame, indeed: pd.DataFrame | None = None) -> go.Figure:
    """Our HN remote share and Indeed's US shares, each divided by its own 2019 average (2019 = 1), with Hansen et al.'s 'more than 3x'."""
    summ = remote_summary(flags, indeed)
    fig = go.Figure()
    styles = {"hn": ("Hacker News (naši podatki)", PALETTE["blue"], 2.6, "solid"),
              "all": (INDEED_SECTORS["all"], PALETTE["orange"], 2.0, "solid"),
              "techsoftware": (INDEED_SECTORS["techsoftware"], PALETTE["red"], 1.6, "dot")}
    x_end = None
    for k, (name, col, width, dash) in styles.items():
        if k not in summ or not np.isfinite(summ[k]["base"]):
            continue
        r = summ[k]
        idx = r["series"] / r["base"]
        x_end = max(x_end, idx.index.max()) if x_end is not None else idx.index.max()
        share_txt = [sl_pct(v, 1) for v in r["series"]]
        fig.add_trace(go.Scatter(x=idx.index, y=idx, mode="lines", name=name, line=dict(color=col, width=width, dash=dash),
                                 customdata=share_txt,
                                 hovertemplate=f"<b>{name}</b><br>%{{x|{HOVER_MONTH}}}: %{{y:.2f}}-krat raven 2019 "
                                               "(delež %{customdata})<extra></extra>"))
    h = STUDIES["hansen"]
    if x_end is not None:
        x0 = pd.Timestamp(f"{x_end.year}-01-01")
        fig.add_shape(type="rect", xref="x", yref="y", x0=x0, x1=x_end + pd.offsets.MonthEnd(0), y0=h["ratio_min"],
                      y1=h["ratio_min"] * 1.25, fillcolor="rgba(34,34,34,0.12)", line=dict(width=0))
        fig.add_shape(type="line", xref="x", yref="y", x0=x0, x1=x_end + pd.offsets.MonthEnd(0), y0=h["ratio_min"], y1=h["ratio_min"],
                      line=dict(color=PALETTE["ink"], width=2))
        fig.add_annotation(xref="x", yref="y", x=x0, y=h["ratio_min"] * 1.25, xanchor="right", yanchor="bottom", showarrow=False,
                           align="right", font=dict(size=11),
                           text=f"Hansen in sod. (2026): ZDA {x_end.year} več kot<br>{sl_num(h['ratio_min'], 0)}-krat raven 2019")
    fig.add_hline(y=1, line=dict(color=PALETTE["grey"], width=1, dash="dot"))
    fig.update_layout(**base_layout("Delo na daljavo v oglasih: koliko krat več kot leta 2019", height=500))
    fig.update_layout(yaxis=dict(title="delež oglasov z delom na daljavo (2019 = 1)", rangemode="tozero"), xaxis=dict(tickformat="%Y"),
                      hovermode="closest")
    add_event_lines(fig, keys=("covid", "chatgpt"))
    return fig


def explain_remote_compare(flags: pd.DataFrame, indeed: pd.DataFrame | None = None) -> dict:
    s = remote_summary(flags, indeed)
    h = STUDIES["hansen"]
    hn = s.get("hn")
    if hn is None or not np.isfinite(hn["base"]):
        pomen = "V naših podatkih ni leta 2019, zato primerjave z letom 2019 ne moremo narediti."
    else:
        direction = "isto smer kot študija (navzgor)" if hn["ratio"] > 1 else "nasprotno smer kot študija"
        pomen = (f"Hansen in sodelavci (2026, Dallas Fed) poročajo, da se je v ZDA delež oglasov, ki dovolijo delo na daljavo, od 2019 do "
                 f"2026 povečal za več kot {sl_num(h['ratio_min'], 0)}-krat. Na Hacker Newsu je delež šel z {sl_pct(hn['base'])} (2019) na {sl_pct(hn['end'])} "
                 f"({hn['end_year']}), to je {_times(hn['ratio'])}: {direction}, a manj kot {sl_num(h['ratio_min'], 0)}-krat. ")
        ind = s.get("all")
        if ind is not None and np.isfinite(ind["base"]):
            gap = _months_between(hn["peak"], ind["peak"])
            pomen += (f"Indeedova serija za vse oglase v ZDA je šla z {sl_pct(ind['base'], 1)} na {sl_pct(ind['end'], 1)}, kar je "
                      f"{_times(ind['ratio'])} in se z ugotovitvijo študije ujema. Vrh je bil na Indeedu {_mm(ind['peak'])} "
                      f"({sl_pct(ind['peak_share'], 1)}), na Hacker Newsu {_mm(hn['peak'])} ({sl_pct(hn['peak_share'])}), "
                      + ("torej v istem mesecu. " if gap == 0 else f"torej skoraj istočasno (razlika {gap} mes.). " if gap <= 12
                         else f"torej {gap} mesecev narazen. "))
            pomen += (f"Raven na Hacker Newsu je bila že leta 2019 {_times(hn['base'] / ind['base'])} višja kot na Indeedu: tam oglašujejo "
                      "zagonska tehnološka podjetja, kjer je delo na daljavo pogosto že od nekdaj, Indeed pa zajema vse poklice, tudi tiste, ki "
                      "jih na daljavo ni mogoče opravljati. Ker je izhodišče visoko, se delež ne more več potrojiti.")
            sw = s.get("techsoftware")
            if sw is not None and np.isfinite(sw["base"]):
                pomen += (f" Med Indeedovimi oglasi za razvoj programske opreme je delež šel z {sl_pct(sw['base'], 1)} na "
                          f"{sl_pct(sw['end'], 1)} ({_times(sw['ratio'])}).")
        else:
            pomen += "Indeedove serije ni bilo mogoče prebrati, zato vrha ne moremo primerjati."
    return {
        "kaj": "Vsaka črta je delež oglasov, ki omenjajo delo na daljavo, deljen s svojim povprečjem iz leta 2019: vrednost 2 pomeni dvakrat "
               "več kot leta 2019. Modra so naši podatki s Hacker Newsa, oranžna Indeedovi oglasi za vse poklice v ZDA, rdeča pikčasta "
               "Indeedovi oglasi za razvoj programske opreme. Sivi pas desno je ugotovitev študije: več kot trikratnik ravni iz leta 2019.",
        "zakaj": "Raziskovalci (Hansen in sod. 2026) so pregledali stotine milijonov oglasov in ugotovili, da se je delo na daljavo v ZDA "
                 "ustalilo na več kot trikratni ravni iz leta 2019. Preverili smo, ali naši podatki kažejo isto smer, isti čas vrha in zakaj je "
                 "naša raven drugačna.",
        "pomen": pomen,
        "omejitve": "Vsi trije viri štejejo oglase po ključnih besedah, vendar ne enako: študija šteje oglase, ki dovolijo delo od doma vsaj "
                    "en dan na teden (tudi hibridno), Indeed šteje omembe dela na daljavo ali hibridnega dela, naša oznaka pa vsako omembo "
                    "besede »remote«, tudi »no remote«. Hacker News predstavlja predvsem zagonska podjetja. Delež v oglasih ne pove, koliko "
                    "ljudi dejansko dela od doma. Leto 2026 še ni končano.",
    }


def verdict_remote_compare(flags: pd.DataFrame, indeed: pd.DataFrame | None = None) -> dict:
    """se ujema: our ratio >= 2/3 of theirs and peak within 12 months of Indeed's; delno: same direction (ratio > 1.1); else se razlikuje."""
    s = remote_summary(flags, indeed)
    h = STUDIES["hansen"]
    hn, ind = s.get("hn"), s.get("all")
    if hn is None or not np.isfinite(hn["ratio"]):
        return check_verdict({"tema": "Delo na daljavo", "studija": "Hansen in sod. (2026), Dallas Fed", "njihov_rezultat": "več kot 3-krat",
                              "nas_rezultat": "ni podatka za 2019", "ocena": "ni primerljivo"})
    close_peak = ind is not None and _months_between(hn["peak"], ind["peak"]) <= 12
    ocena = ("se ujema" if hn["ratio"] >= h["ratio_min"] * 2 / 3 and close_peak else "delno" if hn["ratio"] > 1.1 else "se razlikuje")
    ours = f"Hacker News {_times(hn['ratio'])} (2019-{hn['end_year']}), vrh {_mm(hn['peak'])}"
    if ind is not None and np.isfinite(ind["ratio"]):
        ours += f"; Indeed {_times(ind['ratio'])}, vrh {_mm(ind['peak'])}"
    return check_verdict({"tema": "Delo na daljavo", "studija": "Hansen in sod. (2026), Dallas Fed WP 2629",
                          "njihov_rezultat": f"delež oglasov ZDA 2019-2026 več kot {sl_num(h['ratio_min'], 0)}-krat",
                          "nas_rezultat": ours, "ocena": ocena})


# ---------------------------------------------------------------------------------------- 2. AI
EARLY_2020 = ("2020-01-01", "2020-03-01")
EARLY_2025 = ("2025-01-01", "2025-03-01")


def ai_summary(flags: pd.DataFrame) -> dict:
    """AI/ML share and post counts; changes early 2020 -> early 2025 (Bernard's periods) for all posts and AI-mentioning posts."""
    ai = _flag_series(flags, "ai_ml")
    f = flags[flags["flag"] == "ai_ml"]
    n = pd.Series(f["n_posts"].to_numpy(dtype=float), index=pd.to_datetime(f["month"])).sort_index()
    ai_posts = (ai * n.reindex(ai.index)).dropna()
    w0, w1 = EARLY_2020, EARLY_2025
    if not np.isfinite(_window_mean(n, *w0)) or not np.isfinite(_window_mean(n, *w1)):
        idx = n.index
        w0 = (idx[0].strftime("%Y-%m-%d"), idx[min(2, len(idx) - 1)].strftime("%Y-%m-%d"))
        w1 = (idx[max(0, len(idx) - 3)].strftime("%Y-%m-%d"), idx[-1].strftime("%Y-%m-%d"))
    out = {"ai": ai, "n": n, "w0": w0, "w1": w1,
           "share0": _window_mean(ai, *w0), "share1": _window_mean(ai, *w1),
           "n0": _window_mean(n, *w0), "n1": _window_mean(n, *w1),
           "ai0": _window_mean(ai_posts, *w0), "ai1": _window_mean(ai_posts, *w1),
           "first12": float(ai.iloc[:12].mean()) if len(ai) else float("nan"),
           "last12": float(ai.iloc[-12:].mean()) if len(ai) else float("nan"),
           "n_peak": n.idxmax() if len(n) else None}
    out["n_change"] = _pct_change(out["n0"], out["n1"])
    out["ai_change"] = _pct_change(out["ai0"], out["ai1"])
    return out


def _period(w: tuple[str, str]) -> str:
    a, b = pd.Timestamp(w[0]), pd.Timestamp(w[1])
    return f"{_mm(a)}-{_mm(b)}"


def fig_ai_compare(flags: pd.DataFrame) -> go.Figure:
    """Bars: HN posts per month (right axis). Line: share of posts mentioning AI/ML (left axis). Shaded: Bernard's two periods."""
    s = ai_summary(flags)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=s["n"].index, y=s["n"], name="vse objave na mesec (leva os)", marker_color=PALETTE["light_grey"],
                         hovertemplate=f"%{{x|{HOVER_MONTH}}}: %{{y:.0f}} objav<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=s["ai"].index, y=s["ai"] * 100, mode="lines", name="delež objav, ki omenjajo UI (desna os)",
                             line=dict(color=PALETTE["purple"], width=2.4),
                             hovertemplate=f"%{{x|{HOVER_MONTH}}}: %{{y:.1f}} % objav<extra></extra>"), secondary_y=True)   # right axis: drawn above the bars
    for w, label in ((s["w0"], "začetek 2020"), (s["w1"], "začetek 2025")):
        x0, x1 = pd.Timestamp(w[0]), pd.Timestamp(w[1]) + pd.offsets.MonthEnd(0)
        fig.add_shape(type="rect", xref="x", yref="paper", x0=x0, x1=x1, y0=0, y1=1, fillcolor="rgba(245,133,24,0.15)", line=dict(width=0))
        fig.add_annotation(xref="x", yref="paper", x=x0, y=1, yanchor="bottom", showarrow=False, text=label, font=dict(size=10))
    b = STUDIES["bernard"]
    fig.update_layout(**base_layout("Umetna inteligenca: vedno večji delež vedno manj objav", height=500), bargap=0)
    fig.update_yaxes(title_text="objav na mesec", rangemode="tozero", showgrid=False, secondary_y=False)
    fig.update_yaxes(title_text="delež objav z omembo UI (%)", rangemode="tozero", tickmode="linear", tick0=0, dtick=10, secondary_y=True)
    fig.update_layout(margin=dict(b=130), legend=dict(y=-0.1))
    fig.update_xaxes(tickformat="%Y")
    fig.add_annotation(xref="paper", yref="paper", x=0, y=-0.3, xanchor="left", showarrow=False, align="left", font=dict(size=10),
                       text=f"Oranžna pasova = obdobji, ki ju primerja Bernard (2025): oglasi za inženirje strojnega učenja "
                            f"{_signed(b['ml_pct'])}, za programske inženirje {_signed(b['swe_pct'])}.")
    add_event_lines(fig, keys=("chatgpt",))
    return fig


def explain_ai_compare(flags: pd.DataFrame) -> dict:
    s = ai_summary(flags)
    b = STUDIES["bernard"]
    p0, p1 = _period(s["w0"]), _period(s["w1"])
    if not all(np.isfinite([s["n_change"], s["ai_change"]])):
        pomen = "Za obdobji, ki ju primerja študija, nimamo dovolj podatkov."
    else:
        same_all = (s["n_change"] < 0) == (b["swe_pct"] < 0)
        same_ai = (s["ai_change"] > 0) == (b["ml_pct"] > 0)
        pomen = (f"Bernard (2025) je na Indeedu izmeril, da se je od začetka leta 2020 do začetka leta 2025 število oglasov za inženirje "
                 f"strojnega učenja spremenilo za {_signed(b['ml_pct'])}, oglasov za programske inženirje pa za {_signed(b['swe_pct'])}. "
                 f"Na Hacker Newsu je bilo v istih mesecih ({p0} proti {p1}) vseh objav {_signed(s['n_change'])}, objav, ki omenjajo UI, pa "
                 f"{_signed(s['ai_change'])}; delež objav z UI je šel z {sl_pct(s['share0'])} na {sl_pct(s['share1'])}. ")
        if same_all and same_ai:
            pomen += "Oba vira torej kažeta isto sliko: skupno povpraševanje pada, delo z UI pa raste."
        elif same_all:
            pomen += "Skupni upad se ujema, število objav z UI pa pri nas ni raslo kot pri Indeedu; raste le njihov delež."
        elif same_ai:
            pomen += "Objave z UI rastejo kot pri Indeedu, skupno število objav pa pri nas ni padlo."
        else:
            pomen += "Naši podatki v teh mesecih ne kažejo iste slike kot Indeed."
        pomen += (f" Celotno obdobje: delež UI v prvih 12 mesecih {sl_pct(s['first12'])}, v zadnjih 12 mesecih {sl_pct(s['last12'])}.")
    return {
        "kaj": "Sivi stolpci so število vseh objav v mesečni niti »Who is hiring?« (leva os), vijolična črta pa delež objav, ki omenjajo "
               "umetno inteligenco ali strojno učenje (desna os). Oranžna pasova označujeta prve tri mesece let 2020 in 2025, ki ju primerja študija.",
        "zakaj": "Bernard (2025, Indeed Hiring Lab) je ugotovil, da se je zaposlovanje v tehnologiji ohladilo povsod razen pri vlogah z UI. "
                 "Že Acemoglu, Autor, Hazell in Restrepo (2022) so iz ameriških oglasov pokazali, da podjetja, kjer je veliko nalog primernih "
                 "za UI, objavljajo več oglasov za UI in manj drugih oglasov. Preverili smo, ali Hacker News kaže isto.",
        "pomen": pomen,
        "omejitve": "Indeed šteje oglase po nazivu delovnega mesta (»Machine Learning Engineer«), mi pa objave, ki kjerkoli omenijo UI, "
                    "strojno učenje ali LLM; podjetje, ki samo napiše, da uporablja UI, šteje kot omemba. Ena objava na Hacker Newsu pogosto "
                    "išče več ljudi. Število objav kaže tudi, koliko je nit priljubljena, ne le koliko podjetja zaposlujejo.",
    }


def verdict_ai_compare(flags: pd.DataFrame) -> dict:
    """se ujema: all posts down AND AI posts up (as in Bernard); delno: one of the two; se razlikuje: neither."""
    s = ai_summary(flags)
    b = STUDIES["bernard"]
    if not all(np.isfinite([s["n_change"], s["ai_change"]])):
        ocena, ours = "ni primerljivo", "ni podatkov za ista obdobja"
    else:
        hits = int((s["n_change"] < 0) == (b["swe_pct"] < 0)) + int((s["ai_change"] > 0) == (b["ml_pct"] > 0))
        ocena = {2: "se ujema", 1: "delno", 0: "se razlikuje"}[hits]
        ours = (f"vse objave {_signed(s['n_change'])}, objave z UI {_signed(s['ai_change'])} "
                f"(delež {sl_pct(s['share0'])} na {sl_pct(s['share1'])})")
    return check_verdict({"tema": "Umetna inteligenca", "studija": "Bernard (2025), Indeed Hiring Lab; Acemoglu in sod. (2022)",
                          "njihov_rezultat": f"strojno učenje {_signed(b['ml_pct'])}, programski inženirji {_signed(b['swe_pct'])} "
                                             "(začetek 2020 do začetka 2025)",
                          "nas_rezultat": ours, "ocena": ocena})


# ---------------------------------------------------------------------------------------- 3. junior hiring (only if junior_v2 passed D1)
def has_junior_v2(flags: pd.DataFrame) -> bool:
    return bool((flags["flag"] == "junior_v2").any())


def youth_summary(flags: pd.DataFrame) -> dict:
    s = _flag_series(flags, "junior_v2")
    pre = s[(s.index > CHATGPT - pd.DateOffset(months=12)) & (s.index <= CHATGPT)]
    post = s.iloc[-12:]
    a, b = float(pre.mean()) if len(pre) else float("nan"), float(post.mean()) if len(post) else float("nan")
    return {"series": s, "pre": a, "post": b, "change_rel": _pct_change(a, b), "last": s.index.max() if len(s) else None}


def fig_youth(flags: pd.DataFrame) -> go.Figure:
    s = youth_summary(flags)["series"]
    roll = s.rolling(12, min_periods=12).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s * 100, mode="lines", name="mesečno", line=dict(color=PALETTE["green"], width=1), opacity=0.5,
                             hovertemplate=f"%{{x|{HOVER_MONTH}}}: %{{y:.1f}} % objav<extra></extra>"))
    fig.add_trace(go.Scatter(x=roll.index, y=roll * 100, mode="lines", name="povprečje zadnjih 12 mesecev",
                             line=dict(color=PALETTE["green"], width=2.8),
                             hovertemplate=f"%{{x|{HOVER_MONTH}}}: %{{y:.1f}} %<extra></extra>"))
    fig.update_layout(**base_layout("Objave, ki vabijo začetnike, pripravnike in sveže diplomante", height=460))
    fig.update_layout(yaxis=dict(title="delež objav (%)", rangemode="tozero"), xaxis=dict(tickformat="%Y"))
    add_event_lines(fig, keys=("chatgpt",))
    return fig


def explain_youth(flags: pd.DataFrame) -> dict:
    s = youth_summary(flags)
    st = STUDIES["stanford"]
    if not all(np.isfinite([s["pre"], s["post"]])):
        pomen = "Podatki ne pokrivajo obeh obdobij (pred koncem leta 2022 in zadnjih 12 mesecev), zato primerjave ni."
    else:
        word = "padel" if s["change_rel"] < -1 else "narasel" if s["change_rel"] > 1 else "ostal skoraj enak"
        pomen = (f"{st['cite']} iz plačnih podatkov ADP poročajo, da je zaposlenost 22- do 25-letnikov v poklicih, izpostavljenih UI, "
                 f"{sl_num(abs(st['young_gap_pct']), 0)} % nižja, kot bi bila, če bi sledila manj izpostavljenim vrstnikom. Pri nas je delež "
                 f"objav, ki vabijo začetnike, {word}: z {sl_pct(s['pre'], 1)} v 12 mesecih do ChatGPT na {sl_pct(s['post'], 1)} v zadnjih "
                 f"12 mesecih ({_signed(s['change_rel'])} glede na izhodišče).")
    return {
        "kaj": "Zelena črta je delež objav, ki vabijo začetnike, pripravnike ali sveže diplomante (tanka mesečno, debela povprečje zadnjih 12 "
               "mesecev). Črtkana črta je izid ChatGPT.",
        "zakaj": "Študija s Stanforda je pokazala, da so po koncu leta 2022 delovna mesta izgubljali predvsem mladi v poklicih, ki jih UI lahko "
                 "opravlja. Preverili smo, ali delodajalci na Hacker Newsu začetnike vabijo redkeje.",
        "pomen": pomen,
        "omejitve": "Študija meri zaposlene ljudi po starosti, mi pa oglase, ki omenjajo začetnike; to nista isti stvari. Oznaka je pravilo s "
                    "ključnimi besedami, ki smo ga preverili na ročno označenem vzorcu, vendar ni popolno. Pred ChatGPT so se hkrati dvigovale "
                    "obrestne mere, zato časovno ujemanje ne pomeni vzroka.",
    }


def verdict_youth(flags: pd.DataFrame) -> dict:
    """se ujema: our share fell by >= 10 % of its pre-ChatGPT level; delno: fell by less; se razlikuje: did not fall."""
    s = youth_summary(flags)
    st = STUDIES["stanford"]
    if not np.isfinite(s["change_rel"]):
        ocena, ours = "ni primerljivo", "ni podatkov za obe obdobji"
    else:
        ocena = "se ujema" if s["change_rel"] <= -10 else "delno" if s["change_rel"] < 0 else "se razlikuje"
        ours = f"delež objav za začetnike {sl_pct(s['pre'], 1)} na {sl_pct(s['post'], 1)} ({_signed(s['change_rel'])})"
    return check_verdict({"tema": "Mladi in začetniki", "studija": "Brynjolfsson, Chandar in Chen (2025), Stanford",
                          "njihov_rezultat": f"mladi v poklicih z UI {_signed(st['young_gap_pct'])} glede na vrstnike",
                          "nas_rezultat": ours, "ocena": ocena})


# ---------------------------------------------------------------------------------------- 4. geography
def metro_compare_table(geo: pd.DataFrame) -> pd.DataFrame:
    """STUDY_METROS joined to our metro_map_data on the CBSA code: it_growth_pct only where usable (else NaN = withheld)."""
    g = geo[["cbsa_code", "metro_name", "it_growth_pct", "usable", "estab_growth_pct"]].copy()
    g["cbsa_code"] = g["cbsa_code"].astype(str).str.zfill(5)
    t = STUDY_METROS.merge(g, on="cbsa_code", how="left")
    t["ours"] = t["it_growth_pct"].where(t["usable"].fillna(False).astype(bool))
    return t


def bernard_pairs(t: pd.DataFrame) -> dict:
    """Pairs of Bernard's metros whose order he gives (both exact, or exact above -40 vs 'more than -40'), and whether our job growth
    puts them in the same order. Pairs with a withheld value of ours are skipped."""
    b = t[t["indeed_pct"].notna()].reset_index(drop=True)
    conc = disc = skipped = 0
    pairs = []
    for i in range(len(b)):
        for j in range(i + 1, len(b)):
            x, y = b.loc[i], b.loc[j]
            if x["indeed_bound"] and y["indeed_bound"]:
                continue
            if x["indeed_bound"] or y["indeed_bound"]:
                ex, bd = (y, x) if x["indeed_bound"] else (x, y)
                if not ex["indeed_pct"] > bd["indeed_pct"]:
                    continue                                       # e.g. Boston -51 vs "more than -40": order unknown
                hi, lo = ex, bd
            else:
                if x["indeed_pct"] == y["indeed_pct"]:
                    continue
                hi, lo = (x, y) if x["indeed_pct"] > y["indeed_pct"] else (y, x)
            if pd.isna(hi["ours"]) or pd.isna(lo["ours"]):
                skipped += 1
                continue
            ok = hi["ours"] > lo["ours"]
            conc += int(ok)
            disc += int(not ok)
            pairs.append((hi["name"], lo["name"], bool(ok)))
    return {"concordant": conc, "discordant": disc, "skipped": skipped, "pairs": pairs}


def group_medians(t: pd.DataFrame) -> dict:
    out = {}
    for grp in (SUPER, RISING):
        v = t.loc[t["group"] == grp, "ours"].dropna()
        out[grp] = {"median": float(v.median()) if len(v) else float("nan"), "n": int(len(v)),
                    "hidden": int(((t["group"] == grp) & t["ours"].isna()).sum())}
    return out


def fig_regions_compare(geo: pd.DataFrame) -> go.Figure:
    """Dot plot, one row per metro named in the studies: our IT job growth 2019-2024 (blue dot, or 'podatek je skrit') and Indeed's
    tech postings change early 2020 to early 2025 (orange diamond; open with an arrow where Bernard says only 'more than 40 %')."""
    t = metro_compare_table(geo)
    t["order"] = t["group"].map({RISING: 0, SUPER: 1}).fillna(2)
    t = t.sort_values(["order", "ours"], ascending=[False, True], na_position="first").reset_index(drop=True)
    labels = [f"{r.name} ({r.group})" if isinstance(r.group, str) else r.name for r in t.itertuples()]
    fig = go.Figure()
    ok = t["ours"].notna()
    fig.add_trace(go.Scatter(x=t.loc[ok, "ours"], y=[labels[i] for i in t.index[ok]], mode="markers", name="naši podatki: rast IT delovnih mest 2019-2024",
                             marker=dict(color=PALETTE["blue"], size=11),
                             text=[f"<b>{_metro_label(m)}</b><br>IT delovna mesta 2019-2024: {_signed(v, 1)}"
                                   for m, v in zip(t.loc[ok, "metro_name"], t.loc[ok, "ours"])], hovertemplate="%{text}<extra></extra>"))
    hid = t[~ok]
    if len(hid):
        fig.add_trace(go.Scatter(x=[0] * len(hid), y=[labels[i] for i in hid.index], mode="markers+text", name="naši podatki: podatek je skrit",
                                 marker=dict(symbol="x", color=PALETTE["grey"], size=9), text=["podatek je skrit"] * len(hid),
                                 textposition="middle right", textfont=dict(size=10, color=PALETTE["grey"]), hoverinfo="skip"))
    ex = t[t["indeed_pct"].notna() & ~t["indeed_bound"].astype(bool)]
    if len(ex):
        fig.add_trace(go.Scatter(x=ex["indeed_pct"], y=[labels[i] for i in ex.index], mode="markers",
                                 name="Bernard (2025): tehnološki oglasi, začetek 2020 do začetka 2025",
                                 marker=dict(symbol="diamond", color=PALETTE["orange"], size=12),
                                 text=[f"<b>{n}</b><br>tehnološki oglasi na Indeedu: {_signed(v)}" for n, v in zip(ex["name"], ex["indeed_pct"])],
                                 hovertemplate="%{text}<extra></extra>"))
    bd = t[t["indeed_bound"].astype(bool)]
    if len(bd):
        fig.add_trace(go.Scatter(x=bd["indeed_pct"], y=[labels[i] for i in bd.index], mode="markers",
                                 name="Bernard (2025): »več kot −40 %« (brez točne številke)",
                                 marker=dict(symbol="diamond-open", color=PALETTE["orange"], size=12, line=dict(width=2)),
                                 text=[f"<b>{n}</b><br>tehnološki oglasi na Indeedu: padec za več kot 40 %" for n in bd["name"]],
                                 hovertemplate="%{text}<extra></extra>"))
        for i in bd.index:
            fig.add_annotation(x=bd.loc[i, "indeed_pct"] - 12, y=labels[i], ax=bd.loc[i, "indeed_pct"] - 2, ay=labels[i], xref="x", yref="y",
                               axref="x", ayref="y", showarrow=True, arrowhead=2, arrowcolor=PALETTE["orange"], text="")
    fig.add_vline(x=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.update_layout(**base_layout("Mesta iz študij: naša rast IT delovnih mest in njihove številke o oglasih", height=140 + 30 * len(t)))
    fig.update_layout(xaxis=dict(title="sprememba (%)", ticksuffix=" %", zeroline=False), yaxis=dict(automargin=True),
                      hovermode="closest", legend=dict(orientation="h", y=-0.12, x=0))
    fig.add_annotation(xref="paper", yref="paper", x=0, y=1.0, yanchor="bottom", showarrow=False, font=dict(size=11), align="left",
                       text="Delovna mesta in oglasi nista isto merilo: krog = zaposleni v IT, romb = oglasi za delo")
    return fig


def explain_regions_compare(geo: pd.DataFrame) -> dict:
    t = metro_compare_table(geo)
    bp, gm = bernard_pairs(t), group_medians(t)
    get = lambda n: t.loc[t["name"] == n].iloc[0]
    parts = []
    au, bo = get("Austin"), get("Boston")
    if pd.notna(au["ours"]) and pd.notna(bo["ours"]):
        parts.append(f"Bernard (2025) je izmeril, da so tehnološki oglasi na Indeedu od začetka 2020 do začetka 2025 v Austinu padli za "
                     f"{sl_num(abs(au['indeed_pct']), 0)} %, v Bostonu za {sl_num(abs(bo['indeed_pct']), 0)} %, v Seattlu, San Franciscu in "
                     f"Minneapolisu za več kot 40 %. Pri nas je IT zaposlenost 2019-2024 v Austinu {_signed(au['ours'])}, v Bostonu "
                     f"{_signed(bo['ours'])}.")
    n_pairs = bp["concordant"] + bp["discordant"]
    if n_pairs:
        parts.append(f"Bernard pri parih mest pove, kje je bil padec manjši; preverljivih je {_pairs(n_pairs)}, naši podatki jih "
                     f"{bp['concordant']} razvrstijo enako in {bp['discordant']} drugače"
                     + (f" (še {_pairs(bp['skipped'])} ne moremo preveriti, ker je naš podatek skrit)." if bp["skipped"] else "."))
    s, r = gm[SUPER], gm[RISING]
    if r["n"] and s["n"]:
        better = "hitreje" if r["median"] > s["median"] else "počasneje"
        parts.append(f"Muro in You (2022) sta »vzhajajoče zvezde« (npr. Dallas, Denver, Miami) opisala kot mesta, ki so med pandemijo "
                     f"pridobivala na račun »superzvezd« (npr. San Francisco, Boston, Seattle). Pri nas je tipično vzhajajoče mesto raslo "
                     f"{better}: mediana {_signed(r['median'])} ({r['n']} mest) proti {_signed(s['median'])} pri superzvezdah ({s['n']} mest).")
    hidden = t.loc[t["ours"].isna(), "name"].tolist()
    if hidden:
        parts.append(f"Za {', '.join(hidden)} je naš podatek skrit.")
    return {
        "kaj": "Vsaka vrstica je mesto, ki ga omenja ena od študij (v oklepaju skupina po Brookingsu). Modri krog je naša rast IT delovnih mest "
               "2019-2024, oranžni romb sprememba oglasov za tehnološka delovna mesta na Indeedu po Bernardu (2025). Prazen romb s puščico "
               "pomeni, da študija pove le »padec za več kot 40 %«. Siv križec: naš podatek je skrit.",
        "zakaj": "Dve študiji opisujeta, kam se je preselilo tehnološko delo: Brookings (Muro in You 2022) za prvo leto pandemije, Indeed "
                 "(Bernard 2025) za oglase do leta 2025. Preverili smo, ali naši podatki o zaposlenih razvrstijo mesta podobno.",
        "pomen": " ".join(parts) if parts else "Za mesta iz študij nimamo uporabnih podatkov.",
        "omejitve": "Oglasi in delovna mesta nista isto: oglasi kažejo novo zaposlovanje, mi pa štejemo vse zaposlene. Obdobja niso enaka "
                    "(mi 2019-2024, Indeed začetek 2020 do začetka 2025, Brookings predvsem 2020), naš IT pa je le svetovanje in programiranje "
                    "po naročilu (NAICS 5415), Indeed pa šteje vse tehnološke poklice. Zato primerjamo vrstni red mest, ne številk. Številke "
                    "študij smo prepisali z njihovih spletnih strani.",
    }


def verdict_regions_compare(geo: pd.DataFrame) -> dict:
    """se ujema: all checkable Bernard pairs in the same order AND rising stars grew faster than superstars; delno: one of the two;
    se razlikuje: neither; ni primerljivo: no checkable pair and no group medians."""
    t = metro_compare_table(geo)
    bp, gm = bernard_pairs(t), group_medians(t)
    n_pairs = bp["concordant"] + bp["discordant"]
    s, r = gm[SUPER], gm[RISING]
    have_groups = bool(s["n"] and r["n"])
    if not n_pairs and not have_groups:
        ocena, ours = "ni primerljivo", "naši podatki za ta mesta so skriti"
    else:
        a = n_pairs > 0 and bp["discordant"] == 0
        b = have_groups and r["median"] > s["median"]
        ocena = "se ujema" if a and b else "delno" if a or b else "se razlikuje"
        ours = []
        if n_pairs:
            ours.append(f"v istem vrstnem redu {bp['concordant']} od {n_pairs} preverljivih parov mest")
        if have_groups:
            ours.append(f"vzhajajoče {_signed(r['median'])}, superzvezde {_signed(s['median'])} (mediana rasti IT delovnih mest)")
        ours = "; ".join(ours)
    b = t.set_index("name")["indeed_pct"]
    return check_verdict({"tema": "Geografija", "studija": "Bernard (2025), Indeed; Muro in You (2022), Brookings",
                          "njihov_rezultat": f"oglasi Austin {_signed(b['Austin'])}, Boston {_signed(b['Boston'])}; vzhajajoče zvezde rastejo "
                                             "hitreje od superzvezd",
                          "nas_rezultat": ours, "ocena": ocena})


# ---------------------------------------------------------------------------------------- entry point
def build_figures(flags: pd.DataFrame, indeed: pd.DataFrame | None, geo: pd.DataFrame) -> dict[str, go.Figure]:
    return {"9b_daljava_primerjava": fig_remote_compare(flags, indeed),
            "9b_ui_primerjava": fig_ai_compare(flags),
            **({"9b_mladi": fig_youth(flags)} if has_junior_v2(flags) else {}),
            "9b_regije_primerjava": fig_regions_compare(geo)}


def build_texts(flags: pd.DataFrame, indeed: pd.DataFrame | None, geo: pd.DataFrame) -> dict[str, tuple[dict, dict]]:
    out = {"9b_daljava_primerjava": (explain_remote_compare(flags, indeed), verdict_remote_compare(flags, indeed)),
           "9b_ui_primerjava": (explain_ai_compare(flags), verdict_ai_compare(flags))}
    if has_junior_v2(flags):
        out["9b_mladi"] = (explain_youth(flags), verdict_youth(flags))
    out["9b_regije_primerjava"] = (explain_regions_compare(geo), verdict_regions_compare(geo))
    return out


def build_comparisons_b() -> dict[str, tuple[go.Figure, dict, dict]]:
    """Every Stream B comparison as (figure, explanation, verdict), in display order. Reads only committed aggregates and raises
    FileNotFoundError (with the command that creates it) if one is missing."""
    flags, indeed, geo = load_flags(), load_indeed_remote(), load_map_data()
    figs, texts = build_figures(flags, indeed, geo), build_texts(flags, indeed, geo)
    return {n: (figs[n], *texts[n]) for n in figs}


def main() -> None:
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    cmd = sys.argv[1:]
    if cmd == ["aggregates"]:
        log.info("wrote %s", write_aggregates())
    elif cmd == ["preview"]:
        for name, (fig, _, _) in build_comparisons_b().items():
            log.info("wrote %s", save_html(fig, f"preview_{name}"))
    else:
        raise SystemExit("usage: python -m analysis.compare_text_geo aggregates | preview")


if __name__ == "__main__":
    main()
