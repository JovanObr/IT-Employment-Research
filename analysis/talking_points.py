"""Spoken versions of the story (Slovenian, about 30 seconds each) for a live, informal presentation.

`collect_facts(story)` pulls the few numbers each script needs from the same data as the figures; `render(facts)` turns them into text whose wording
follows the numbers (so a script never says 'naraslo' where the data fell). Run  python -m analysis.talking_points  to write reports/zgodba_govor.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import causes as cs
from analysis.viz_theme import sl_num, sl_pct


def _spans_zero(lo, hi):
    return lo <= 0 <= hi


def _series(fl: pd.DataFrame, flag: str) -> pd.Series:
    f = fl[fl["flag"] == flag]
    return pd.Series(f["share"].to_numpy(float), index=pd.to_datetime(f["month"])).sort_index().dropna()


def collect_facts(story: dict) -> dict:
    """Numbers for the scripts. Keys that cannot be computed (a chapter without data) are simply absent."""
    from analysis.story_text import model_comparison_table, MODEL_LABELS
    f: dict = {}
    w = story["weekly"]
    fh, gp = cs.event_study(w, cs.FED_HIKE), cs.event_study(w, cs.CHATGPT)
    f.update(hike_before=fh["before_mean"], hike_after=fh["after_mean"], gpt_before=gp["before_mean"], gpt_after=gp["after_mean"])
    ev = {x: r for (x, y), r in story["tests"].items() if y == "tracker events (3-month sum)"}
    other = [r for (x, y), r in story["tests"].items() if y != "tracker events (3-month sum)"]
    f["ev_sig"] = any(r["p_value"] < 0.05 for r in ev.values())
    f["other_sig"] = any(r["p_value"] < 0.05 for r in other)
    if "fedfunds_chg12" in ev and "nasdaq_chg12" in ev:
        f.update(corr_fed=ev["fedfunds_chg12"]["best_corr"], corr_nasdaq=ev["nasdaq_chg12"]["best_corr"])
    boom, ob = story["quartiles"]["boom_growth"]["rate"].to_numpy(), story["quartiles"]["overbuild"]["rate"].to_numpy()
    f.update(boom_first=float(boom[0]), boom_last=float(boom[-1]), boom_up=bool(np.all(np.diff(boom) > 0)), ob_up=bool(np.all(np.diff(ob) > 0)))
    t = model_comparison_table(story["size_control"]).set_index("label")
    f.update(base=float(t.iloc[0]["pr_auc"]), size_only=float(t.loc["samo velikost podjetja", "pr_auc"]),
             logit=float(t.loc[MODEL_LABELS["logit_size"], "pr_auc"]), logit_nosize=float(t.loc[MODEL_LABELS["logit_nosize"], "pr_auc"]))
    hn = story.get("hn")
    if hn and hn.get("flags") is not None:
        rem, ai = _series(hn["flags"], "remote"), _series(hn["flags"], "ai_ml")
        if len(rem) >= 24 and len(ai) >= 24:
            has19 = (rem.index.year == 2019).any()
            roll = rem.rolling(12).mean()
            pm = roll.idxmax()
            f.update(remote_base=float(rem[rem.index.year == 2019].mean() if has19 else rem.iloc[:12].mean()), remote_base_label="leta 2019" if has19 else "na začetku",
                     remote_peak=float(roll.max()), remote_peak_month=f"{pm.month}/{pm.year}", remote_last=float(rem.iloc[-12:].mean()),
                     ai_first=float(ai.iloc[:12].mean()), ai_last=float(ai.iloc[-12:].mean()))
    if story.get("geo") is not None:
        from analysis.geo import in_lower48
        g = story["geo"].dropna(subset=["lat", "lon"])
        g = g[in_lower48(g["lon"], g["lat"])]
        ok = g["usable"].astype(bool) & g["it_growth_pct"].notna()
        if ok.any():
            f.update(geo_n=int(ok.sum()), geo_up=float((g.loc[ok, "it_growth_pct"] > 0).mean()), geo_med=float(g.loc[ok, "it_growth_pct"].median()),
                     geo_hidden=int((~ok).sum()))
    if story.get("stock"):
        s = story["stock"]["summary"]
        f.update(stock_mean=s["mean_pct"], stock_lo=s["ci_lo_pct"], stock_hi=s["ci_hi_pct"])
        d = story["stock"].get("diff")
        if d:
            f.update(gap=d["diff_pct"], gap_lo=d["ci_lo_pct"], gap_hi=d["ci_hi_pct"])
    return f


def _say(x: float, digits: int = 1) -> str:
    """A number as it is spoken: 'minus 1,3' instead of '-1,3'."""
    return f"minus {sl_num(abs(x), digits)}" if x < 0 else sl_num(x, digits)


def _gpt_phrase(b: float, a: float) -> str:
    if b > 0 and abs(a - b) / b < 0.10:
        return f"se število skoraj ni spremenilo ({sl_num(b)} pred, {sl_num(a)} po)"
    return f"se je število {'povečalo' if a > b else 'zmanjšalo'} ({sl_num(b)} pred, {sl_num(a)} po)"


def render(f: dict) -> list[tuple[str, str]]:
    out = [("Uvod", "Zanimalo nas je, kaj se je zgodilo s tehnološkimi službami po koronavirusu. Pogledali smo šest stvari: kdaj so podjetja napovedovala odpuščanja, "
                    "zakaj ravno takrat, katera podjetja so bila na udaru, kaj iščejo delodajalci, kje v ZDA se je delo spremenilo in kako se je odzvala borza. "
                    "Grafi so interaktivni, pod vsakim so štiri kratke razlage, med njimi tudi: česa ne vemo.")]
    surge = f["hike_after"] > 1.1 * f["hike_before"]
    flat_gpt = f["gpt_before"] > 0 and abs(f["gpt_after"] - f["gpt_before"]) / f["gpt_before"] < 0.10
    t1 = (f"Prvi graf postavi na isto os odpuščanja, obrestno mero in borzo. Pred prvim zvišanjem obrestne mere je bilo povprečno {sl_num(f['hike_before'])} napovedi odpuščanj na teden, "
          f"po njem {sl_num(f['hike_after'])}. Ob izidu ChatGPT {_gpt_phrase(f['gpt_before'], f['gpt_after'])}. ")
    t1 += ("Val je torej prišel spomladi 2022, ne ob ChatGPT. " if surge and flat_gpt else "")
    t1 += "Pozor: seznam beleži napovedi znanih podjetij, ne vseh odpuščanj."
    out.append(("1. Kdaj", t1))
    if f["ev_sig"] and not f["other_sig"] and "corr_fed" in f:
        a = (f"Število napovedi sledi obrestnim meram (korelacija {_say(f['corr_fed'], 2)}) in borzi"
             + (f", a v nasprotni smeri: ko borza pade, je napovedi več (korelacija {_say(f['corr_nasdaq'], 2)}). " if f["corr_nasdaq"] < 0
                else f" (korelacija {_say(f['corr_nasdaq'], 2)}). ")
             + "Števila odpuščenih ljudi in uradne statistike pa isti vzorec ne ujame. ")
    elif f["ev_sig"]:
        a = "Število napovedi se ujema z obrestnimi merami in borzo, pa tudi z vsaj enim drugim merilom. "
    else:
        a = "Obrestnih mer in borze v teh podatkih ne moremo jasno povezati z odpuščanji. "
    if f["boom_up"] and not f["ob_up"]:
        b = (f"Podjetja, ki so v letih 2019 do 2021 najhitreje rasla, so pozneje odpuščala pogosteje: {sl_pct(f['boom_last'])} proti {sl_pct(f['boom_first'])} pri najpočasnejših, "
             f"vendar ne zato, ker bi jim stroški rasli hitreje od prihodkov. ")
    elif f["boom_up"] and f["ob_up"]:
        b = f"Hitro rastoča podjetja so pozneje odpuščala pogosteje ({sl_pct(f['boom_last'])} proti {sl_pct(f['boom_first'])}), tudi tista, ki jim je strošek rasel hitreje od prihodkov. "
    else:
        b = "Razlage s prezaposlovanjem v teh podatkih ne vidimo jasno. "
    out.append(("2. Zakaj", "Pri vprašanju zakaj smo preverili tri razlage: obrestne mere in borzo, dva znana datuma in prezaposlovanje. " + a + b + "Vse to so povezave, ne dokazi vzroka."))
    if f["logit_nosize"] < 0.5 * f["logit"]:
        c = f"Največ pove velikost podjetja. Samo z njo dosežemo {sl_num(f['size_only'], 2)}, model z računovodskimi kazalniki {sl_num(f['logit'], 2)}, naključje {sl_num(f['base'], 2)}. Ko modelu velikost vzamemo, pade na {sl_num(f['logit_nosize'], 2)}. "
    else:
        c = f"Velikost je pomembna ({sl_num(f['size_only'], 2)}), a modeli brez nje še vedno dosežejo {sl_num(f['logit_nosize'], 2)} (naključje {sl_num(f['base'], 2)}). "
    out.append(("3. Katera podjetja", c + "Na grafu s pikami lahko miško premaknete na posamezno podjetje: rdeča so tista, ki so napovedala odpuščanja."))
    if "remote_base" in f:
        rem = (f"Pri objavah delodajalcev na Hacker Newsu je delež omemb dela na daljavo {f['remote_base_label']} znašal {sl_pct(f['remote_base'])}, "
               f"na vrhuncu ({f['remote_peak_month']}) {sl_pct(f['remote_peak'])}, v zadnjih 12 mesecih pa {sl_pct(f['remote_last'])}. ")
        ai_word = "ostal podoben" if abs(f["ai_last"] - f["ai_first"]) < 0.01 else ("zrasel" if f["ai_last"] > f["ai_first"] else "padel")
        ai = f"Delež omemb umetne inteligence je {ai_word} z {sl_pct(f['ai_first'])} v prvih 12 mesecih na {sl_pct(f['ai_last'])} v zadnjih 12 mesecih. "
        out.append(("4. Kaj iščejo delodajalci", rem + ai + "Pozor: to je kotiček trga s prevlado zagonskih podjetij, ne vsi delodajalci."))
    if "geo_n" in f:
        out.append(("5. Kje", f"Na zemljevidu vidimo IT delovna mesta po ameriških metropolitanskih območjih. Med {f['geo_n']} območji z uporabnim podatkom se je zaposlenost med letoma 2019 in 2024 "
                              f"povečala v {sl_pct(f['geo_up'])} območij, pri tipičnem območju za {sl_num(abs(f['geo_med']), 1)} %{'' if f['geo_med'] > 0 else ' (padec)'}. "
                              f"Za {f['geo_hidden']} območij je podatek skrit, in skrit ni nič. Z menijem lahko preklopite med dvema merilami rasti."))
    if "stock_mean" in f:
        zero = _spans_zero(f["stock_lo"], f["stock_hi"])
        s6 = (f"Za konec borza. Ob objavi odpuščanj se je cena delnice v dveh dneh v povprečju {'znižala' if f['stock_mean'] < 0 else 'zvišala'} za {sl_num(abs(f['stock_mean']), 1)} %, "
              f"a negotovost je od {_say(f['stock_lo'])} do {_say(f['stock_hi'])} %, torej {'ni jasno več kot naključje' if zero else 'je sprememba statistično opazna'}. ")
        if "gap" in f:
            s6 += (f"Pri manjših podjetjih je odziv {'bolj negativen' if f['gap'] < 0 else 'bolj pozitiven'} kot pri največjih (razlika {sl_num(abs(f['gap']), 1)} odstotne točke), "
                   f"vendar {'ni zanesljiva' if _spans_zero(f['gap_lo'], f['gap_hi']) else 'je zanesljiva'}.")
        out.append(("6. Borza", s6))
    quiet = "borza pa se ni jasno odzvala" if "stock_mean" not in f or _spans_zero(f["stock_lo"], f["stock_hi"]) else "borza pa se je odzvala"
    out.append(("Zaključek", f"Skratka: odpuščanja so {'prišla z dražjim denarjem in padcem borze' if f['ev_sig'] else 'v teh podatkih niso jasno povezana z obrestnimi merami'}, "
                             f"najpogosteje pri velikih podjetjih, {quiet}. Česa ne vemo: ali je za tem umetna inteligenca, koliko ljudi je dejansko izgubilo delo, in vzroka, saj gre za povezave v času."))
    return out


def to_markdown(points: list[tuple[str, str]]) -> str:
    lines = ["# Govor (približno 30 sekund na poglavje)", ""]
    for title, text in points:
        lines += [f"## {title}  ({len(text.split())} besed)", "", text, ""]
    return "\n".join(lines)


def main() -> None:
    from analysis import viz
    from analysis.viz_theme import ROOT
    story = viz.prepare_story_data()
    write(story)


def write(story: dict) -> None:
    from analysis.viz_theme import ROOT
    path = ROOT / "reports" / "zgodba_govor.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(render(collect_facts(story))), encoding="utf-8")
    print(f"written {path}")


if __name__ == "__main__":
    main()
