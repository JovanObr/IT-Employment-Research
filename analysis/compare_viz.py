"""Notebook 09 (Stream A part): our findings beside published studies. Figures, Slovenian explanations and verdict rows.

Every comparison is returned as (figure, explanation, verdict):
* explanation: the four parts kaj / zakaj / pomen / omejitve (shown with viz_theme.explanation_markdown), numbers from the data;
* verdict: one row of the summary table {tema, studija, njihov_rezultat, nas_rezultat, ocena}, ocena in VERDICTS, chosen by the numbers.
Stream B delivers the same shape from analysis/compare_text_geo.py (build_comparisons_b). Figure sources: analysis/data_sources.py.

    python -m analysis.compare_viz preview     # writes reports/figures_sl/preview_9a_*.html
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis import causes as cs
from analysis import comparisons as cp
from analysis.viz_theme import PALETTE, base_layout, sl_num, sl_pct

log = logging.getLogger("covid_it_data")
VERDICTS = ("se ujema", "delno", "se razlikuje", "ni primerljivo")
VERDICT_KEYS = ("tema", "studija", "njihov_rezultat", "nas_rezultat", "ocena")


def _pct(x: float, digits: int = 1, sign: bool = True) -> str:
    s = sl_num(x, digits)
    return f"+{s} %" if sign and x > 0 else f"{s} %"


def _ci(lo: float, hi: float, digits: int = 1) -> str:
    return f"od {_pct(lo, digits)} do {_pct(hi, digits)}"


def _spans_zero(lo: float, hi: float) -> bool:
    return bool(lo <= 0 <= hi)


# ---------------------------------------------------------------------------------------- 1. Challenger
def _annual(t: pd.DataFrame) -> pd.DataFrame:
    return t[t["period"].str.fullmatch(r"\d{4}")].sort_values("period")


PERIOD_SL = {"2022Q1": "1. četrtletje 2022", "2022-11": "november 2022", "2023Q1": "1. četrtletje 2023"}   # in time order


def fig_challenger(t: pd.DataFrame) -> go.Figure:
    """Grouped bars: Challenger's US technology job cuts and the tracker's people at US companies, per year (left) and for the
    three shorter periods Challenger reports separately (right)."""
    a = _annual(t)
    s = t[~t["period"].str.fullmatch(r"\d{4}")]
    s = s.assign(k=s["period"].map({p: i for i, p in enumerate(PERIOD_SL)}).fillna(99)).sort_values(["k", "period"])
    s = s.assign(period=s["period"].map(PERIOD_SL).fillna(s["period"]))
    fig = make_subplots(rows=1, cols=2, column_widths=[0.62, 0.38], horizontal_spacing=0.08,
                        subplot_titles=["po letih", "posamezna obdobja"])
    for j, d in enumerate((a, s), 1):
        for col, name, color in (("challenger", "Challenger, Gray & Christmas (tehnološki sektor)", PALETTE["grey"]),
                                 ("tracker_us", "naš seznam (Layoffs.fyi), podjetja iz ZDA", PALETTE["red"])):
            extra = ([f"{sl_pct(x)} napovedi s številom" for x in d["share_with_number"]] if col == "tracker_us"
                     else ["" for _ in range(len(d))])
            fig.add_trace(go.Bar(x=d["period"], y=d[col], name=name, marker_color=color, showlegend=j == 1, legendgroup=col,
                                 customdata=np.c_[[sl_num(v, 0) for v in d[col]], extra],
                                 hovertemplate="%{x}: %{customdata[0]} ljudi<br>%{customdata[1]}<extra>" + name + "</extra>"), row=1, col=j)
    fig.update_layout(**base_layout("Koliko ljudi so podjetja napovedala odpustiti: naš seznam in Challenger", height=460), barmode="group")
    fig.update_yaxes(title_text="napovedano odpuščenih ljudi", row=1, col=1)
    fig.update_xaxes(type="category")                          # '2022Q1' and '2022-11' are labels, not dates
    return fig


def explain_challenger(t: pd.DataFrame) -> dict:
    a = _annual(t).set_index("period")
    peak_c, peak_t = a["challenger"].idxmax(), a["tracker_us"].idxmax()
    close = a[(a["ratio_us_to_challenger"] >= 0.8) & (a["ratio_us_to_challenger"] <= 1.25)].index.tolist()
    years = ", ".join(f"{y}: {sl_num(r['tracker_us'], 0)} proti {sl_num(r['challenger'], 0)}" for y, r in a.iterrows())
    q22 = t.set_index("period").get("tracker_us", pd.Series(dtype=float)).get("2022Q1", np.nan)
    c22 = t.set_index("period")["challenger"].get("2022Q1", np.nan)
    timing = ("Obe štetji imata vrh v istem letu" if peak_c == peak_t else f"Vrh je pri Challengerju v letu {peak_c}, pri nas v letu {peak_t}")
    ratio_txt = (f"V letih {', '.join(close)} sta števili blizu (razlika do četrtine)" if close else "V nobenem letu števili nista blizu")
    share = _annual(t)["share_with_number"].mean()
    return {
        "kaj": "Sivi stolpci so podatki podjetja Challenger, Gray & Christmas, ki že od leta 1993 šteje napovedana odpuščanja ameriških podjetij "
               "po panogah; tu je njihov tehnološki sektor. Rdeči stolpci so seštevek ljudi iz našega seznama, le za podjetja s sedežem v ZDA. "
               "Levo so cela leta, desno tri krajša obdobja, ki jih Challenger objavlja posebej. Z miško vidite, kolikšen del naših napovedi sploh "
               "navede število ljudi.",
        "zakaj": "Naš seznam (Layoffs.fyi) je zbirka novic, ki jo ureja ena oseba. Preveriti smo želeli, ali neodvisno štetje pride do podobnih "
                 "številk, preden se na naše številke zanesemo.",
        "pomen": f"{timing}. {ratio_txt}. Po letih (naš seznam proti Challengerju): {years}. "
                 + (f"Velika izjema je prvo četrtletje 2022: pri nas {sl_num(q22, 0)} ljudi, pri Challengerju le {sl_num(c22, 0)}, "
                    "kar kaže, da Challenger v tehnološki sektor šteje ožji krog podjetij kot naš seznam. " if np.isfinite(q22) and np.isfinite(c22) and q22 > 5 * c22 else "")
                 + "Dva neodvisna vira torej kažeta isti val odpuščanj; naše številke niso izmišljene, so pa le približne.",
        "omejitve": f"Naše številke so spodnja meja: le približno {sl_pct(share)} napovedi pove, koliko ljudi bodo odpustili. Oba vira štejeta napovedi, "
                    "ne dejansko izgubljenih služb, in »tehnologijo« opredelita različno (naš seznam ima tudi finančna, prodajna in prevozna "
                    "tehnološka podjetja). Challengerjeve številke smo prepisali iz njihovih mesečnih poročil.",
    }


def verdict_challenger(t: pd.DataFrame) -> dict:
    a = _annual(t).set_index("period")
    same_peak = a["challenger"].idxmax() == a["tracker_us"].idxmax()
    core = a.reindex(["2022", "2023"])["ratio_us_to_challenger"]
    close = bool(core.notna().all() and core.between(0.8, 1.25).all())
    ocena = "se ujema" if same_peak and close else "delno" if same_peak or close else "se razlikuje"
    return {"tema": "Koliko ljudi", "studija": "Challenger, Gray & Christmas (mesečna poročila)",
            "njihov_rezultat": " / ".join(f"{y}: {sl_num(v, 0)}" for y, v in a["challenger"].items()),
            "nas_rezultat": " / ".join(f"{y}: {sl_num(v, 0)}" for y, v in a["tracker_us"].items()), "ocena": ocena}


# ---------------------------------------------------------------------------------------- 2. stock reaction by layoff share
SHARE_ORDER = list(cp.SHARE_LABELS) + ["ni podatka"]


def fig_stock_share(by_group: pd.DataFrame) -> go.Figure:
    """Average abnormal return over days 0 and +1 with its 95 % interval, per share of staff laid off."""
    d = by_group.assign(k=by_group["share_group"].astype(str)).set_index("k").reindex(SHARE_ORDER).dropna(subset=["n"])
    up = (d["ci_hi_pct"] - d["mean_pct"]).fillna(0).to_numpy()
    dn = (d["mean_pct"] - d["ci_lo_pct"]).fillna(0).to_numpy()
    colors = [PALETTE["grey"] if k == "ni podatka" else PALETTE["blue"] for k in d.index]
    fig = go.Figure(go.Scatter(x=list(d.index), y=d["mean_pct"], mode="markers", marker=dict(size=13, color=colors),
                               error_y=dict(type="data", symmetric=False, array=up, arrayminus=dn, color=PALETTE["ink"]),
                               customdata=np.c_[d["n"], d["median_pct"]], showlegend=False,
                               hovertemplate="%{x}: povprečje %{y:.2f} %<br>mediana %{customdata[1]:.2f} %<br>%{customdata[0]} objav<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.update_layout(**base_layout("Ali borza bolj kaznuje večja odpuščanja?", height=440))
    fig.update_layout(xaxis=dict(title="delež zaposlenih, ki jih podjetje odpusti"),
                      yaxis=dict(title="povprečni nenavadni donos v dneh 0 in +1 (%)"))
    return fig


def explain_stock_share(s: dict) -> dict:
    g = s["by_big"].set_index("share_big")
    big, small = g.loc["nad 10 %"], g.loc["do 10 %"]
    diff = s["diff_big_minus_small"]
    sig = not _spans_zero(diff["ci_lo_pct"], diff["ci_hi_pct"])
    unknown = g["mean_pct"].get("ni podatka", np.nan)
    direction = ("bolj negativen" if diff["diff_pct"] < 0 else "manj negativen ali celo pozitiven")
    return {
        "kaj": "Vsaka pika je povprečni »nenavadni donos« delnice v dnevu objave in naslednjem dnevu, to je sprememba cene, ki je ne pojasni "
               "gibanje celotne borze. Objave smo razdelili po tem, kolikšen del zaposlenih podjetje odpusti. Navpične črte kažejo 95-odstotni "
               "interval negotovosti; siva pika so objave, ki deleža ne navedejo.",
        "zakaj": "Starejše raziskave (Worrell, Davidson in Sharma 1991) in pregled 78 študij (Eshghi in Astvansh 2024) ugotavljajo, da borza "
                 "večja odpuščanja kaznuje bolj. Preverili smo, ali to velja tudi za tehnološka podjetja po letu 2020.",
        "pomen": f"Pri odpuščanjih več kot desetine zaposlenih je povprečni odziv {_pct(big['mean_pct'], 2)} ({int(big['n'])} objav), pri manjših "
                 f"{_pct(small['mean_pct'], 2)} ({int(small['n'])} objav). Odziv pri večjih je torej {direction}: razlika {_pct(diff['diff_pct'], 2)}, "
                 f"interval {_ci(diff['ci_lo_pct'], diff['ci_hi_pct'], 2)}. "
                 + ("Interval ne vključuje ničle, zato je razlika verjetno resnična, tako kot v študijah. " if sig else
                    "Interval vključuje ničlo, zato razlika lahko nastane tudi po naključju: smer je ista kot v študijah, dokaza pa nimamo. ")
                 + (f"Objave brez navedenega deleža imajo povprečje {_pct(unknown, 2)}; zato je bil skupni odziv vseh objav tako majhen."
                    if np.isfinite(unknown) else ""),
        "omejitve": f"Delež navede le {s['n_known']} od {len(s['events'])} objav, in to morda ne naključno izbranih. Večja odpuščanja so pogosto "
                    "v podjetjih, ki jim že sicer slabo gre, zato velikost odpuščanja in slabe novice o poslovanju težko ločimo. "
                    "Starejše študije merijo drugače (pogosto število ljudi, ne delež) in v drugih desetletjih.",
    }


def verdict_stock_share(s: dict) -> dict:
    d = s["diff_big_minus_small"]
    ocena = ("se ujema" if d["diff_pct"] < 0 and d["ci_hi_pct"] < 0 else "delno" if d["diff_pct"] < 0 else "se razlikuje")
    g = s["by_big"].set_index("share_big")["mean_pct"]
    return {"tema": "Borza in velikost odpuščanja", "studija": "Worrell in sod. (1991); Eshghi in Astvansh (2024)",
            "njihov_rezultat": "večja odpuščanja borza kaznuje bolj",
            "nas_rezultat": f"nad 10 % zaposlenih {_pct(g['nad 10 %'], 2)}, do 10 % {_pct(g['do 10 %'], 2)}; razlika {_ci(d['ci_lo_pct'], d['ci_hi_pct'], 2)}",
            "ocena": ocena}


# ---------------------------------------------------------------------------------------- 3. within-firm model
WITHIN_SPEC = ("rev_decline", "op_margin", "net_loss", "cash_assets", "log_assets")
FEATURE_SL = {"rev_decline": "prihodki nižji kot pred letom", "op_margin": "poslovna marža", "net_loss": "podjetje posluje z izgubo",
              "cash_assets": "delež gotovine v sredstvih", "log_assets": "velikost podjetja (sredstva)", "rev_yoy": "rast prihodkov v letu"}
MODEL_SL = {False: "med podjetji (FE četrtletja)", True: "znotraj podjetja (FE podjetja + četrtletja)"}


def fig_within(w: pd.DataFrame) -> go.Figure:
    """Coefficient plot: change in the chance of a layoff in the next two quarters (percentage points), comparing firms with each
    other (grey) and each firm with itself (blue), with 95 % intervals."""
    fig = go.Figure()
    feats = [f for f in WITHIN_SPEC if f in set(w["feature"])][::-1]
    for within, color, offset in ((False, PALETTE["grey"], 0.15), (True, PALETTE["blue"], -0.15)):
        d = w[w["model"] == MODEL_SL[within]].set_index("feature").reindex(feats)
        y = np.arange(len(feats)) + offset
        fig.add_trace(go.Scatter(x=d["pp_effect"], y=y, mode="markers", name=MODEL_SL[within].split(" (")[0],
                                 marker=dict(size=11, color=color),
                                 error_x=dict(type="data", symmetric=False, array=(d["ci_hi"] - d["pp_effect"]).to_numpy(),
                                              arrayminus=(d["pp_effect"] - d["ci_lo"]).to_numpy(), color=color),
                                 customdata=np.c_[[FEATURE_SL[f] for f in feats], d["ci_lo"], d["ci_hi"]],
                                 hovertemplate="%{customdata[0]}: %{x:.2f} odstotne točke<br>interval %{customdata[1]:.2f} do %{customdata[2]:.2f}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.update_layout(**base_layout("Kaj napove odpuščanje: primerjava med podjetji in znotraj istega podjetja", height=460))
    fig.update_layout(yaxis=dict(tickvals=list(range(len(feats))), ticktext=[FEATURE_SL[f] for f in feats]),
                      xaxis=dict(title="sprememba verjetnosti odpuščanja v naslednjih dveh četrtletjih (odstotne točke)"))
    return fig


def _row(w: pd.DataFrame, feature: str, within: bool) -> pd.Series:
    return w[(w["model"] == MODEL_SL[within]) & (w["feature"] == feature)].iloc[0]


def explain_within(w: pd.DataFrame) -> dict:
    rd_in, rd_out = _row(w, "rev_decline", True), _row(w, "rev_decline", False)
    sz_in, sz_out = _row(w, "log_assets", True), _row(w, "log_assets", False)
    base = rd_in["base_rate"]
    rev_matters = rd_in["ci_lo"] > 0
    size_gone = _spans_zero(sz_in["ci_lo"], sz_in["ci_hi"]) and not _spans_zero(sz_out["ci_lo"], sz_out["ci_hi"])
    return {
        "kaj": "Vsaka pika pove, za koliko odstotnih točk se spremeni verjetnost, da podjetje v naslednjih dveh četrtletjih napove odpuščanja, "
               "če se ena lastnost spremeni (pri lastnostih z da/ne: razlika med »da« in »ne«; pri drugih: sprememba za en standardni odklon). "
               "Sive pike primerjajo podjetja med seboj, modre vsako podjetje samo s seboj v drugih četrtletjih. Črte so 95-odstotni intervali.",
        "zakaj": "Študija Federal Reserve (Weingarden 2017) je pokazala, da podjetje odpušča, ko mu prihodki padajo, in to znotraj istega podjetja. "
                 "Naš model je prej primerjal podjetja med seboj, in tam je vse preglasila velikost. Zato smo uporabili njihov pristop.",
        "pomen": f"Ko podjetje primerjamo samo s seboj, nižji prihodki kot pred letom spremenijo verjetnost za {sl_num(rd_in['pp_effect'], 2)} točke "
                 f"(interval {sl_num(rd_in['ci_lo'], 2)} do {sl_num(rd_in['ci_hi'], 2)}), pri osnovni verjetnosti okoli {sl_pct(base)}. "
                 + ("Padec prihodkov torej napove odpuščanje, kot v študiji. " if rev_matters else
                    "Padec prihodkov torej ne napove odpuščanja niti znotraj podjetja; tu se z ameriško študijo ne ujemamo. ")
                 + f"Velikost podjetja med podjetji poveča verjetnost za {sl_num(sz_out['pp_effect'], 1)} točke na standardni odklon, "
                 + ("znotraj podjetja pa učinka ni več, ker se velikost v nekaj letih skoraj ne spremeni." if size_gone else
                    f"znotraj podjetja za {sl_num(sz_in['pp_effect'], 1)} točke.")
                 + ("" if rev_matters else " Odpuščanj tehnoloških podjetij po letu 2020 torej ne moremo pojasniti s padcem prihodkov; razlog moramo "
                                          "iskati drugje (na primer v prejšnjem zaposlovanju, glej naslednji graf)."),
        "omejitve": f"Primerjava podjetja s samim seboj deluje le pri podjetjih, ki imajo četrtletja z odpuščanji in brez njih; takih je {int(rd_in['firms_with_variation'])} "
                    f"od {int(rd_in['firms'])}, zato so intervali široki. Študija je opazovala obdobje 2007-2012 z veliko recesijo, ko so prihodki res padali, "
                    "mi pa obdobje, ko so prihodki večine tehnoloških podjetij še rasli. Model je linearen in pokaže povezave, ne vzrokov.",
    }


def verdict_within(w: pd.DataFrame) -> dict:
    r = _row(w, "rev_decline", True)
    return {"tema": "Padec prihodkov in odpuščanja", "studija": "Weingarden (2017), Federal Reserve FEDS 2017-088",
            "njihov_rezultat": "padec prihodkov poveča verjetnost odpuščanja znotraj podjetja",
            "nas_rezultat": f"{sl_num(r['pp_effect'], 2)} odstotne točke (interval {sl_num(r['ci_lo'], 2)} do {sl_num(r['ci_hi'], 2)})",
            "ocena": "se ujema" if r["ci_lo"] > 0 else "se razlikuje"}


# ---------------------------------------------------------------------------------------- 4. over-hiring with headcount
def fig_overhiring(h: dict) -> go.Figure:
    """Left: share of companies with a tracker layoff in 2022-2023, by quartile of headcount growth 2019-2021.
    Right: median headcount change 2022 -> 2023 by the same quartiles (from the 10-K filings, independent of the tracker)."""
    q, c = h["quartiles"], h["cut_quartiles"]
    labels = ["najpočasnejša<br>četrtina", "2.<br>četrtina", "3.<br>četrtina", "najhitrejša<br>četrtina"]
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                        subplot_titles=["delež podjetij z napovedjo odpuščanj 2022-2023", "srednja sprememba zaposlenih 2022 → 2023"])
    fig.add_trace(go.Bar(x=labels, y=100 * q["rate"], marker_color=PALETTE["red"], showlegend=False,
                         customdata=np.c_[q["laid_off"], q["companies"]],
                         hovertemplate="%{x}: %{y:.0f} %<br>%{customdata[0]} od %{customdata[1]} podjetij<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=labels, y=c["median_change_22_23_pct"], marker_color=PALETTE["blue"], showlegend=False,
                         customdata=np.c_[c["median_hire_growth_pct"], c["companies"], 100 * c["share_cut_5pct"]],
                         hovertemplate="%{x}: %{y:.1f} %<br>rast 2019-2021: %{customdata[0]:.0f} %<br>%{customdata[1]} podjetij, "
                                       "%{customdata[2]:.0f} % jih je zmanjšalo zaposlene za več kot 5 %<extra></extra>"), row=1, col=2)
    fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1), row=1, col=2)
    fig.update_layout(**base_layout("Ali so odpuščala podjetja, ki so v pandemiji najhitreje zaposlovala?", height=470))
    fig.update_yaxes(title_text="%", row=1, col=1)
    fig.update_yaxes(title_text="%", row=1, col=2)
    fig.update_xaxes(title_text="podjetja po rasti števila zaposlenih 2019-2021", row=1, col=1)
    fig.update_xaxes(title_text="podjetja po rasti števila zaposlenih 2019-2021", row=1, col=2)
    return fig


def explain_overhiring(h: dict) -> dict:
    q, c, lg = h["quartiles"], h["cut_quartiles"], h["logit"].set_index("term").loc["hire_growth"]
    cut, cv = h["cut"], h["cut_vs_hire"]
    tracker_agrees = lg["ci_lo"] > 1
    cut_agrees = cut["ci_hi"] < 0
    rel = ("hitrejše zaposlovanje je povezano z večjim kasnejšim krčenjem" if cut_agrees else
           "kasnejše krčenje ni povezano s prejšnjo hitrostjo zaposlovanja" if _spans_zero(cut["ci_lo"], cut["ci_hi"]) else
           "hitreje zaposlujoča podjetja so se kasneje celo manj krčila")
    return {
        "kaj": "Podjetja smo razdelili v četrtine po tem, za koliko se je med letoma 2019 in 2021 povečalo število zaposlenih (iz letnih poročil 10-K). "
               "Levo je delež podjetij v vsaki četrtini, ki so v letih 2022-2023 napovedala odpuščanja. Desno je srednja sprememba števila zaposlenih "
               "od konca 2022 do konca 2023 v istih četrtinah, kar ni odvisno od našega seznama napovedi.",
        "zakaj": "Najpogostejša razlaga (na primer Srivastava in sod. 2023) je, da so podjetja v pandemiji zaposlila preveč in so odpuščanja popravek. "
                 "Prej tega nismo mogli preveriti, ker nismo imeli števila zaposlenih; zdaj ga imamo za "
                 f"{h['n']} tehnoloških podjetij.",
        "pomen": f"Delež podjetij z napovedjo odpuščanj raste od {sl_pct(q['rate'].iloc[0])} v najpočasnejši do {sl_pct(q['rate'].iloc[-1])} v najhitrejši četrtini; "
                 f"tudi ob upoštevanju velikosti podjetja so obeti {sl_num(lg['odds_ratio'], 2)}-krat večji na standardni odklon rasti "
                 f"(interval {sl_num(lg['ci_lo'], 2)} do {sl_num(lg['ci_hi'], 2)}). "
                 + ("Kdo je napovedal odpuščanja, se torej ujema z razlago o prevelikem zaposlovanju. " if tracker_agrees else
                    "Povezava ni dovolj zanesljiva, da bi razlago o prevelikem zaposlovanju potrdili. ")
                 + f"Pri dejanskem številu zaposlenih pa {rel} (korelacija {sl_num(cut['spearman'], 2)}, interval {sl_num(cut['ci_lo'], 2)} do {sl_num(cut['ci_hi'], 2)}). "
                 f"Podjetja, ki so zaposlene zmanjšala, so jih v srednjem za {sl_num(-cv['median_cut_pct'], 1)} %, po prej {_pct(cv['median_prior_growth_pct'], 1)} rasti; "
                 f"{sl_pct(cv['share_still_above_2019'])} jih je imelo leta 2023 še vedno več zaposlenih kot leta 2019. "
                 "Tudi Srivastava in sod. ugotavljajo, da so bila odpuščanja majhna v primerjavi s prejšnjim zaposlovanjem.",
        "omejitve": "Število zaposlenih smo prebrali iz besedila letnih poročil s pravili za iskanje stavkov; ročni pregled vzorca je pokazal, da je "
                    "okoli 9 od 10 števil pravilnih. Podjetja štejejo različno (nekatera vključijo pogodbene sodelavce), število pa velja za en dan v letu, "
                    "zato odpuščanja in nova zaposlovanja v istem letu ne vidimo ločeno. Leva slika temelji na našem seznamu napovedi, ki ne zajame vseh odpuščanj.",
    }


def verdict_overhiring(h: dict) -> dict:
    lg = h["logit"].set_index("term").loc["hire_growth"]
    a, b = lg["ci_lo"] > 1, h["cut"]["ci_hi"] < 0
    q = h["quartiles"]["rate"]
    cut = h["cut"]
    rel = ("je močnejša pri hitrejši rasti" if cut["ci_hi"] < 0 else "ni povezana z rastjo" if _spans_zero(cut["ci_lo"], cut["ci_hi"])
           else "je šibkejša pri hitrejši rasti")
    return {"tema": "Preveliko zaposlovanje v pandemiji", "studija": "Srivastava, Govindarajan, Rajgopal in Tanone (2023)",
            "njihov_rezultat": "odpuščala so podjetja, ki so v pandemiji najbolj zaposlovala; odpuščanja so bila majhna glede na prejšnjo rast",
            "nas_rezultat": f"napovedi odpuščanj: {sl_pct(q.iloc[0])} → {sl_pct(q.iloc[-1])} po četrtinah rasti (ob upoštevanju velikosti obeti "
                            f"{sl_num(lg['odds_ratio'], 2)}-krat, interval {sl_num(lg['ci_lo'], 2)} do {sl_num(lg['ci_hi'], 2)}); krčenje zaposlenih "
                            f"2022-2023 {rel} (korelacija {sl_num(h['cut']['spearman'], 2)}); "
                            f"{sl_pct(h['cut_vs_hire']['share_still_above_2019'])} podjetij, ki so krčila, je še nad ravnjo 2019",
            "ocena": "se ujema" if a and b else "delno" if a or b or h["cut_vs_hire"]["share_still_above_2019"] > 0.5 else "se razlikuje"}


# ---------------------------------------------------------------------------------------- earlier findings (rows only)
def verdicts_earlier(stock_summary: dict | None, weekly: pd.Series, h2: dict) -> list[dict]:
    """Rows for the findings of notebook 08 already compared in the case-study doc (numbers recomputed from the data)."""
    rows = []
    if stock_summary:
        s = stock_summary
        rows.append({"tema": "Odziv borze na napoved odpuščanj", "studija": "Farber in Hallock (2009); Floros in sod. (2023); Eshghi in Astvansh (2024)",
                     "njihov_rezultat": "negativen, a vse šibkejši skozi desetletja; leta 2020 brez učinka",
                     "nas_rezultat": f"{_pct(s['mean_pct'], 2)} v dneh 0 in +1 (interval {_ci(s['ci_lo_pct'], s['ci_hi_pct'], 2)})",
                     "ocena": "se ujema" if _spans_zero(s["ci_lo_pct"], s["ci_hi_pct"]) or s["mean_pct"] < 0 else "se razlikuje"})
    f, c = cs.event_study(weekly, cs.FED_HIKE), cs.event_study(weekly, cs.CHATGPT)
    rows.append({"tema": "Kdaj se je začel val", "studija": "Bailey in Hernandez Martinez (2023, Cleveland Fed); Bernard (2025, Indeed)",
                 "njihov_rezultat": "dražje zadolževanje je zmanjšalo prosta mesta; skoraj polovica padca oglasov pred ChatGPT",
                 "nas_rezultat": f"napovedi na teden: ob zvišanju obrestne mere {sl_num(f['before_mean'])} → {sl_num(f['after_mean'])}, "
                                 f"ob ChatGPT {sl_num(c['before_mean'])} → {sl_num(c['after_mean'])}",
                 "ocena": "se ujema" if f["diff"] > c["diff"] else "se razlikuje"})
    j = h2.get("jolts", {}).get("first Fed hike 2022-03-16", {}).get("information")
    if j:
        rows.append({"tema": "Uradna stopnja odpuščanj", "studija": "Cohen (2023, Kansas City Fed)",
                     "njihov_rezultat": "kljub zvišanju obrestnih mer se stopnja odpuščanj skoraj ni spremenila",
                     "nas_rezultat": f"informacijski sektor (JOLTS): {sl_num(j['before'], 2)} % → {sl_num(j['after'], 2)} % na mesec",
                     "ocena": "se ujema" if abs(j["after"] - j["before"]) < 0.15 else "se razlikuje"})
    return rows


def verdict_markdown(rows: list[dict]) -> str:
    for r in rows:
        missing = [k for k in VERDICT_KEYS if not str(r.get(k, "")).strip()]
        if missing or r["ocena"] not in VERDICTS:
            raise ValueError(f"verdict row {r.get('tema')!r}: missing {missing} or bad ocena {r.get('ocena')!r}")
    head = "| Tema | Študija | Njihov rezultat | Naš rezultat | Ocena |\n|---|---|---|---|---|\n"
    esc = lambda s: str(s).replace("|", "/")
    return head + "\n".join(f"| {esc(r['tema'])} | {esc(r['studija'])} | {esc(r['njihov_rezultat'])} | {esc(r['nas_rezultat'])} | **{r['ocena']}** |"
                            for r in rows)


# ---------------------------------------------------------------------------------------- data and entry point
def load_headcount() -> pd.DataFrame | None:
    from collectors import sec_headcount as sh
    from collectors.common import RAW
    p = RAW / "sec_headcount.csv"
    return sh.recheck(pd.read_csv(p))[0] if p.exists() else None   # the current sentence rules, even before a re-run


def prepare_compare_data(n_boot: int = 1000) -> dict:
    """Run the comparisons once on the local files (a few minutes)."""
    from analysis import event_study as es
    from collectors.common import PROCESSED
    d = cs.load_inputs()
    out = {"challenger": cp.challenger_compare(d["events"]), "weekly": cs.weekly_layoffs(d["events"]),
           "h2": cs.run_h2(d["events"], d["fred"], d["jolts"])}
    ev = PROCESSED / "event_study_events.csv"
    if ev.exists():
        cars = pd.read_csv(ev, parse_dates=["date", "event_day"])
        out["stock"] = cp.stock_by_share(cars, cp.event_layoff_size(d["events"], d["matches"]), n_boot=n_boot)
        out["stock_summary"] = es.summarize(cars, n_boot=n_boot)
    panel = pd.read_csv(PROCESSED / "company_panel.csv", dtype={"sic": str, "sic2": str})
    out["within"] = cp.within_firm_model(panel, WITHIN_SPEC)
    heads = load_headcount()
    if heads is not None:
        boom = cs.run_h3(d["fin"], d["revenue"], d["universe"], d["matches"], d["events"])["used"]
        h = cp.headcount_overhiring(heads, boom, n_boot=n_boot)
        if "logit" in h and "cut" in h:
            out["headcount"] = h
    return out


def build_figures(data: dict) -> dict[str, go.Figure]:
    return {"9a_challenger": fig_challenger(data["challenger"]),
            **({"9a_borza_delez": fig_stock_share(data["stock"]["by_group"])} if data.get("stock") else {}),
            "9a_znotraj": fig_within(data["within"]),
            **({"9a_zaposlovanje": fig_overhiring(data["headcount"])} if data.get("headcount") else {})}


def build_comparisons_a(data: dict) -> dict[str, tuple[go.Figure, dict, dict]]:
    figs = build_figures(data)
    texts = {"9a_challenger": (explain_challenger(data["challenger"]), verdict_challenger(data["challenger"])),
             "9a_znotraj": (explain_within(data["within"]), verdict_within(data["within"]))}
    if data.get("stock"):
        texts["9a_borza_delez"] = (explain_stock_share(data["stock"]), verdict_stock_share(data["stock"]))
    if data.get("headcount"):
        texts["9a_zaposlovanje"] = (explain_overhiring(data["headcount"]), verdict_overhiring(data["headcount"]))
    return {n: (figs[n], *texts[n]) for n in figs}


def main() -> None:
    import sys
    from analysis.viz_theme import save_html
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if sys.argv[1:] != ["preview"]:
        raise SystemExit("usage: python -m analysis.compare_viz preview")
    for name, (fig, _, _) in build_comparisons_a(prepare_compare_data()).items():
        log.info("wrote %s", save_html(fig, f"preview_{name}"))


if __name__ == "__main__":
    main()
