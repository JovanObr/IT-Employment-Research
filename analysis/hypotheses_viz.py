"""Notebook 10 (milestone 3): the four pre-registered hypotheses, in Slovenian for a casual audience.

Numbers in the text come from the frozen results files of the single registered run (reports/hypotheses_a_results.json from
analysis/hypotheses.py, reports/hypotheses_b_results.json from Stream B's analysis/hypotheses_b.py); figures redraw the same data.
The verdict of each hypothesis is decided only by the registered rule: Holm-adjusted p < 0.05 across all four AND the predicted sign.
Until all four p-values exist, no verdict is printed (a Holm correction over part of the family would be wrong).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.hypotheses import ALPHA, holm
from analysis.viz_theme import PALETTE, base_layout, sl_num

NAMES = {"A": "Slovenija in strokovnjaki IKT", "B": "San Francisco in Austin po prvem zvišanju obrestne mere",
         "C": "Napovedana odpuščanja in dejansko število zaposlenih", "D": "Ponovljene napovedi odpuščanj in borza"}
PREDICTION = {"A": "delež strokovnjakov IKT je v Sloveniji 2021-2024 zrasel bolj kot v večini držav EU",
              "B": "po zvišanju obrestne mere je zaposlenost v IT v San Franciscu padla glede na Austin",
              "C": "podjetja, ki so napovedala odpuščanja, so imela 2021-2023 večji padec zaposlenih",
              "D": "ponovljene napovedi borza kaznuje bolj kot prve"}
EU_SL = {"AT": "Avstrija", "BE": "Belgija", "BG": "Bolgarija", "CY": "Ciper", "CZ": "Češka", "DE": "Nemčija", "DK": "Danska",
         "EE": "Estonija", "EL": "Grčija", "ES": "Španija", "FI": "Finska", "FR": "Francija", "HR": "Hrvaška", "HU": "Madžarska",
         "IE": "Irska", "IT": "Italija", "LT": "Litva", "LU": "Luksemburg", "LV": "Latvija", "MT": "Malta", "NL": "Nizozemska",
         "PL": "Poljska", "PT": "Portugalska", "RO": "Romunija", "SE": "Švedska", "SI": "Slovenija", "SK": "Slovaška"}


def _p(p: float) -> str:
    return "manj kot 0,001" if p < 0.001 else sl_num(p, 3)


def _pct_log(x: float, digits: int = 1) -> str:
    v = 100 * np.expm1(x)
    return f"{'+' if v > 0 else ''}{sl_num(v, digits)} %"


def _pp(x: float, digits: int = 2) -> str:
    return f"{'+' if x > 0 else ''}{sl_num(x, digits)}"


# ---------------------------------------------------------------------------------------- verdicts
def verdicts(results: dict[str, dict | None]) -> pd.DataFrame:
    """One row per hypothesis: p, Holm p (only when all four exist), predicted sign, verdict by the registered rule."""
    prim = {k: (v or {}).get("primary") for k, v in results.items()}
    have = {k: v["p"] for k, v in prim.items() if v and v.get("p") is not None}
    complete = set(have) == set(NAMES)
    h = holm(have).set_index("hypothesis") if complete else None
    rows = []
    for k in NAMES:
        r = prim.get(k)
        if not r or r.get("p") is None:
            rows.append({"hipoteza": k, "tema": NAMES[k], "p": np.nan, "p_holm": np.nan, "smer": "", "sklep": "čaka na rezultat"})
            continue
        sign = bool(r.get("predicted_sign"))
        if h is None:                                        # Holm only raises p-values: p >= 0.05 already decides
            verdict = "ni potrjena" if r["p"] >= ALPHA else "čaka na vse štiri teste"
            ph = np.nan
        else:
            ph = float(h.loc[k, "p_holm"])
            verdict = "potrjena" if (ph < ALPHA and sign) else "ni potrjena"
        rows.append({"hipoteza": k, "tema": NAMES[k], "p": float(r["p"]), "p_holm": ph,
                     "smer": "kot napovedano" if sign else "nasprotna od napovedi", "sklep": verdict})
    return pd.DataFrame(rows)


def verdict_markdown(v: pd.DataFrame) -> str:
    head = "| | Hipoteza (napoved) | Smer | p | p po popravku (Holm) | Sklep |\n|---|---|---|---|---|---|\n"
    lines = []
    for r in v.itertuples():
        p = "" if np.isnan(r.p) else _p(r.p)
        ph = "" if np.isnan(r.p_holm) else _p(r.p_holm)
        lines.append(f"| **{r.hipoteza}** | {r.tema}: {PREDICTION[r.hipoteza]} | {r.smer} | {p} | {ph} | **{r.sklep}** |")
    return head + "\n".join(lines)


def _verdict_sentence(v: pd.DataFrame, k: str) -> str:
    r = v.set_index("hipoteza").loc[k]
    if r["sklep"] in ("potrjena", "ni potrjena") and not np.isnan(r["p_holm"]):
        return f"Po popravku za štiri teste je p {_p(r['p_holm'])}, zato je hipoteza **{r['sklep']}**."
    if not np.isnan(r["p"]) and r["p"] >= ALPHA:
        return (f"Že brez popravka je p {_p(r['p'])}, kar je več kot 0,05; popravek p-vrednosti le poveča, zato hipoteza **ni potrjena**, "
                "ne glede na ostale teste.")
    return "Končni sklep bo znan, ko bodo izračunani vsi štirje testi (popravek upošteva vse štiri hkrati)."


# ---------------------------------------------------------------------------------------- C. headcount
def fig_c(c21: pd.DataFrame, c22: pd.DataFrame | None = None) -> go.Figure:
    """Box plots of the change in employees by group: main window 2021-2023 (left), exploratory 2022-2023 (right)."""
    panels = [("glavni test: 2021 → 2023", c21)] + ([("dodatno, ni del glavnega testa: 2022 → 2023", c22)] if c22 is not None and len(c22) else [])
    fig = make_subplots(rows=1, cols=len(panels), shared_yaxes=True, subplot_titles=[t for t, _ in panels], horizontal_spacing=0.06)
    for j, (_, d) in enumerate(panels, 1):
        for ann, name, col in ((0, "brez napovedi odpuščanj", PALETTE["grey"]), (1, "z napovedjo odpuščanj 2022-2023", PALETTE["red"])):
            y = 100 * np.expm1(d.loc[d["announced"] == ann, "outcome"])
            fig.add_trace(go.Box(y=y.clip(-80, 150), name=name, marker_color=col, boxpoints="outliers", showlegend=False,
                                 hovertemplate="%{y:.1f} %<extra>" + name + "</extra>"), row=1, col=j)
        fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"), row=1, col=j)
    fig.update_layout(**base_layout("Ali so podjetja z napovedjo odpuščanj res zmanjšala število zaposlenih?", height=480))
    fig.update_yaxes(title_text="sprememba števila zaposlenih (%)", row=1, col=1)
    return fig


def explain_c(res: dict, v: pd.DataFrame) -> dict:
    p, s, pl = res["primary"], res.get("secondary_2022_2023", {}), res.get("placebo", {})
    ols = res.get("secondary_ols", {})
    sig = p["p"] < ALPHA
    pomen = (f"Med letoma 2021 in 2023 so podjetja z napovedjo odpuščanj ({p['n_announced']}) v srednjem spremenila število zaposlenih za "
             f"{_pct_log(p['median_announced'])}, podjetja brez napovedi ({p['n_not']}) za {_pct_log(p['median_not'])}. Razlika je "
             f"{'v napovedani smeri' if p['predicted_sign'] else 'v nasprotni smeri od napovedi'}, a "
             f"{'statistično značilna' if sig else 'premajhna, da bi jo ločili od naključja'} (p {_p(p['p'])}; 95-odstotni interval razlike "
             f"od {_pct_log(p['ci_lo'])} do {_pct_log(p['ci_hi'])}). " + _verdict_sentence(v, "C"))
    if s:
        pomen += (f" Dodatno (vnaprej določeno kot pomožno, zato ne spremeni sklepa): v oknu 2022 → 2023 je razlika "
                  f"{_pct_log(s['diff_median'])} (od {_pct_log(s['ci_lo'])} do {_pct_log(s['ci_hi'])}, p {_p(s['p'])}). "
                  "Rast v letu 2022 je verjetno prikrila kasnejše krčenje; to je zanimiva ugotovitev za nadaljnje delo, ne pa potrditev hipoteze.")
    return {
        "kaj": "Vsak »škatlasti« graf kaže, kako se je spremenilo število zaposlenih v posameznih tehnoloških podjetjih (iz letnih poročil 10-K). "
               "Črta v škatli je srednja vrednost (mediana), škatla zajema srednjo polovico podjetij, pike so posebej velike spremembe "
               "(prikazane največ do -80 % in +150 %). Sivo so podjetja brez napovedi odpuščanj, "
               "rdeče podjetja, ki so v letih 2022-2023 napovedala odpuščanja. Levo je glavni, vnaprej določeni test, desno pomožni.",
        "zakaj": "Naš seznam odpuščanj temelji na napovedih v medijih. Preveriti smo želeli, ali se napovedi pokažejo tudi v uradnem številu "
                 "zaposlenih, ki ga podjetja sporočijo nadzorniku borze. Če ne, bi bil seznam slabo merilo dejanskih odpuščanj.",
        "pomen": pomen,
        "omejitve": f"Število zaposlenih velja za en dan v letu in smo ga prebrali iz besedila poročil (približno 9 od 10 pravilnih). Podjetje lahko "
                    "v istem letu odpušča in zaposluje, prevzemi pa število spremenijo neodvisno od odpuščanj. "
                    + (f"Preverba z naključno premešanimi skupinami da lažni zadetek v {sl_num(100 * pl['false_positive_rate'], 1)} % primerov "
                       "(pričakovano okoli 5 %), torej je test pravilno umerjen. " if pl else "")
                    + (f"Ob upoštevanju velikosti podjetja je razlika {_pct_log(ols['coef_announced'])} (p {_p(ols['p'])})." if ols.get("p") is not None else ""),
    }


# ---------------------------------------------------------------------------------------- D. repeat announcements
def d_groups(cars: pd.DataFrame, n_boot: int = 2000, seed: int = 0) -> pd.DataFrame:
    """Winsorised mean abnormal return per group with a day-clustered 95 % interval (the same winsorisation as the primary test)."""
    from analysis import event_study as es
    d = cars.dropna(subset=["car_ann_0_1"]).copy()
    v = d["car_ann_0_1"].clip(d["car_ann_0_1"].quantile(0.01), d["car_ann_0_1"].quantile(0.99))
    rng, rows = np.random.default_rng(seed), []
    for rep, name in ((0, "prva napoved podjetja"), (1, "ponovljena napoved")):
        m = d["repeat"] == rep
        lo, hi = es._cluster_bootstrap_mean(v[m].to_numpy(float), d.loc[m, "event_day"].to_numpy(), n_boot, rng)
        rows.append({"group": name, "n": int(m.sum()), "mean_pct": 100 * float(v[m].mean()), "lo_pct": 100 * lo, "hi_pct": 100 * hi})
    return pd.DataFrame(rows)


def fig_d(groups: pd.DataFrame) -> go.Figure:
    up, dn = groups["hi_pct"] - groups["mean_pct"], groups["mean_pct"] - groups["lo_pct"]
    fig = go.Figure(go.Scatter(x=groups["group"], y=groups["mean_pct"], mode="markers", marker=dict(size=14, color=[PALETTE["blue"], PALETTE["orange"]]),
                               error_y=dict(type="data", symmetric=False, array=up, arrayminus=dn, color=PALETTE["ink"]), customdata=groups["n"],
                               hovertemplate="%{x}: %{y:.2f} %<br>%{customdata} objav<extra></extra>", showlegend=False))
    fig.add_hline(y=0, line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.update_layout(**base_layout("Prva in ponovljena napoved odpuščanj: odziv borze", height=430))
    fig.update_layout(yaxis=dict(title="povprečni nenavadni donos v dneh 0 in +1 (%)"), xaxis=dict(title=""))
    return fig


def explain_d(res: dict, v: pd.DataFrame) -> dict:
    p, s, pl = res["primary"], res.get("secondary", {}), res.get("placebo", {})
    mw = s.get("mannwhitney_p_raw")
    pomen = (f"Prve napovedi ({p['n_first']}) so imele povprečni odziv {_pp(p['mean_first_pct'])} %, ponovljene ({p['n_repeat']}) "
             f"{_pp(p['mean_repeat_pct'])} %, razlika {_pp(p['diff_pct'])} odstotne točke (p {_p(p['p'])}). "
             + ("Razlika je v napovedani smeri. " if p["predicted_sign"] else
                "Razlika je **v nasprotni smeri od napovedi**: borza bolj reagira na prvo napoved, ne na ponovljene. ")
             + _verdict_sentence(v, "D"))
    if mw is not None and not p["predicted_sign"]:
        pomen += (f" Pomožni test na neskrčenih vrednostih (p {_p(mw)}) kaže isto smer. Možna razlaga, ki jo bo treba preveriti posebej: "
                  "prva napoved je novica, ponovljene borza že pričakuje.")
    return {
        "kaj": "Pika je povprečni »nenavadni donos« delnice v dnevu napovedi in naslednjem dnevu, to je sprememba cene, ki je ne pojasni gibanje "
               "celotne borze. Levo so prve napovedi podjetja v našem seznamu, desno vse kasnejše. Navpična črta je 95-odstotni interval.",
        "zakaj": "Pričakovali smo, da ponovljena odpuščanja vlagatelji razumejo kot znak, da ima podjetje resne težave, in zato bolj kaznujejo.",
        "pomen": pomen,
        "omejitve": "»Prva« pomeni prva v našem seznamu, ki se začne marca 2020, ne nujno prva v zgodovini podjetja. Podjetja, ki odpuščajo "
                    "večkrat, se lahko od ostalih razlikujejo tudi drugače (velikost, panoga). Skrajne vrednosti smo skrčili na 1. in 99. percentil. "
                    + (f"Preverba na naključnih dneh brez napovedi da lažni zadetek v {sl_num(100 * pl['false_positive_rate'], 0)} % ponovitev "
                       "(pričakovano okoli 5 %)." if pl else ""),
    }


# ---------------------------------------------------------------------------------------- A. Slovenia (Stream B's numbers)
def fig_a(primary: dict) -> go.Figure:
    vals = pd.Series(primary["values"], dtype=float).dropna().sort_values()
    colors = [PALETTE["red"] if c == "SI" else PALETTE["grey"] for c in vals.index]
    fig = go.Figure(go.Bar(x=vals.to_numpy(), y=[EU_SL.get(c, c) for c in vals.index], orientation="h", marker_color=colors,
                           hovertemplate="%{y}: %{x:.2f} odstotne točke<extra></extra>"))
    fig.add_vline(x=primary["mean_others"], line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.add_annotation(x=primary["mean_others"], y=1, yref="paper", text="povprečje ostalih 26 držav", showarrow=False, xanchor="left", yanchor="bottom")
    fig.update_layout(**base_layout("Sprememba deleža strokovnjakov IKT med zaposlenimi, 2021 → 2024", height=640))
    fig.update_layout(xaxis=dict(title="sprememba (odstotne točke)"), yaxis=dict(title=""))
    return fig


def explain_a(res: dict, v: pd.DataFrame) -> dict:
    p, pl = res["primary"], res.get("placebo", {})
    return {
        "kaj": "Vsak stolpec je ena država EU: za koliko odstotnih točk se je od leta 2021 do 2024 spremenil delež strokovnjakov za informacijske "
               "in komunikacijske tehnologije (IKT) med vsemi zaposlenimi. Slovenija je rdeča, črtkana črta je povprečje ostalih 26 držav.",
        "zakaj": "Slovenija ima rastočo IT panogo. Preverili smo, ali je njena rast res izstopala v primerjavi z drugimi državami EU ali pa je "
                 "bila podobna kot drugje.",
        "pomen": (f"Delež se je v Sloveniji spremenil za {_pp(p['x_si'])} odstotne točke, v povprečju ostalih držav za {_pp(p['mean_others'])} "
                  f"(standardni odklon {sl_num(p['sd_others'], 2)}). Slovenija je po rasti na {int(p['rank'])}. mestu od {int(p['n_countries'])}. "
                  f"Test, ali Slovenija izstopa, da p {_p(p['p'])}. " + _verdict_sentence(v, "A")),
        "omejitve": "Eurostat je leta 2021 spremenil metodo ankete o delovni sili, zato primerjamo šele od leta 2021; nekatere vrednosti so ocene. "
                    "Test pove le, ali Slovenija izstopa, ne pa zakaj. "
                    + (f"Isti test za vsako drugo državo da p pod 0,05 v {sl_num(100 * pl['share_p_below_005'], 0)} % primerov (pričakovano okoli 5 %)."
                       if pl.get("share_p_below_005") is not None else ""),
    }


# ---------------------------------------------------------------------------------------- B. San Francisco vs. Austin (Stream B's numbers)
def fig_b(primary: dict) -> go.Figure:
    s = pd.DataFrame(primary["series"]).dropna(subset=["sf", "austin"])
    s = s.assign(d=np.log(s["sf"]) - np.log(s["austin"]))
    base = s.iloc[0]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.55, 0.45],
                        subplot_titles=["zaposleni v IT (prvo četrtletje = 100)", "razlika San Francisco - Austin (logaritem)"])
    for col, name, color in (("sf", "San Francisco", PALETTE["red"]), ("austin", "Austin", PALETTE["blue"])):
        fig.add_trace(go.Scatter(x=s["quarter"], y=100 * s[col] / base[col], name=name, mode="lines+markers", line=dict(color=color, width=2.5),
                                 hovertemplate="%{x}: %{y:.1f}<extra>" + name + "</extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=s["quarter"], y=s["d"], mode="lines+markers", line=dict(color=PALETTE["ink"], width=2), showlegend=False,
                             hovertemplate="%{x}: %{y:.3f}<extra></extra>"), row=2, col=1)
    q = list(s["quarter"])
    if "2022Q2" in q:
        for r in (1, 2):
            fig.add_vrect(x0="2022Q2", x1=q[-1], fillcolor=PALETTE["light_grey"], opacity=0.5, line_width=0, row=r, col=1)
    fig.update_layout(**base_layout("San Francisco in Austin: zaposlenost v IT pred in po prvem zvišanju obrestne mere", height=620))
    fig.update_xaxes(type="category", row=2, col=1)
    fig.update_xaxes(type="category", row=1, col=1)
    return fig


def explain_b(res: dict, v: pd.DataFrame) -> dict:
    p, pl = res["primary"], res.get("placebo", {})
    change = _pct_log(p["b"])
    return {
        "kaj": "Zgoraj je število zaposlenih v IT (računalniško programiranje in svetovanje) v obeh mestnih območjih, preračunano tako, da je prvo "
               "četrtletje 100. Spodaj je razlika med njima; sivo je obdobje po prvem zvišanju obrestne mere (od 2. četrtletja 2022).",
        "zakaj": "San Francisco je tradicionalno središče tehnoloških podjetij, Austin hitro rastoče novo središče. Preverili smo, ali je zvišanje "
                 "obrestnih mer San Francisco prizadelo bolj.",
        "pomen": (f"Po zvišanju je bila razlika med mestoma povprečno za {change} drugačna kot prej (95-odstotni interval "
                  f"{_pct_log(p['ci_lo'])} do {_pct_log(p['ci_hi'])}, p {_p(p['p'])}), "
                  + ("v napovedani smeri. " if p["predicted_sign"] else "v nasprotni smeri od napovedi. ")
                  + ("Ker se je razlika spreminjala že pred zvišanjem, test meri odmik od tega prejšnjega trenda. " if p.get("trend_added") else "")
                  + _verdict_sentence(v, "B")),
        "omejitve": f"Le dve območji in kratke vrste ({p.get('n_pre', '?')} četrtletij pred, {p.get('n_post', '?')} po). Podatki zajemajo računalniške "
                    "storitve (NAICS 5415), ne pa programskih založnikov in velikih tehnoloških podjetij. Dogajanje v istem času (delo na daljavo, "
                    "selitve) lahko pojasni razliko. "
                    + (f"Med {pl['n_pairs']} pari velikih mestnih območij jih ima {sl_num(100 * pl['share_abs_b_at_least'], 0)} % vsaj tako velik "
                       "premik, zato premik San Francisca ni nenavaden." if pl.get("n_pairs") and pl.get("share_abs_b_at_least", 0) > 0.1 else
                       (f"Med {pl['n_pairs']} pari velikih mestnih območij jih ima le {sl_num(100 * pl['share_abs_b_at_least'], 0)} % vsaj tako velik premik."
                        if pl.get("n_pairs") else "")),
    }


# ---------------------------------------------------------------------------------------- data and entry point
def load_results() -> dict[str, dict | None]:
    from analysis.viz_theme import ROOT
    out = {k: None for k in NAMES}
    pa, pb = ROOT / "reports" / "hypotheses_a_results.json", ROOT / "reports" / "hypotheses_b_results.json"
    if pa.exists():
        ra = json.loads(pa.read_text(encoding="utf-8"))
        out["C"], out["D"] = ra.get("C"), ra.get("D")
    if pb.exists():
        rb = json.loads(pb.read_text(encoding="utf-8"))
        out["A"], out["B"] = rb.get("A"), rb.get("B")
    return out


def prepare_figure_data() -> dict:
    """The C sample and the labelled D events, rebuilt with the registered functions (for the figures only)."""
    from analysis import causes as cs
    from analysis import hypotheses as hy
    from collectors import sec_headcount as sh
    from collectors.common import PROCESSED, RAW
    d = cs.load_inputs()
    panel = pd.read_csv(PROCESSED / "company_panel.csv", dtype={"sic": str, "sic2": str})
    heads = sh.recheck(pd.read_csv(RAW / "sec_headcount.csv"))[0]
    ann = hy.announced_ciks(d["events"], d["matches"])
    out = {"c21": hy.headcount_sample(heads, d["universe"], ann, panel), "c22": hy.headcount_sample(heads, d["universe"], ann, panel, years=(2022, 2023))}
    ev = PROCESSED / "event_study_events.csv"
    if ev.exists():
        out["d"] = d_groups(hy.label_repeat(pd.read_csv(ev, parse_dates=["date", "event_day"]), d["events"], d["matches"]))
    return out


def build_figures(results: dict, data: dict) -> dict[str, go.Figure]:
    ok = lambda k: results.get(k) and results[k].get("primary")
    return {**({"10a_slovenija": fig_a(results["A"]["primary"])} if ok("A") and "values" in results["A"]["primary"] else {}),
            **({"10b_sf_austin": fig_b(results["B"]["primary"])} if ok("B") and "series" in results["B"]["primary"] else {}),
            **({"10c_zaposleni": fig_c(data["c21"], data.get("c22"))} if ok("C") and "c21" in data else {}),
            **({"10d_borza": fig_d(data["d"])} if ok("D") and "d" in data else {})}


def build_hypotheses(results: dict, data: dict) -> dict[str, tuple[go.Figure, dict]]:
    v = verdicts(results)
    figs = build_figures(results, data)
    explain = {"10a_slovenija": lambda: explain_a(results["A"], v), "10b_sf_austin": lambda: explain_b(results["B"], v),
               "10c_zaposleni": lambda: explain_c(results["C"], v), "10d_borza": lambda: explain_d(results["D"], v)}
    return {n: (f, explain[n]()) for n, f in figs.items()}


def exploratory_markdown(results: dict) -> str:
    """Findings from the registered secondary checks that point somewhere new. They do not change any verdict."""
    items = []
    c, d = (results.get("C") or {}), (results.get("D") or {})
    s = c.get("secondary_2022_2023")
    if s and s.get("p") is not None and c.get("primary"):
        items.append(f"**Odpuščanja se v številu zaposlenih vidijo, a šele v oknu 2022 → 2023.** Razlika med podjetji z napovedjo in brez nje je "
                     f"{_pct_log(s['diff_median'])} (od {_pct_log(s['ci_lo'])} do {_pct_log(s['ci_hi'])}, p {_p(s['p'])}), medtem ko je v vnaprej "
                     f"izbranem oknu 2021 → 2023 le {_pct_log(c['primary']['diff_median'])}. Zaposlovanje v letu 2022 je verjetno prikrilo kasnejše "
                     "krčenje. Za potrditev bi potrebovali nov, vnaprej zapisan test na drugih podatkih (na primer za leto 2024).")
    if d.get("primary") and not d["primary"]["predicted_sign"]:
        mw = d.get("secondary", {}).get("mannwhitney_p_raw")
        items.append(f"**Borza bolj reagira na prvo napoved odpuščanj kot na ponovljene** ({_pp(d['primary']['mean_first_pct'])} % proti "
                     f"{_pp(d['primary']['mean_repeat_pct'])} %" + (f"; pomožni test p {_p(mw)}" if mw is not None else "") +
                     "). To je nasprotno od naše napovedi in je zato le zamisel za novo hipotezo: prva napoved je novica, naslednje vlagatelji že pričakujejo.")
    if not items:
        return "*Pomožni testi niso pokazali ničesar, kar bi kazalo v novo smer.*"
    return "Te ugotovitve niso bile glavni testi, zato **ne spremenijo nobenega sklepa**. So pa dobra izhodišča za nova vprašanja.\n\n" + "\n\n".join(f"- {x}" for x in items)
