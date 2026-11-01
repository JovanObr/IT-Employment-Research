"""Plain-language explanations (Slovenian, casual audience) for the chapter 1-3 figures of the milestone story.

Each `explain_*` function takes the same data as its figure and returns four parts:
  kaj      what we see (how to read the figure)
  zakaj    why we did it (the question)
  pomen    what it means (numbers computed from the data; the wording follows the numbers)
  omejitve what we do not know (always present)
`build_explanations(story)` returns them under the same names as `analysis.viz.build_figures`.
Show them with `analysis.viz_theme.explanation_markdown`. A reader should be able to follow the story without the code.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import causes as cs
from analysis.viz import MODEL_LABELS, model_comparison_table
from analysis.viz_theme import sl_num, sl_pct


def _date(d: pd.Timestamp) -> str:
    return f"{d.day}. {d.month}. {d.year}"


def _change(before: float, after: float, tol: float = 0.10) -> str:
    """'skoraj nespremenjeno', 'naraslo' or 'padlo', chosen from the numbers."""
    if before > 0 and abs(after - before) / before < tol:
        return "skoraj nespremenjeno"
    return "naraslo" if after > before else "padlo"


def _times(x: float) -> str:
    return f"{sl_num(x, 1)}-krat"


# ---------------------------------------------------------------------------------------- chapter 1
def explain_timeline(weekly: pd.Series, macro: pd.DataFrame) -> dict:
    st = cs.event_study(weekly, cs.FED_HIKE)
    before_hike = macro["fedfunds"][macro.index < "2022-03-01"].iloc[-1]
    peak_rate = macro["fedfunds"][macro.index >= "2022-03-01"].max()
    n = macro["nasdaq"]
    window = n[(n.index >= "2021-01-01") & (n.index <= "2022-06-30")]
    peak = window.idxmax()
    trough = n[(n.index >= peak) & (n.index <= peak + pd.DateOffset(months=18))].min()
    drop = 100 * (1 - trough / window.max())
    surge = _change(st["before_mean"], st["after_mean"]) == "naraslo"
    rate_up, market_down = peak_rate - before_hike >= 1.0, drop >= 5
    facts = [f"v 26 tednih pred prvim zvišanjem obrestne mere (16. 3. 2022) je bilo povprečno {sl_num(st['before_mean'])} napovedi na teden, "
             f"v 26 tednih po njem {sl_num(st['after_mean'])}"]
    facts.append(f"obrestna mera je zrasla z {sl_num(before_hike)} % na {sl_num(peak_rate)} %" if rate_up
                 else f"obrestna mera se je spremenila le z {sl_num(before_hike)} % na {sl_num(peak_rate)} %")
    facts.append(f"borzni indeks NASDAQ je od vrha do dna izgubil {sl_num(drop, 0)} %" if market_down
                 else "borzni indeks NASDAQ ni bistveno padel")
    together = (" Dražji denar, padec borze in val napovedanih odpuščanj so se torej zgodili v istem obdobju." if surge and rate_up and market_down
                else " V teh podatkih se stvari ne ujemajo tako jasno, da bi lahko govorili o skupnem valu.")
    return {
        "kaj": "Na enem grafu je več črt: koliko odpuščanj so podjetja napovedala na teden, obrestna mera ameriške centralne banke (Fed), "
               "borzni indeks NASDAQ in, če so podatki na voljo, delež objav za delo na Hacker Newsu, ki omenjajo delo na daljavo "
               "oziroma umetno inteligenco. Vsako črto smo preračunali na lestvico od 0 do 100, da jih lahko primerjamo; ko miško "
               "premakneš na črto, vidiš pravo vrednost. Črtkani črti označujeta prvo zvišanje obrestne mere in izid ChatGPT.",
        "zakaj": "Hoteli smo videti, ali se te stvari dogajajo ob istem času. Številke imajo različne enote (število, odstotki, točke), "
                 "zato jih brez preračuna ne bi mogli narisati na isto os.",
        "pomen": (facts[0][0].upper() + facts[0][1:] + "; " + "; ".join(facts[1:]) + "." + together),
        "omejitve": "Dogajanje ob istem času še ne dokazuje vzroka. Seznam odpuščanj beleži napovedi, ne števila dejansko odpuščenih ljudi, "
                    "in je po letu 2022 postal bolj znan, zato se je lahko povečalo tudi samo beleženje.",
    }


def explain_layoff_calendar(weekly: pd.Series) -> dict:
    iso = weekly.index.isocalendar()
    by_year = weekly.groupby(iso["year"].to_numpy()).sum()
    top_year = int(by_year.idxmax())
    top_week = weekly.idxmax()
    ordered = weekly.sort_values(ascending=False).to_numpy()
    k = int(np.searchsorted(np.cumsum(ordered), 0.5 * ordered.sum()) + 1)
    return {
        "kaj": "Vsaka vrstica je eno leto, vsak stolpec en teden v letu. Čim temnejše je polje, tem več odpuščanj so podjetja v tistem tednu napovedala. "
               "Prazna polja pomenijo, da za tisti teden nimamo podatkov. Ko miško premakneš na polje, vidiš točno število.",
        "zakaj": "Hoteli smo videti, ali so napovedi razporejene enakomerno ali pridejo v valovih.",
        "pomen": f"Največ napovedi je bilo leta {top_year} ({sl_num(by_year.max(), 0)}). Najbolj pretresljiv je bil teden z začetkom {_date(top_week)}, "
                 f"ko je bilo napovedanih {sl_num(weekly.max(), 0)} odpuščanj. Polovica vseh napovedi je padla v samo {k} od {len(weekly)} tednov, "
                 f"{'torej v zelo kratkih valovih.' if k < 0.25 * len(weekly) else 'torej so bile razmeroma enakomerno razporejene.'}",
        "omejitve": "Seznam odpuščanj se je začel marca 2020, zato so prvi tedni prazni. Pozna se tudi to, da se beležijo predvsem znana podjetja.",
    }


# ---------------------------------------------------------------------------------------- chapter 2
def explain_event_windows(weekly: pd.Series) -> dict:
    f, c = cs.event_study(weekly, cs.FED_HIKE), cs.event_study(weekly, cs.CHATGPT)
    jump = f["largest_jump_date"]
    weeks = int(round((jump - cs.FED_HIKE).days / 7))
    where = f"približno {abs(weeks)} tednov {'po' if weeks >= 0 else 'pred'} prvem zvišanju obrestne mere"
    return {
        "kaj": "Dva grafa: levi kaže tedne okoli prvega zvišanja obrestne mere Fed (16. 3. 2022), desni okoli izida ChatGPT (30. 11. 2022). "
               "Vsak stolpec je en teden, 26 tednov pred in 26 tednov po datumu. Siva polja so pred datumom, modra po njem, vodoravni črti "
               "pa kažeta povprečje pred in po.",
        "zakaj": "Pogosto slišimo, da sta ta dva trenutka prelomnici za odpuščanja. Preverili smo, ali se je število napovedi res spremenilo prav takrat.",
        "pomen": f"Okoli zvišanja obrestne mere je bilo povprečje {sl_num(f['before_mean'])} napovedi na teden pred datumom in {sl_num(f['after_mean'])} po njem. "
                 f"Okoli izida ChatGPT {sl_num(c['before_mean'])} pred in {sl_num(c['after_mean'])} po datumu, torej {_change(c['before_mean'], c['after_mean'])}. "
                 f"Če za vsak teden v celotnem obdobju izračunamo enako primerjavo, je največji skok v tednu z začetkom {_date(jump)}, {where}.",
        "omejitve": "Datuma sta le osem mesecev narazen in v istem obdobju padanja borze, zato ju podatki ne morejo ločiti. Poleg tega seznam odpuščanj ne pove, "
                    "ali je bil razlog umetna inteligenca, zato lahko le rečemo, kdaj se je število napovedi spremenilo, ne zakaj.",
    }


def explain_leadlag(tests: dict) -> dict:
    ev = {x: r for (x, y), r in tests.items() if y == "tracker events (3-month sum)"}
    other = [(y, r) for (x, y), r in tests.items() if y != "tracker events (3-month sum)"]
    parts, ev_sig = [], False
    for x, what in (("fedfunds_chg12", "s spremembo obrestne mere"), ("nasdaq_chg12", "s spremembo borze")):
        if x in ev:
            r = ev[x]
            sig = r["p_value"] < 0.05
            ev_sig |= sig
            parts.append(f"Število napovedi se ujema {what}: korelacija {sl_num(r['best_corr'], 2)}, p = {sl_num(r['p_value'], 2)}"
                         + (f", kar pomeni, da bi tako dobro ujemanje videli le v približno {sl_num(100 * r['p_value'], 0)} % naključnih premikov vrste po koledarju."
                            if sig else ", torej jasne povezave ni."))
    other_sig = False
    if other:
        ps = [r["p_value"] for _, r in other]
        other_sig = min(ps) < 0.05
        prange = f"p = {sl_num(ps[0], 2)}" if len(set(round(p, 2) for p in ps)) == 1 else f"p od {sl_num(min(ps), 2)} do {sl_num(max(ps), 2)}"
        parts.append("Pri številu odpuščenih ljudi in pri uradni statistiki (JOLTS) je vsaj ena povezava statistično opazna; poglej vrstice na grafu." if other_sig
                     else f"Pri številu odpuščenih ljudi in pri uradni statistiki (JOLTS) povezave ni videti ({prange}).")
    if ev_sig and not other_sig:
        parts.append("Z besedami: število napovedanih odpuščanj sledi obrestnim meram in borzi, a to ne pomeni nujno, da je odpuščenih več ljudi.")
    elif ev_sig and other_sig:
        parts.append("Z besedami: povezava ni omejena na število napovedi, vidi se tudi pri drugih merilih.")
    else:
        parts.append("Z besedami: v teh podatkih ne vidimo jasnega ujemanja makro številk z odpuščanji.")
    return {
        "kaj": "Vsaka vrstica primerja eno makro številko (kako se je v zadnjih 12 mesecih spremenila obrestna mera ali borza) z enim merilom odpuščanj. "
               "Stolpci so zamiki v mesecih: kaj dobimo, če odpuščanja primerjamo z makro podatkom izpred nekaj mesecev (pozitiven zamik) ali nekaj mesecev pozneje (negativen). "
               "Modra pomeni, da se vrsti premikata v isto smer, rdeča v nasprotno; zvezdica označuje najmočnejši zamik.",
        "zakaj": "Vprašali smo se, ali dražji denar in padec borze 'prehitevata' odpuščanja, in ali to velja za vsa merila: število napovedi, "
                 "število odpuščenih ljudi in uradno statistiko.",
        "pomen": " ".join(parts),
        "omejitve": "Imamo en cikel obrestnih mer in okoli šest let podatkov, zato se skoraj vsaki dve vrsti, ki v tem času rasteta ali padata, ujemata; test to upošteva le delno. "
                    "12-mesečna sprememba zaostaja za pravo spremembo, zato zamik +1 ne pomeni, da je obrestna mera delovala mesec prej. Vzroka s tem ne dokažemo.",
    }


def explain_overbuild(quartiles: dict[str, pd.DataFrame]) -> dict:
    boom, ob = quartiles["boom_growth"]["rate"].to_numpy(), quartiles["overbuild"]["rate"].to_numpy()
    boom_up, ob_up = bool(np.all(np.diff(boom) > 0)), bool(np.all(np.diff(ob) > 0))
    if boom_up and not ob_up:
        verdict = "Hitra rast torej gre z odpuščanji, kar pa še ne pomeni, da so podjetja zaposlovala preveč glede na prihodke."
    elif boom_up and ob_up:
        verdict = "Z odpuščanji gresta skupaj tako hitra rast kot hitrejša rast stroškov od prihodkov, kar je v skladu z razlago o prezaposlovanju."
    elif not boom_up and ob_up:
        verdict = "Z odpuščanji gre predvsem to, da stroški rastejo hitreje od prihodkov, ne pa sama hitrost rasti."
    else:
        verdict = "Niti hitra rast niti hitrejša rast stroškov od prihodkov ne gresta jasno z odpuščanji."
    return {
        "kaj": "Podjetja smo razvrstili v štiri enako velike skupine glede na to, kako hitro so rasla v letih 2019 do 2021: po rasti prihodkov, po rasti stroškov "
               "in po tem, ali so stroški rasli hitreje od prihodkov. Stolpec kaže, kolikšen delež podjetij iz skupine je v letih 2022 in 2023 napovedal odpuščanja.",
        "zakaj": "Preverjamo pogosto razlago, da so podjetja v času razcveta zaposlovala preveč in morala zato kasneje odpuščati.",
        "pomen": f"Med podjetji z najpočasnejšo rastjo prihodkov je odpuščanja napovedalo {sl_pct(boom[0])}, med najhitreje rastočimi {sl_pct(boom[-1])}; "
                 f"delež {'narašča iz skupine v skupino' if boom_up else 'ne narašča enakomerno'}. Če podjetja razvrstimo po tem, ali so stroški rasli hitreje od prihodkov, "
                 f"so deleži od {sl_pct(ob.min())} do {sl_pct(ob.max())} in {'naraščajo iz skupine v skupino' if ob_up else 'ne naraščajo enakomerno'}. {verdict}",
        "omejitve": "Nimamo števila zaposlenih, zato stroški le približno nadomeščajo zaposlovanje (vključujejo tudi nakupe podjetij in plačevanje z delnicami). "
                    "Hitro rastoča podjetja so pogosto bolj znana, zato jih seznam odpuščanj lažje zazna. V vsaki skupini je le nekaj deset podjetij, zato so razlike negotove.",
    }


# ---------------------------------------------------------------------------------------- chapter 3
def explain_size_deciles(panel: pd.DataFrame, n: int = 10) -> dict:
    d = panel.dropna(subset=["log_assets"]).copy()
    d["g"] = pd.qcut(d["log_assets"], n, labels=False, duplicates="drop")
    share = d.groupby("g")["y_next2q"].mean()
    lo, hi = share.iloc[0], share.iloc[-1]
    ratio = f"približno {_times(hi / lo)} pogosteje" if lo > 0 else "veliko pogosteje"
    return {
        "kaj": "Podjetja smo po vrednosti njihovih sredstev razdelili v deset enako velikih skupin: od najmanjših (1) do največjih (10). Stolpec kaže, "
               "v kolikšnem deležu četrtletij je podjetju v naslednjih dveh četrtletjih sledila napoved odpuščanj. Ko miško premakneš na stolpec, vidiš število četrtletij.",
        "zakaj": "Hoteli smo ugotoviti, kaj najbolj loči podjetja, ki se znajdejo na seznamu odpuščanj, od tistih, ki se ne.",
        "pomen": f"Pri najmanjših podjetjih je napovedi sledilo {sl_pct(lo, 1)} četrtletij, pri največjih {sl_pct(hi, 1)}"
                 + (f", torej {ratio}. Velikost podjetja je v naših podatkih zelo močno sporočilo." if hi > 1.5 * lo else
                    ". Velikost podjetja v teh podatkih ne ločuje jasno med podjetji z odpuščanji in brez njih."),
        "omejitve": "Veliko podjetje je tudi bolj opazno: seznam odpuščanj beleži predvsem znana podjetja. Velikost zato verjetno meri tudi to, kako zanesljivo je podjetje "
                    "sploh zabeleženo, ne le, kako veliko je tveganje za odpuščanja.",
    }


def explain_company_scatter(table: pd.DataFrame) -> dict:
    d = table.dropna(subset=["boom_growth", "log_assets_start"])
    big = d["log_assets_start"] >= d["log_assets_start"].median()
    fast = d["boom_growth"] >= d["boom_growth"].median()
    both = big & fast
    r_both, r_rest = float(d.loc[both, "y_layoff"].mean()), float(d.loc[~both, "y_layoff"].mean())
    ratio = r_both / r_rest if r_rest > 0 else np.inf
    how = (f"torej približno {_times(ratio)} pogosteje" if ratio >= 1.5 and np.isfinite(ratio) else
           "torej redkeje" if ratio <= 0.67 else "torej približno enako pogosto")
    return {
        "kaj": "Vsaka pika je eno podjetje. Vodoravno je velikost (sredstva ob koncu 2019; lestvica se z vsako črto podeseteri), navpično rast prihodkov med letoma 2019 in 2021. "
               "Rdeče pike so podjetja, ki so v letih 2022 in 2023 napovedala odpuščanja, sive tista, ki niso. Črtkani črti sta mediani: pol podjetij je levo od navpične črte, pol desno, in enako za vodoravno. "
               "Ko miško premakneš na piko, vidiš ime podjetja.",
        "zakaj": "Hoteli smo videti obe razlagi hkrati: ali odpuščajo predvsem velika podjetja, hitro rastoča podjetja ali oboja.",
        "pomen": f"Med {int(both.sum())} podjetji, ki so nad mediano tako po velikosti kot po rasti (zgornji desni kot), je odpuščanja napovedalo {sl_pct(r_both)}, "
                 f"med ostalimi {int((~both).sum())} pa {sl_pct(r_rest)}, {how}.",
        "omejitve": "Vsaka pika je le eno podjetje, zato so izjeme. Sredstva so le približek velikosti, rast prihodkov pa ne pove, koliko ljudi so podjetja zaposlila. "
                    "Seznam odpuščanj beleži predvsem znana podjetja, zato so velika podjetja že vnaprej bolj vidna.",
    }


def explain_model_comparison(sc: dict) -> dict:
    t = model_comparison_table(sc).set_index("label")
    base = t.loc["naključno (osnovna stopnja)", "pr_auc"]
    size = t.loc["samo velikost podjetja", "pr_auc"]
    lg, lg0 = t.loc[MODEL_LABELS["logit_size"]], t.loc[MODEL_LABELS["logit_nosize"]]
    te = sc["test"]
    n_pos, n_comp = int(te["y_next2q"].sum()), int(te.loc[te["y_next2q"] == 1, "cik"].nunique())
    since = str(te["quarter"].min())[:4]
    if lg0["pr_auc"] < 0.5 * lg["pr_auc"]:
        verdict = "Skoraj vse, kar modeli znajo, torej pride iz velikosti podjetja."
        move = f"pade na {sl_num(lg0['pr_auc'], 2)}"
    else:
        verdict = "Velikost je pomembna, a ni edino, kar modeli uporabijo."
        move = f"je {sl_num(lg0['pr_auc'], 2)}"
    return {
        "kaj": "Primerjamo, kako dobro različni modeli razvrstijo podjetja od tistih, ki bodo po vsej verjetnosti napovedala odpuščanja, do tistih, ki jih ne bodo. "
               "Mera se imenuje PR-AUC: višja vrednost pomeni, da so podjetja, ki so res napovedala odpuščanja, višje na seznamu. Črtkana črta je rezultat naključnega "
               "ugibanja. Črte na stolpcih kažejo negotovost (z 95-odstotno zanesljivostjo je prava vrednost nekje v tem območju).",
        "zakaj": "Zanimalo nas je, ali lahko iz javnih računovodskih podatkov podjetij vnaprej ocenimo, kdo bo napovedal odpuščanja, in še bolj, od česa je ta uspeh odvisen.",
        "pomen": f"Logistični model doseže {sl_num(lg['pr_auc'], 2)}, kar je {_times(lg['pr_auc'] / base)} boljše od naključja ({sl_num(base, 2)}). "
                 f"Samo velikost podjetja doseže {sl_num(size, 2)}. Ko modelu velikost vzamemo, {move} ({_times(lg0['pr_auc'] / base)} boljše od naključja). {verdict}",
        "omejitve": f"Preizkušali smo na {n_pos} napovedih odpuščanj, ki jih je dalo {n_comp} podjetij v letih od {since} naprej; učili smo se na starejših podatkih, ki jih je bilo bistveno manj. "
                    "Model zna razvrščati, ne zna pa zanesljivo povedati, kako verjetno je odpuščanje (verjetnosti so v povprečju prenizke). Ne pove nam tudi, zakaj podjetja odpuščajo.",
    }


def explain_size_group_lift(stratified: pd.DataFrame) -> dict:
    s = stratified

    def pick(g, m):
        r = s[(s["size_group"] == g) & (s["model"] == m)]
        return r.iloc[0] if len(r) else None

    small = s[s["size_group"] == 1].iloc[0]
    big_with, big_without, mid_with = pick(3, "logit_size"), pick(3, "logit_nosize"), pick(2, "logit_size")
    bits = []
    shrinks = None
    if big_with is not None and big_without is not None and not np.isnan(big_with["lift"]) and not np.isnan(big_without["lift"]):
        bits.append(f"Med največjimi podjetji je model z velikostjo {_times(big_with['lift'])} boljši od naključja, brez velikosti pa {_times(big_without['lift'])}.")
        shrinks = big_without["lift"] < 0.6 * big_with["lift"]
    if mid_with is not None and not np.isnan(mid_with["lift"]):
        bits.append(f"Med srednje velikimi podjetji je model {_times(mid_with['lift'])} boljši od naključja.")
    if shrinks is True:
        bits.append("Ko primerjamo podjetja podobne velikosti, napoved torej v veliki meri izgine: računovodski kazalniki (rast, marža, denar) povedo malo.")
    elif shrinks is False:
        bits.append("Tudi med podjetji podobne velikosti modela ostaneta precej boljša od naključja, kazalniki torej povedo nekaj tudi neodvisno od velikosti.")
    small_rows = f"{int(small['rows']):,}".replace(",", ".")
    small_txt = (f"V najmanjši tretjini je le {int(small['positives'])} napovedi odpuščanj med {small_rows} četrtletji, zato je izpustimo."
                 if np.isnan(small["lift"]) else
                 f"V najmanjši tretjini je {int(small['positives'])} napovedi odpuščanj med {small_rows} četrtletji, kar zadošča za oceno.")
    return {
        "kaj": "Podjetja smo razdelili v tretjine po velikosti. V vsaki tretjini vidimo, kolikokrat je model boljši od naključnega ugibanja (1 pomeni: nič boljši). "
               "Oranžni stolpci so modeli, ki poznajo velikost, modri tisti, ki je ne. Tretjine z občutno premalo napovedmi odpuščanj ne ocenjujemo.",
        "zakaj": "Če velikost približno držimo na isti ravni, vidimo, ali ostane še kaj, iz česar bi lahko ocenili tveganje.",
        "pomen": " ".join(bits) if bits else "Za nobeno tretjino ni dovolj napovedi odpuščanj, da bi lahko primerjali modele.",
        "omejitve": small_txt + " Tudi znotraj tretjine so podjetja različno velika, zato velikost ni popolnoma izenačena. "
                    "Število podjetij s pozitivnim izidom je omejeno, zato so razlike med modeli negotove.",
    }


# ---------------------------------------------------------------------------------------- chapter 6
def _spans_zero(lo: float, hi: float) -> bool:
    return lo <= 0 <= hi


def _placebo_sentence(placebo: dict | None, spans_zero: bool) -> str:
    """How trustworthy our significance test is, from the check on random non-event days."""
    if not placebo:
        return ""
    rate = placebo["bootstrap_false_positive_rate"]
    base = f" Preizkus na naključnih dnevih kaže, da naš test v {sl_pct(rate)} primerov zazna učinek, ki ga ni (pričakovanih je 5 %)."
    if rate <= 0.075:
        return base + " Test je torej dobro umerjen."
    return base + (" Intervali so zato nekoliko preozki, kar pri rezultatu, ki že zajema ničlo, sklepa ne spremeni." if spans_zero
                   else " Rezultat je zato treba jemati previdno.")


def explain_car_path(path: pd.DataFrame, summary: dict, placebo: dict | None = None) -> dict:
    mean, lo, hi, n = summary["mean_pct"], summary["ci_lo_pct"], summary["ci_hi_pct"], int(summary["n"])
    pre = path.set_index("t").loc[-2]
    pre_ok = _spans_zero(pre["lo_pct"], pre["hi_pct"])
    return {
        "kaj": f"Graf kaže, kako se je cena delnice v povprečju gibala v dneh okoli objave odpuščanj, ko od njenega gibanja odštejemo gibanje celotne borze "
               f"(temu rečemo nenavadni donos). Dan 0 je prvi trgovalni dan po objavi; sivo območje označuje dneva 0 in +1, ko borza novico prebavi. "
               f"Črta je povprečje preko {n} objav, modro območje je 95-odstotna negotovost. Ko miško premakneš na točko, vidiš vrednost.",
        "zakaj": "Zanima nas, ali vlagatelji objavo odpuščanj nagradijo ali kaznujejo, torej ali je za borzo novica dobra ali slaba.",
        "pomen": f"V dneh 0 in +1 se je cena v povprečju {'znižala' if mean < 0 else 'zvišala'} za {sl_num(abs(mean), 1)} % (negotovost od {sl_num(lo, 1)} % do {sl_num(hi, 1)} %). "
                 + ("Ker negotovost zajema ničlo, ne moremo trditi, da je sprememba več kot naključje. " if _spans_zero(lo, hi)
                    else "Ker negotovost ne zajema ničle, je sprememba statistično opazna. ")
                 + ("V dneh pred objavo ni opaznega premika, kar je dober znak: novica očitno ni pricurljala vnaprej." if pre_ok
                    else "Že v dneh pred objavo je viden premik, zato je cena morda padla prej in so podjetja odpuščala zaradi tega, ne obratno."),
        "omejitve": "Podjetja odpuščanja pogosto objavijo skupaj z rezultati poslovanja ali opozorili vlagateljem, zato učinka odpuščanj ne moremo ločiti od druge novice istega dne. "
                    "Datum na seznamu je lahko dan prepozen. Podjetja, ki so kasneje izginila z borze, v podatkih manjkajo. Gre za povprečje: posamezne objave se zelo razlikujejo."
                    + _placebo_sentence(placebo, _spans_zero(lo, hi)),
    }


def explain_car_distribution(cars: pd.DataFrame, summary: dict, window: str = "ann_0_1", clip: float = 20.0) -> dict:
    v = 100 * cars[f"car_{window}"].dropna()
    q50, q90 = float(v.abs().quantile(0.5)), float(v.abs().quantile(0.9))
    skew = abs(summary["mean_pct"]) > 3 * abs(summary["median_pct"]) and abs(summary["mean_pct"]) > 0.3
    return {
        "kaj": f"Vsak stolpec šteje, koliko objav je imelo določen nenavadni donos v dneh 0 in +1 (v odstotkih). Rdeča črta je povprečje, oranžna mediana (sredinska vrednost, "
               f"polovica objav je pod njo, polovica nad njo). Skrajne vrednosti smo skrčili na ±{sl_num(clip, 0)} %, da je graf berljiv.",
        "zakaj": "Povprečje lahko skriva, kako različne so posamezne objave, zato pogledamo vse.",
        "pomen": f"Pri polovici objav se je cena premaknila za manj kot {sl_num(q50, 1)} %, pri devetih od desetih za manj kot {sl_num(q90, 1)} %. "
                 f"Navzgor jo je potisnilo {sl_pct(summary['share_positive'])} objav, navzdol {sl_pct(1 - summary['share_positive'])}. Mediana je {sl_num(summary['median_pct'], 1)} %, "
                 f"povprečje {sl_num(summary['mean_pct'], 1)} %."
                 + (" Povprečje potegnejo posamezni skrajni primeri, zato je mediana pošteneje merilo tipične objave." if skew else ""),
        "omejitve": "Razpršenost je tudi posledica običajnega nihanja posameznih delnic, ne le novice o odpuščanjih. Z nekaj sto objavami lahko govorimo o skupini podjetij, ne o posameznem podjetju.",
    }


def explain_car_groups(by_size: pd.DataFrame, by_year: pd.DataFrame, diff: dict | None = None, min_n: int = 10) -> dict:
    order = ["najmanjša tretjina", "srednja tretjina", "največja tretjina"]
    sz = by_size.assign(k=by_size["size_group"].astype(str)).set_index("k").reindex(order).dropna(subset=["n"])
    yr = by_year[by_year["n"] >= min_n]
    parts = [f"{k}: {sl_num(r['mean_pct'], 1)} % (od {sl_num(r['ci_lo_pct'], 1)} do {sl_num(r['ci_hi_pct'], 1)} %)" for k, r in sz.iterrows()]
    sentence = "Po velikosti: " + "; ".join(parts) + "."
    if diff is not None:
        sentence += (f" Razlika med najmanjšimi in največjimi podjetji je {sl_num(diff['diff_pct'], 1)} odstotne točke (negotovost od {sl_num(diff['ci_lo_pct'], 1)} do {sl_num(diff['ci_hi_pct'], 1)}), "
                     + ("kar ni statistično zanesljivo." if _spans_zero(diff["ci_lo_pct"], diff["ci_hi_pct"]) else "kar je statistično opazno."))
    else:
        sentence += " Razlike med velikostnimi skupinami nismo posebej preizkusili."
    judged = yr.dropna(subset=["ci_lo_pct", "ci_hi_pct"])
    n_sig = int((~judged.apply(lambda r: _spans_zero(r["ci_lo_pct"], r["ci_hi_pct"]), axis=1)).sum()) if len(judged) else 0
    sentence += (f" Po letih pri nobenem letu negotovost ne izključuje ničle, zato jasnega vzorca ni." if n_sig == 0
                 else f" Po letih se pri {n_sig} od {len(judged)} let odziv statistično loči od nič.")
    return {
        "kaj": "Levo so podjetja razdeljena v tretjine po velikosti, desno po letu objave. Pika je povprečni nenavadni donos v dneh 0 in +1, črte kažejo 95-odstotno negotovost. "
               f"Če črta prečka ničlo, ne moremo reči, da se je cena sploh premaknila. Skupin z manj kot {min_n} objavami ne kažemo.",
        "zakaj": "Zanima nas, ali je odziv borze drugačen pri majhnih in velikih podjetjih ali v različnih letih, na primer med največjim valom odpuščanj leta 2022 in pozneje.",
        "pomen": sentence,
        "omejitve": "V posamezni skupini je od nekaj deset do dvesto objav, zato so razlike negotove. Hkrati primerjamo več skupin, zato je lahko katera 'opazna' razlika tudi naključna. "
                    "Velikost je merjena z vrednostjo sredstev pred objavo, ne z vrednostjo podjetja na borzi.",
    }


# ---------------------------------------------------------------------------------------- closing summary
def build_summary(story: dict) -> dict[str, list[str]]:
    """Plain-language conclusions for the end of the story, computed from the same data as the figures. 'zakljucki' follow the numbers;
    'odprto' lists what the data cannot tell us."""
    out = []
    w = story["weekly"]
    f, c = cs.event_study(w, cs.FED_HIKE), cs.event_study(w, cs.CHATGPT)
    if _change(f["before_mean"], f["after_mean"]) == "naraslo":
        out.append(f"**Kdaj:** napovedi odpuščanj so se močno povečale spomladi 2022. Pred prvim zvišanjem obrestne mere jih je bilo povprečno {sl_num(f['before_mean'])} na teden, po njem {sl_num(f['after_mean'])}. "
                   f"Ob izidu ChatGPT se je število {_change(c['before_mean'], c['after_mean'])} ({sl_num(c['before_mean'])} pred, {sl_num(c['after_mean'])} po).")
    else:
        out.append(f"**Kdaj:** ob prvem zvišanju obrestne mere se število napovedi ni jasno povečalo ({sl_num(f['before_mean'])} na teden pred, {sl_num(f['after_mean'])} po).")
    ev = {x: r for (x, y), r in story["tests"].items() if y == "tracker events (3-month sum)"}
    other = [r for (x, y), r in story["tests"].items() if y != "tracker events (3-month sum)"]
    ev_sig = [r for r in ev.values() if r["p_value"] < 0.05]
    other_sig = [r for r in other if r["p_value"] < 0.05]
    if ev_sig and not other_sig:
        out.append("**Zakaj:** število napovedi sledi obrestnim meram in borzi, števila odpuščenih ljudi in uradne statistike pa isti vzorec ne ujame. Seznam torej bolj kaže, kdaj so podjetja objavljala odpuščanja, kot koliko ljudi je izgubilo delo.")
    elif ev_sig:
        out.append("**Zakaj:** obrestne mere in borza se ujemajo s številom napovedi in tudi z vsaj enim drugim merilom odpuščanj.")
    else:
        out.append("**Zakaj:** obrestnih mer in borze v teh podatkih ne moremo jasno povezati z odpuščanji.")
    boom = story["quartiles"]["boom_growth"]["rate"].to_numpy()
    ob = story["quartiles"]["overbuild"]["rate"].to_numpy()
    if bool(np.all(np.diff(boom) > 0)) and not bool(np.all(np.diff(ob) > 0)):
        out.append(f"**Katera podjetja (rast):** podjetja, ki so v letih 2019 do 2021 najhitreje rasla, so pozneje pogosteje napovedala odpuščanja ({sl_pct(boom[-1])} proti {sl_pct(boom[0])} pri najpočasnejših), vendar ne zato, ker bi jim stroški rasli hitreje od prihodkov.")
    else:
        out.append(f"**Katera podjetja (rast):** deleži podjetij z odpuščanji po hitrosti rasti 2019 do 2021 se gibljejo od {sl_pct(boom.min())} do {sl_pct(boom.max())}; jasne razlage s prezaposlovanjem ne vidimo.")
    sc = story["size_control"]
    t = model_comparison_table(sc).set_index("label")
    lg, lg0, size = t.loc[MODEL_LABELS["logit_size"], "pr_auc"], t.loc[MODEL_LABELS["logit_nosize"], "pr_auc"], t.loc["samo velikost podjetja", "pr_auc"]
    if lg0 < 0.5 * lg:
        out.append(f"**Katera podjetja (velikost):** največ pove velikost podjetja. Samo z njo dosežemo {sl_num(size, 2)} (naključje {sl_num(t.iloc[0]['pr_auc'], 2)}), model z računovodskimi kazalniki {sl_num(lg, 2)}, brez velikosti pa {sl_num(lg0, 2)}.")
    else:
        out.append(f"**Katera podjetja (velikost):** velikost je pomembna ({sl_num(size, 2)}), a modeli brez nje še vedno dosežejo {sl_num(lg0, 2)} (naključje {sl_num(t.iloc[0]['pr_auc'], 2)}).")
    if story.get("stock"):
        sm = story["stock"]["summary"]
        out.append(f"**Borza:** ob objavi odpuščanj se cena delnice v povprečju {'znižala' if sm['mean_pct'] < 0 else 'zvišala'} za {sl_num(abs(sm['mean_pct']), 1)} % (negotovost od {sl_num(sm['ci_lo_pct'], 1)} do {sl_num(sm['ci_hi_pct'], 1)} %), "
                   + ("kar ni jasno več kot naključje." if _spans_zero(sm["ci_lo_pct"], sm["ci_hi_pct"]) else "kar je statistično opazno."))
    odprto = ["Seznam odpuščanj beleži napovedi predvsem znanih podjetij, ne vseh odpuščanj; tudi uradna statistika kaže manj dramatično sliko kot seznam.",
              "Vse povezave so povezave v času, ne dokaz vzroka: imamo en cikel obrestnih mer in nekaj sto podjetij.",
              "Nimamo števila zaposlenih in ne vemo, ali je bil razlog za odpuščanja umetna inteligenca.",
              "Podjetja, ki so kasneje izginila z borze, v podatkih o cenah manjkajo."]
    return {"zakljucki": out, "odprto": odprto}


def build_explanations(story: dict) -> dict[str, dict]:
    sc = story["size_control"]
    return {"1_casovnica": explain_timeline(story["weekly"], story["macro"]),
            "1_koledar": explain_layoff_calendar(story["weekly"]),
            "2_datumi": explain_event_windows(story["weekly"]),
            "2_zamiki": explain_leadlag(story["tests"]),
            "2_rast": explain_overbuild(story["quartiles"]),
            "3_velikost": explain_size_deciles(story["panel"]),
            "3_modeli": explain_model_comparison(sc),
            "3_skupine": explain_size_group_lift(sc["stratified"]),
            **({"3_podjetja": explain_company_scatter(story["boom_table"])} if story.get("boom_table") is not None else {}),
            **({"6_pot": explain_car_path(story["stock"]["path"], story["stock"]["summary"], story["stock"].get("placebo")),
                "6_porazdelitev": explain_car_distribution(story["stock"]["cars"], story["stock"]["summary"]),
                "6_skupine": explain_car_groups(story["stock"]["by_size"], story["stock"]["by_year"], story["stock"].get("diff"))}
               if story.get("stock") else {})}


def export_texts(story: dict) -> str:
    """Every explanation and the summary as one Markdown text, for proofreading outside the notebook."""
    from analysis.viz_theme import EXPLANATION_PARTS
    out = ["# Besedila zgodbe (za lektoriranje)", ""]
    for name, parts in build_explanations(story).items():
        out.append(f"## {name}")
        for key, heading in EXPLANATION_PARTS:
            out.append(f"**{heading}** {parts[key]}")
            out.append("")
    summ = build_summary(story)
    out += ["## povzetek", "", "**Kaj smo se naučili**", ""] + [f"- {x}" for x in summ["zakljucki"]] + ["", "**Česa ne vemo**", ""] + [f"- {x}" for x in summ["odprto"]]
    return "\n".join(out) + "\n"


def main() -> None:
    import sys
    from analysis import viz
    from analysis.viz_theme import ROOT
    if sys.argv[1:] != ["export"]:
        raise SystemExit("usage: python -m analysis.story_text export")
    path = ROOT / "reports" / "zgodba_besedila.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(export_texts(viz.prepare_story_data()), encoding="utf-8")
    print(f"written {path}")


if __name__ == "__main__":
    main()
