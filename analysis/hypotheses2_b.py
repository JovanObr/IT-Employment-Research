"""Round 2, Stream B: the pre-registered tests A2 and F (docs/hypotheses/round2/A2_F.md, registered in commit fdd6e00), and the
exploratory Slovenia check B1 (no test, no verdict).

A2  Catch-up across the EU-27: OLS slope of the change in the ICT share 2021 -> 2024 on the 2019-2020 mean level; two-sided
    permutation p (10,000), bootstrap interval over countries (5,000). Predicted b < 0.
F   East vs. West Coast: Mann-Whitney U of IT job growth 2019 -> 2024 (metro_map_data.csv, usable metros), West vs. East by state
    list; difference in medians (West - East) with a bootstrap interval. Predicted negative.
B1  Slovenia's ICT share 2015-2025 against the EU-27 and the range of the other countries, its rank, absolute vs. relative change,
    and the number of ICT specialists (Eurostat unit THS_PER). Exploratory.

Follow the registration exactly; any change after the real run is a dated amendment in the registration file. Choices the
registration leaves open, fixed here before the real run:
- A2: a country "has" a year only if its PC_EMP value is a number (as in round 1); flagged cells are used as published and listed.
- A2 bootstrap: resamples with fewer than 3 distinct start levels are skipped (the slope is undefined).
- A2 Slovenia: rank 1 = the largest (most positive) residual, as in round 1's rank of changes.
- F: the state is the first two-letter code after the first comma of `metro_name`; metros without a comma are out.
- F placebo: groups drawn without replacement from all usable metros, the West group first, then the East group from the rest.

    python -m analysis.hypotheses2_b         # runs A2, F and B1 on the local files, writes reports/hypotheses2_b_results.json
"""
from __future__ import annotations

import json
import logging
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from analysis.hypotheses import ALPHA, file_hashes
from analysis.hypotheses_b import EU27, _a_wide, _clean, estimated_flags
from analysis.viz_theme import PALETTE, base_layout, sl_num

log = logging.getLogger("covid_it_data")

# ---------------------------------------------------------------------------------------- constants (registration)
A2_START_YEARS = (2019, 2020)
A2_YEARS = (2021, 2024)
A2_YEARS_2025 = (2021, 2025)
A2_NOISE_YEARS = tuple(range(2015, 2021))
A2_BREAK_YEAR = 2021
WEST = ("WA", "OR", "CA")
EAST = ("ME", "NH", "MA", "RI", "CT", "NY", "NJ", "PA", "DE", "MD", "VA", "NC", "SC", "GA", "FL", "DC")
F_BIG = 1000.0                        # secondary: at least 1,000 IT jobs in 2019
MW_EFFICIENCY = 3 / math.pi           # asymptotic relative efficiency of Mann-Whitney vs. t under normality (0.955)
B1_YEARS = tuple(range(2015, 2026))

EU_SL = {"AT": "Avstrija", "BE": "Belgija", "BG": "Bolgarija", "CY": "Ciper", "CZ": "Češka", "DE": "Nemčija", "DK": "Danska",
         "EE": "Estonija", "EL": "Grčija", "ES": "Španija", "FI": "Finska", "FR": "Francija", "HR": "Hrvaška", "HU": "Madžarska",
         "IE": "Irska", "IT": "Italija", "LT": "Litva", "LU": "Luksemburg", "LV": "Latvija", "MT": "Malta", "NL": "Nizozemska",
         "PL": "Poljska", "PT": "Portugalska", "RO": "Romunija", "SE": "Švedska", "SI": "Slovenija", "SK": "Slovaška"}


def _z80() -> float:
    return float(stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(0.8))


# ======================================================================================== A2
def a2_data(eurostat: pd.DataFrame, countries=EU27) -> pd.DataFrame:
    """One row per country: start (mean 2019-2020), level_2021, change (2024 - 2021), change_2025 (2025 - 2021), rel_change (%)."""
    years = sorted(set(A2_START_YEARS) | set(A2_YEARS) | set(A2_YEARS_2025))
    w = _a_wide(eurostat, years, countries)
    d = pd.DataFrame({"start": w[list(A2_START_YEARS)].mean(axis=1), "level_2021": w[2021], "level_2024": w[2024],
                      "change": w[2024] - w[2021], "change_2025": w[2025] - w[2021],
                      "rel_change": 100 * (w[2024] / w[2021] - 1)}).astype(float)
    d.index.name = "country"
    return d


def slope(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """OLS slope and intercept of y on x."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    xc = x - x.mean()
    b = float(xc @ (y - y.mean()) / (xc @ xc))
    return b, float(y.mean() - b * x.mean())


def perm_slope_p(x: np.ndarray, y: np.ndarray, n_perm: int, rng) -> tuple[float, np.ndarray]:
    """Two-sided permutation p of the OLS slope: y shuffled across units; p = (#|b_perm| >= |b_obs| + 1) / (n_perm + 1)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    xc = x - x.mean()
    obs = float(xc @ (y - y.mean()) / (xc @ xc))
    Y = np.array([rng.permutation(y) for _ in range(n_perm)])
    null = (Y - Y.mean(axis=1, keepdims=True)) @ xc / (xc @ xc)
    return float((np.sum(np.abs(null) >= abs(obs) - 1e-12) + 1) / (n_perm + 1)), null


def _ols_p(x: np.ndarray, y: np.ndarray) -> float:
    r = stats.linregress(np.asarray(x, float), np.asarray(y, float))
    return float(r.pvalue)


def test_a2(d: pd.DataFrame, x: str = "start", y: str = "change", n_perm: int = 10000, n_boot: int = 5000, seed: int = 0) -> dict:
    """Primary test A2 (registered): slope of `y` on `x`, two-sided permutation p, bootstrap interval over countries."""
    xs, ys = d[x].to_numpy(float), d[y].to_numpy(float)
    rng = np.random.default_rng(seed)
    b, a = slope(xs, ys)
    p, _ = perm_slope_p(xs, ys, n_perm, rng)
    boots = []
    n = len(xs)
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        if len(np.unique(xs[i])) < 3:
            continue
        boots.append(slope(xs[i], ys[i])[0])
    r = float(np.corrcoef(xs, ys)[0, 1])
    return {"n": int(n), "x": x, "y": y, "b": b, "intercept": a, "ci_lo": float(np.percentile(boots, 2.5)),
            "ci_hi": float(np.percentile(boots, 97.5)), "p": p, "p_ols": _ols_p(xs, ys), "r": r, "predicted_sign": bool(b < 0),
            "n_perm": n_perm, "n_boot": len(boots), "mde_abs_r": mde_r(n)}


def mde_r(n: int) -> float:
    """Smallest |correlation| detectable with 80 % power at alpha 0.05 (Fisher z)."""
    return float(np.tanh(_z80() / math.sqrt(n - 3)))


def slovenia_a2(d: pd.DataFrame, country: str = "SI") -> dict:
    """Slovenia against the line fitted on the other countries: residual, prediction-interval t (df m - 2), rank of its residual in
    the full fit (1 = largest residual). Descriptive, no verdict."""
    o = d.drop(country)
    x, y = o["start"].to_numpy(float), o["change"].to_numpy(float)
    b, a = slope(x, y)
    m = len(o)
    res = y - (a + b * x)
    s = math.sqrt(res @ res / (m - 2))
    x0, y0 = float(d.at[country, "start"]), float(d.at[country, "change"])
    pred = a + b * x0
    se = s * math.sqrt(1 + 1 / m + (x0 - x.mean()) ** 2 / ((x - x.mean()) @ (x - x.mean())))
    t = (y0 - pred) / se
    bf, af = slope(d["start"], d["change"])
    full_res = d["change"] - (af + bf * d["start"])
    return {"country": country, "start": x0, "change": y0, "predicted_change": float(pred), "residual": float(y0 - pred),
            "pi_t": float(t), "pi_p": float(2 * stats.t.sf(abs(t), df=m - 2)), "df": m - 2, "b_without": b,
            "residual_full": float(full_res[country]), "rank_residual_full": int(1 + (full_res > full_res[country]).sum()),
            "n": int(len(d)), "start_rank": int(1 + (d["start"] > x0).sum())}


def noise_sigma(eurostat: pd.DataFrame, years=A2_NOISE_YEARS, countries=EU27) -> dict:
    """Measured noise: root mean square over countries of the residual sd of a linear trend fitted to each country's years."""
    w = _a_wide(eurostat, years, countries)
    t = np.array(years, float)
    sds = {}
    for c, row in w.iterrows():
        yv = row.to_numpy(float)
        b, a = slope(t, yv)
        r = yv - (a + b * t)
        sds[c] = float(math.sqrt(r @ r / (len(t) - 2)))
    return {"sigma": float(math.sqrt(np.mean(np.square(list(sds.values()))))), "years": list(years), "by_country": sds}


def simulate_a2(start: np.ndarray, mean_change: float, sd_true: float, sigma: float, rng) -> tuple[np.ndarray, ...]:
    """One simulated world without catch-up: returns (start, naive start = 2021 value, change 2021 -> 2024)."""
    n = len(start)
    true_change = rng.normal(mean_change, sd_true, n)
    y19, y20, y21 = (start + rng.normal(0, sigma, n) for _ in range(3))
    y24 = start + true_change + rng.normal(0, sigma, n)
    return (y19 + y20) / 2, y21, y24 - y21


def placebo_a2(d: pd.DataFrame, sigma: float, n_sim: int = 2000, n_perm: int = 1000, seed: int = 2) -> dict:
    """Registered placebo: no catch-up by construction, noise sd sigma; share of simulated data sets with p < 0.05 for the
    registered design (2019-2020 start) and for the naive 2021-start design."""
    rng = np.random.default_rng(seed)
    start = d["start"].to_numpy(float)
    mean_change = float(d["change"].mean())
    sd_true = float(math.sqrt(max(d["change"].var(ddof=1) - 2 * sigma ** 2, 0.0)))
    rej, rej_naive, slopes_naive = 0, 0, []
    for _ in range(n_sim):
        s, s21, ch = simulate_a2(start, mean_change, sd_true, sigma, rng)
        rej += perm_slope_p(s, ch, n_perm, rng)[0] < ALPHA
        pn, _ = perm_slope_p(s21, ch, n_perm, rng)
        rej_naive += pn < ALPHA
        slopes_naive.append(slope(s21, ch)[0])
    return {"n_sim": n_sim, "n_perm": n_perm, "sigma": sigma, "sd_true": sd_true, "mean_change": mean_change,
            "share_p_below_005": rej / n_sim, "share_p_below_005_naive": rej_naive / n_sim,
            "mean_slope_naive": float(np.mean(slopes_naive))}


def secondary_a2(d: pd.DataFrame, eurostat: pd.DataFrame, n_perm: int = 10000) -> dict:
    keep = ("b", "ci_lo", "ci_hi", "p", "p_ols", "r", "predicted_sign", "n")
    pick = lambda r: {k: r[k] for k in keep}
    rho = stats.spearmanr(d["start"], d["change"])
    return {"naive_start_2021": pick(test_a2(d, x="level_2021", n_perm=n_perm)),
            "spearman": {"rho": float(rho.statistic), "p": float(rho.pvalue)},
            "relative_change": pick(test_a2(d, y="rel_change", n_perm=n_perm)),
            "change_2021_2025": pick(test_a2(d, y="change_2025", n_perm=n_perm)),
            "without_slovenia": pick(test_a2(d.drop("SI"), n_perm=n_perm)),
            "flagged_cells": estimated_flags(eurostat, years=sorted(set(A2_START_YEARS) | set(A2_YEARS) | {2025}))}


def run_a2(eurostat: pd.DataFrame) -> dict:
    d = a2_data(eurostat)
    noise = noise_sigma(eurostat)
    return {"primary": test_a2(d), "slovenia": slovenia_a2(d), "secondary": secondary_a2(d, eurostat),
            "placebo": placebo_a2(d, noise["sigma"]), "noise": noise,
            "values": {c: {k: float(v) for k, v in row.items()} for c, row in d.iterrows()}}


# ======================================================================================== F
def state_of(metro_name: str) -> str | None:
    """First state code after the first comma ('New York-Newark-Jersey City, NY-NJ-PA Metro Area' -> 'NY')."""
    parts = str(metro_name).split(",")
    if len(parts) < 2 or not parts[1].strip():
        return None
    return parts[1].strip().split()[0].split("-")[0]


def coast_of(metro_name: str) -> str | None:
    s = state_of(metro_name)
    return "west" if s in WEST else "east" if s in EAST else None


def _true(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(["true", "1"])


def f_data(geo: pd.DataFrame) -> pd.DataFrame:
    """The map table with coast, state, usable flags as booleans and numeric growth and levels."""
    g = geo.copy()
    g["state"] = g["metro_name"].map(state_of)
    g["coast"] = g["metro_name"].map(coast_of)
    g["usable"] = _true(g["usable"])
    g["usable_estab"] = _true(g["usable_estab"]) if "usable_estab" in g else False
    for c in ("it_growth_pct", "emp_it_2019", "emp_it_2024", "estab_growth_pct"):
        if c in g:
            g[c] = pd.to_numeric(g[c], errors="coerce")
    return g


def _median_diff(w: np.ndarray, e: np.ndarray) -> float:
    return float(np.median(w) - np.median(e))


def mann_whitney(w: np.ndarray, e: np.ndarray) -> dict:
    r = stats.mannwhitneyu(w, e, alternative="two-sided", method="asymptotic", use_continuity=True)
    return {"u": float(r.statistic), "p": float(r.pvalue), "prob_west_higher": float(r.statistic / (len(w) * len(e)))}


def mde_d(n1: int, n0: int) -> float:
    """Minimum detectable shift in standard deviations for Mann-Whitney (normal approximation divided by sqrt(efficiency))."""
    return float(_z80() * math.sqrt(1 / n1 + 1 / n0) / math.sqrt(MW_EFFICIENCY))


def test_f(g: pd.DataFrame, n_boot: int = 5000, seed: int = 0, col: str = "it_growth_pct", usable: str = "usable") -> dict:
    """Primary test F (registered): Mann-Whitney West vs. East; difference in medians with a bootstrap interval (within coast)."""
    u = g[g[usable] & g[col].notna()]
    w, e = u.loc[u["coast"] == "west", col].to_numpy(float), u.loc[u["coast"] == "east", col].to_numpy(float)
    rng = np.random.default_rng(seed)
    mw = mann_whitney(w, e)
    boots = [_median_diff(rng.choice(w, len(w)), rng.choice(e, len(e))) for _ in range(n_boot)]
    diff = _median_diff(w, e)
    d = mde_d(len(w), len(e))
    return {"n_west": int(len(w)), "n_east": int(len(e)),
            "n_withheld_west": int(((g["coast"] == "west") & ~g[usable]).sum()),
            "n_withheld_east": int(((g["coast"] == "east") & ~g[usable]).sum()),
            "median_west": float(np.median(w)), "median_east": float(np.median(e)), "diff_median": diff,
            "ci_lo": float(np.percentile(boots, 2.5)), "ci_hi": float(np.percentile(boots, 97.5)), **mw,
            "predicted_sign": bool(diff < 0), "mde_sd": d, "mde_prob": float(stats.norm.cdf(d / math.sqrt(2)))}


def weighted_growth(sub: pd.DataFrame) -> float:
    return float(100 * (sub["emp_it_2024"].sum() / sub["emp_it_2019"].sum() - 1))


def secondary_f(g: pd.DataFrame, n_boot: int = 5000, seed: int = 3) -> dict:
    u = g[g["usable"] & g["it_growth_pct"].notna() & g["coast"].notna()]
    w, e = u[u["coast"] == "west"], u[u["coast"] == "east"]
    rng = np.random.default_rng(seed)
    boots = [weighted_growth(w.iloc[rng.integers(0, len(w), len(w))]) - weighted_growth(e.iloc[rng.integers(0, len(e), len(e))])
             for _ in range(n_boot)]
    out = {"weighted": {"west": weighted_growth(w), "east": weighted_growth(e), "diff": weighted_growth(w) - weighted_growth(e),
                        "ci_lo": float(np.percentile(boots, 2.5)), "ci_hi": float(np.percentile(boots, 97.5)),
                        "jobs_2019_west": float(w["emp_it_2019"].sum()), "jobs_2019_east": float(e["emp_it_2019"].sum())}}
    big = u[u["emp_it_2019"] >= F_BIG]
    bw, be = big.loc[big["coast"] == "west", "it_growth_pct"], big.loc[big["coast"] == "east", "it_growth_pct"]
    out["big_metros"] = {"n_west": int(len(bw)), "n_east": int(len(be)), "median_west": float(bw.median()),
                         "median_east": float(be.median()), **mann_whitney(bw.to_numpy(float), be.to_numpy(float))}
    if "estab_growth_pct" in g:
        r = test_f(g, n_boot=1000, col="estab_growth_pct", usable="usable_estab")
        out["establishments"] = {k: r[k] for k in ("n_west", "n_east", "median_west", "median_east", "diff_median", "ci_lo", "ci_hi",
                                                     "p", "prob_west_higher")}
    return out


def placebo_f(g: pd.DataFrame, n_west: int, n_east: int, n_rep: int = 1000, seed: int = 4) -> dict:
    """Registered placebo: groups of the same sizes drawn at random from all usable metros (any state); share with p < 0.05."""
    pool = g.loc[g["usable"] & g["it_growth_pct"].notna(), "it_growth_pct"].to_numpy(float)
    rng = np.random.default_rng(seed)
    ps = []
    for _ in range(n_rep):
        idx = rng.permutation(len(pool))
        ps.append(mann_whitney(pool[idx[:n_west]], pool[idx[n_west:n_west + n_east]])["p"])
    return {"n_rep": n_rep, "pool": int(len(pool)), "share_p_below_005": float(np.mean(np.array(ps) < ALPHA))}


def run_f(geo: pd.DataFrame) -> dict:
    g = f_data(geo)
    primary = test_f(g)
    u = g[g["usable"] & g["coast"].notna()]
    return {"primary": primary, "secondary": secondary_f(g), "placebo": placebo_f(g, primary["n_west"], primary["n_east"]),
            "metros": [{"name": n, "coast": c, "growth": float(x), "jobs_2019": float(j)}
                       for n, c, x, j in zip(u["metro_name"], u["coast"], u["it_growth_pct"], u["emp_it_2019"])],
            "withheld": sorted(g.loc[g["coast"].notna() & ~g["usable"], "metro_name"].tolist())}


# ======================================================================================== B1 Slovenia (exploratory)
def slovenia_explore(eurostat: pd.DataFrame, country: str = "SI", years=B1_YEARS) -> dict:
    """Slovenia's ICT share next to the EU-27 aggregate and the other countries' range; ranks; absolute vs. relative change;
    absolute number of ICT specialists (thousand persons). Exploratory: no test."""
    w = _a_wide(eurostat, years, EU27)
    eu = _a_wide(eurostat, years, ("EU27_2020",)).iloc[0]
    others = w.drop(country)
    series = [{"year": int(y), "si": float(w.at[country, y]), "eu27": float(eu[y]), "min": float(others[y].min()),
               "q25": float(others[y].quantile(0.25)), "median": float(others[y].median()), "q75": float(others[y].quantile(0.75)),
               "max": float(others[y].max())} for y in years]
    rank = lambda y: int(1 + (w[y] > w.at[country, y]).sum())
    ab = w[2024] - w[2021]
    rel = 100 * (w[2024] / w[2021] - 1)
    out = {"series": series, "break_year": A2_BREAK_YEAR, "rank": {str(y): rank(y) for y in years}, "n": int(len(w)),
           "level_2021": {c: float(v) for c, v in w[2021].items()},
           "change_2021_2024": {"si_points": float(ab[country]), "others_mean_points": float(ab.drop(country).mean()),
                                "si_pct": float(rel[country]), "others_mean_pct": float(rel.drop(country).mean()),
                                "rank_points": int(1 + (ab > ab[country]).sum()), "rank_pct": int(1 + (rel > rel[country]).sum())},
           "earlier_rise": {"si_2015_2020_points": float(w.at[country, 2020] - w.at[country, 2015]),
                            "others_mean_2015_2020_points": float((others[2020] - others[2015]).mean()),
                            "rank_2015_2020": int(1 + ((w[2020] - w[2015]) > (w.at[country, 2020] - w.at[country, 2015])).sum())}}
    try:
        th = _a_wide(eurostat, years, (country, "EU27_2020"), unit="THS_PER")
        out["thousands"] = [{"year": int(y), "si": float(th.at[country, y]), "eu27": float(th.at["EU27_2020", y])} for y in years]
    except ValueError as err:
        out["thousands"] = {"error": str(err)}
    return out


# ======================================================================================== figures for notebook 11
def _p(p: float) -> str:
    return "< 0,001" if p < 0.001 else f"= {sl_num(p, 3)}"


def _pp(x: float, digits: int = 2) -> str:
    return ("+" if x > 0 else "") + sl_num(x, digits)


def fig_a2(a2: dict) -> go.Figure:
    v = pd.DataFrame(a2["values"]).T
    p = a2["primary"]
    xs = np.linspace(v["start"].min(), v["start"].max(), 2)
    fig = go.Figure()
    o = v.drop("SI")
    fig.add_trace(go.Scatter(x=o["start"], y=o["change"], mode="markers+text", text=list(o.index), textposition="top center",
                             marker=dict(color=PALETTE["grey"], size=9), name="druge države EU",
                             customdata=[EU_SL.get(c, c) for c in o.index],
                             hovertemplate="%{customdata}: izhodišče %{x:.2f} %, sprememba %{y:.2f} točke<extra></extra>"))
    fig.add_trace(go.Scatter(x=[v.at["SI", "start"]], y=[v.at["SI", "change"]], mode="markers+text", text=["Slovenija"],
                             textposition="bottom center", marker=dict(color=PALETTE["blue"], size=13), name="Slovenija",
                             hovertemplate="Slovenija: izhodišče %{x:.2f} %, sprememba %{y:.2f} točke<extra></extra>"))
    fig.add_trace(go.Scatter(x=xs, y=p["intercept"] + p["b"] * xs, mode="lines", line=dict(color=PALETTE["orange"], width=2),
                             name="premica", hoverinfo="skip"))
    direction = ("Rast skoraj ni povezana z izhodiščem" if abs(p["r"]) < 0.2 else
                 "Države z višjim izhodiščem so zrasle manj" if p["b"] < 0 else "Države z višjim izhodiščem so zrasle več")
    fig.update_layout(**base_layout(f"{direction} (naklon {sl_num(p['b'], 2)})", height=560))
    fig.update_layout(xaxis=dict(title="delež strokovnjakov IKT med zaposlenimi, povprečje 2019-2020 (%)"),
                      yaxis=dict(title="sprememba deleža 2021 → 2024 (odstotne točke)"), showlegend=False)
    return fig


def explain_a2(a2: dict) -> dict:
    p, s, pl, sec = a2["primary"], a2["slovenia"], a2["placebo"], a2["secondary"]
    return {
        "kaj": "Vsaka pika je ena država EU. Vodoravno je, kolikšen delež zaposlenih so bili strokovnjaki za informacijske in komunikacijske "
               "tehnologije (IKT) v letih 2019-2020, navpično, za koliko odstotnih točk se je ta delež spremenil od 2021 do 2024. "
               "Oranžna premica kaže skupni trend, Slovenija je modra.",
        "zakaj": "Pri prvi hipotezi je bila Slovenija po rasti zadnja med 27 državami. Vprašali smo se, ali je to zato, ker je začela visoko: "
                 "države z že velikim deležem IT bi lahko rasle počasneje, druge pa jih dohitevale. Izhodišče smo vzeli iz let pred 2021, "
                 "da ista (nenatančna) številka ne nastopa na obeh straneh primerjave.",
        "pomen": (f"Naklon premice je {_pp(p['b'], 2)} odstotne točke spremembe na vsako točko izhodišča (95 % interval od {sl_num(p['ci_lo'], 2)} "
                  f"do {sl_num(p['ci_hi'], 2)}), p {_p(p['p'])} (permutacijski test). Slovenija je začela na {s['start_rank']}. mestu od {s['n']}; "
                  f"premica, izračunana brez nje, ji napove spremembo {_pp(s['predicted_change'])} točke, izmerjena je bila {_pp(s['change'])} "
                  f"(odstopanje {_pp(s['residual'])}, opisni test p {_p(s['pi_p'])}): izhodišče slovenskega padca ne pojasni. Ali je hipoteza potrjena, odloči šele popravek za vse štiri hipoteze v zvezku 11."),
        "omejitve": (f"Le 27 držav: test zanesljivo opazi šele močno povezavo (korelacija okoli {sl_num(p['mde_abs_r'], 2)}). Leta 2021 se je metoda "
                     f"ankete spremenila. Simulacija brez dohitevanja da p pod 0,05 v {sl_num(100 * pl['share_p_below_005'], 1)} % primerov z našim "
                     f"načrtom in v {sl_num(100 * pl['share_p_below_005_naive'], 1)} % z izhodiščem 2021; zato izhodišča 2021 nismo uporabili "
                     f"(z njim bi bil naklon {sl_num(sec['naive_start_2021']['b'], 2)}). Povezava ne pove, zakaj."),
    }


def fig_f(f: dict) -> go.Figure:
    m = pd.DataFrame(f["metros"])
    p = f["primary"]
    fig = go.Figure()
    for coast, name, color in (("west", "Zahodna obala", PALETTE["orange"]), ("east", "Vzhodna obala", PALETTE["blue"])):
        s = m[m["coast"] == coast]
        fig.add_trace(go.Box(y=s["growth"].clip(-100, 300), name=f"{name} ({len(s)})", boxpoints="all", jitter=0.4, pointpos=0,
                             marker=dict(color=color, size=6, opacity=0.7), line=dict(color=color), fillcolor="rgba(0,0,0,0)",
                             text=[n.replace(" Metro Area", "").replace(" Micro Area", "") for n in s["name"]],
                             hovertemplate="%{text}: %{y:.0f} %<extra></extra>"))
    lower = "na zahodni obali manj" if p["diff_median"] < 0 else "na zahodni obali več"
    fig.update_layout(**base_layout(f"IT delovna mesta so 2019-2024 v tipičnem mestu rasla {lower} kot na vzhodni "
                                    f"({sl_num(p['median_west'], 0)} % proti {sl_num(p['median_east'], 0)} %)", height=560))
    fig.update_layout(yaxis=dict(title="rast IT zaposlenosti 2019 → 2024 (%, odrezano pri -100 in 300)"), showlegend=False)
    return fig


def explain_f(f: dict) -> dict:
    p, sec, pl = f["primary"], f["secondary"], f["placebo"]
    w = sec["weighted"]
    return {
        "kaj": "Vsaka pika je eno mestno območje v ZDA, škatla kaže srednjo polovico območij in mediano. Navpično je, za koliko odstotkov se je "
               "od 2019 do 2024 spremenilo število delovnih mest v IT storitvah (programiranje, svetovanje). Zahodna obala so zvezne države "
               "Washington, Oregon in Kalifornija, vzhodna pa atlantske države od Maina do Floride s Pensilvanijo in Washingtonom D.C.",
        "zakaj": "Na zahodni obali so velika tehnološka središča (San Francisco, Seattle, Los Angeles), na vzhodni pa poleg Bostona in New Yorka "
                 "tudi hitro rastoča mesta na jugovzhodu. Preverili smo, ali se je rast med obalama razlikovala.",
        "pomen": (f"Mediana je {sl_num(p['median_west'], 1)} % na zahodu ({p['n_west']} območij) in {sl_num(p['median_east'], 1)} % na vzhodu "
                  f"({p['n_east']}), razlika {_pp(p['diff_median'], 1)} odstotne točke (95 % interval od {sl_num(p['ci_lo'], 1)} do "
                  f"{sl_num(p['ci_hi'], 1)}), p {_p(p['p'])} (Mann-Whitneyjev test). Če štejemo vsa delovna mesta skupaj (velika mesta štejejo več), "
                  f"se je njihovo število na zahodu spremenilo za {_pp(w['west'], 1)} %, na vzhodu za {_pp(w['east'], 1)} %. Ali je hipoteza potrjena, odloči šele popravek "
                  f"za vse štiri hipoteze v zvezku 11."),
        "omejitve": (f"Za {p['n_withheld_east']} območij na vzhodu in {p['n_withheld_west']} na zahodu urad podatka o zaposlenih ne objavi (med njimi "
                     f"Atlanta), zato manjkajo. Cela zvezna država šteje k obali, tudi mesta v notranjosti. IT storitve niso vsa tehnološka "
                     f"podjetja. Naključne skupine enake velikosti dajo p pod 0,05 v {sl_num(100 * pl['share_p_below_005'], 1)} % primerov. "
                     f"Test ne pove, zakaj se obali razlikujeta."),
    }


def fig_slovenia_share(b1: dict) -> go.Figure:
    s = pd.DataFrame(b1["series"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["year"], y=s["max"], mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=s["year"], y=s["min"], mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(154,154,154,0.25)", name="razpon ostalih 26 držav",
                             customdata=s[["min", "max"]].to_numpy(), hovertemplate="%{x}: od %{customdata[0]:.1f} do %{customdata[1]:.1f} %<extra></extra>"))
    fig.add_trace(go.Scatter(x=s["year"], y=s["eu27"], mode="lines", line=dict(color=PALETTE["orange"], width=2.5), name="EU-27",
                             hovertemplate="EU-27 %{x}: %{y:.1f} %<extra></extra>"))
    fig.add_trace(go.Scatter(x=s["year"], y=s["si"], mode="lines+markers", line=dict(color=PALETTE["blue"], width=3), name="Slovenija",
                             hovertemplate="Slovenija %{x}: %{y:.1f} %<extra></extra>"))
    fig.add_shape(type="line", x0=b1["break_year"] - 0.5, x1=b1["break_year"] - 0.5, y0=0, y1=1, yref="paper",
                  line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    fig.add_annotation(x=b1["break_year"] - 0.5, y=1, yref="paper", text="nova metoda ankete", showarrow=False, xanchor="right",
                       yanchor="top", textangle=-90)
    last, y21 = s.iloc[-1], s.loc[s["year"] == b1["break_year"]].iloc[0]
    if y21["si"] > y21["eu27"] and last["si"] < last["eu27"]:
        head = f"Slovenija je bila leta {b1['break_year']} nad povprečjem EU, do leta {int(last['year'])} pa je padla pod njega"
    else:
        where = "nad" if last["si"] > last["eu27"] else "pod"
        head = f"Slovenija je {where} povprečjem EU" + (", po letu 2021 pa ne raste več" if last["si"] <= y21["si"] else "")
    fig.update_layout(**base_layout(head, height=520))
    fig.update_layout(yaxis=dict(title="strokovnjaki IKT med zaposlenimi (%)"), xaxis=dict(title="", dtick=1))
    return fig


def _after_break(s: pd.DataFrame, year: int) -> str:
    """One sentence on Slovenia's highest and lowest year from the break year on (the timing question of the feedback)."""
    a = s.loc[s.index >= year, "si"]
    hi, lo = int(a.idxmax()), int(a.idxmin())
    if hi == year:
        return (f"Leto {year}, kjer se primerjava začne, je bilo za Slovenijo najvišje ({sl_num(a[hi], 1)} %); najnižje je bilo "
                f"leto {lo} ({sl_num(a[lo], 1)} %).")
    return f"Po letu {year} je bil delež najvišji leta {hi} ({sl_num(a[hi], 1)} %) in najnižji leta {lo} ({sl_num(a[lo], 1)} %)."


def explain_slovenia_share(b1: dict) -> dict:
    s = pd.DataFrame(b1["series"]).set_index("year")
    e = b1["earlier_rise"]
    return {
        "kaj": "Modra črta je delež strokovnjakov IKT med vsemi zaposlenimi v Sloveniji, oranžna povprečje EU-27, siva površina razpon ostalih "
               "26 držav. Črtkana črta loči leta pred in po spremembi metode ankete leta 2021.",
        "zakaj": "Recenzent je vprašal, ali je slovenski rezultat pri prvi hipotezi posledica visokega izhodišča ali zgodnejše rasti. To je "
                 "raziskovalni pogled brez testa.",
        "pomen": (f"Slovenija je imela {sl_num(s.at[2015, 'si'], 1)} % leta 2015, {sl_num(s.at[2021, 'si'], 1)} % leta 2021 in "
                  f"{sl_num(s.at[2024, 'si'], 1)} % leta 2024 (EU-27: {sl_num(s.at[2015, 'eu27'], 1)}, {sl_num(s.at[2021, 'eu27'], 1)}, "
                  f"{sl_num(s.at[2024, 'eu27'], 1)}). Med 2015 in 2020 je zrasla za {_pp(e['si_2015_2020_points'], 2)} točke, ostale države v "
                  f"povprečju za {_pp(e['others_mean_2015_2020_points'], 2)} (po rasti {e['rank_2015_2020']}. mesto od {b1['n']}), torej ni rasla prej kot "
                  f"druge. {_after_break(s, b1['break_year'])}"),
        "omejitve": "Delež je že normaliziran: deli se s številom vseh zaposlenih, zato velikost države ne vpliva neposredno. Ne odpravi pa tega, "
                    "da je vzorec ankete v majhni državi manjši in ocena bolj negotova. Zadnja leta so delno ocene (oznaka »e«).",
    }


def fig_slovenia_rank(b1: dict) -> go.Figure:
    lv = pd.Series(b1["level_2021"]).sort_values()
    fig = go.Figure(go.Bar(x=lv.to_numpy(), y=[EU_SL.get(c, c) for c in lv.index], orientation="h",
                           marker_color=[PALETTE["blue"] if c == "SI" else PALETTE["grey"] for c in lv.index],
                           hovertemplate="%{y}: %{x:.1f} %<extra></extra>"))
    r = b1["rank"]["2021"]
    fig.update_layout(**base_layout(f"Leta 2021 je bila Slovenija po deležu strokovnjakov IKT na {r}. mestu od {b1['n']}", height=640))
    fig.update_layout(xaxis=dict(title="strokovnjaki IKT med zaposlenimi, 2021 (%)"), yaxis=dict(title=""))
    return fig


def explain_slovenia_rank(b1: dict) -> dict:
    r = b1["rank"]
    return {
        "kaj": "Vsak stolpec je ena država EU: delež strokovnjakov IKT med vsemi zaposlenimi leta 2021. Slovenija je modra.",
        "zakaj": "Če je Slovenija začela visoko, bi bila počasnejša rast lahko pričakovana. Pogledali smo, kje je bila na začetku obdobja.",
        "pomen": f"Slovenija je bila leta 2021 na {r['2021']}. mestu od {b1['n']}, leta 2019 na {r['2019']}. in leta 2024 na {r['2024']}. mestu.",
        "omejitve": "Mesto na lestvici ne pove, koliko je razlika do sosednjih držav; razlike med srednjimi državami so majhne in v okviru "
                    "negotovosti ankete. Raziskovalni pogled, brez testa.",
    }


def fig_slovenia_change(b1: dict) -> go.Figure:
    c = b1["change_2021_2024"]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("v odstotnih točkah", "v odstotkih izhodišča"))
    for col, (si, oth) in enumerate(((c["si_points"], c["others_mean_points"]), (c["si_pct"], c["others_mean_pct"])), start=1):
        fig.add_trace(go.Bar(x=["Slovenija", "povprečje ostalih 26"], y=[si, oth], marker_color=[PALETTE["blue"], PALETTE["grey"]],
                             hovertemplate="%{x}: %{y:.2f}<extra></extra>", showlegend=False), row=1, col=col)
    fig.update_layout(**base_layout(f"Slovenija je zadnja po obeh merilih ({c['rank_points']}. in {c['rank_pct']}. mesto od {b1['n']})"
                                    if c["rank_points"] == c["rank_pct"] == b1["n"] else
                                    f"Slovenija: {c['rank_points']}. mesto v točkah, {c['rank_pct']}. v odstotkih", height=460))
    return fig


def explain_slovenia_change(b1: dict) -> dict:
    c = b1["change_2021_2024"]
    return {
        "kaj": "Sprememba deleža strokovnjakov IKT od 2021 do 2024, na levi v odstotnih točkah (razlika deležev), na desni v odstotkih "
               "izhodiščnega deleža (relativna sprememba).",
        "zakaj": "Država z velikim izhodiščem lahko v točkah zraste več, v odstotkih pa manj. Preverili smo, ali je slovenski rezultat odvisen od "
                 "tega, kako spremembo merimo.",
        "pomen": (f"Slovenija: {_pp(c['si_points'])} točke oziroma {_pp(c['si_pct'], 1)} %; ostale države v povprečju {_pp(c['others_mean_points'])} "
                  f"točke oziroma {_pp(c['others_mean_pct'], 1)} %. Po točkah je na {c['rank_points']}. mestu, po odstotkih na {c['rank_pct']}."),
        "omejitve": "Leto 2024 je za Slovenijo ocena (oznaka »e«). Raziskovalni pogled, brez testa.",
    }


def fig_slovenia_count(b1: dict) -> go.Figure:
    t = pd.DataFrame(b1["thousands"])
    fig = go.Figure(go.Scatter(x=t["year"], y=t["si"], mode="lines+markers", line=dict(color=PALETTE["blue"], width=3), name="Slovenija",
                               hovertemplate="%{x}: %{y:.1f} tisoč<extra></extra>"))
    fig.add_shape(type="line", x0=b1["break_year"] - 0.5, x1=b1["break_year"] - 0.5, y0=0, y1=1, yref="paper",
                  line=dict(color=PALETTE["ink"], width=1, dash="dash"))
    first, peak = t.iloc[0], t.loc[t["si"].idxmax()]
    fig.update_layout(**base_layout(f"V Sloveniji je bilo največ strokovnjakov IKT leta {int(peak['year'])} "
                                    f"({sl_num(peak['si'], 1)} tisoč)", height=480))
    fig.update_layout(yaxis=dict(title="strokovnjaki IKT v Sloveniji (tisoč)", rangemode="tozero"), xaxis=dict(title="", dtick=1),
                      showlegend=False)
    return fig


def explain_slovenia_count(b1: dict) -> dict:
    t = pd.DataFrame(b1["thousands"]).set_index("year")
    return {
        "kaj": "Število strokovnjakov IKT v Sloveniji v tisočih (Eurostat, ista anketa kot delež).",
        "zakaj": "Delež lahko pade tudi, ko strokovnjakov ni manj, če hitreje raste skupno število zaposlenih. Zato pogledamo še število ljudi.",
        "pomen": (f"Leta 2015 {sl_num(t.at[2015, 'si'], 1)} tisoč, 2021 {sl_num(t.at[2021, 'si'], 1)} tisoč, 2024 {sl_num(t.at[2024, 'si'], 1)} tisoč "
                  f"in 2025 {sl_num(t.at[2025, 'si'], 1)} tisoč."),
        "omejitve": "Število je zaokroženo in ocenjeno iz ankete; v majhni državi je negotovost razmeroma velika. Raziskovalni pogled, brez testa.",
    }


def build_figures_b(results: dict) -> dict[str, tuple[go.Figure, dict]]:
    """Notebook 11: one figure and its four explanation parts per name (the `pomen` parts state no verdict)."""
    out = {}
    if results.get("A2"):
        out.update({"11a2_dohitevanje": (fig_a2(results["A2"]), explain_a2(results["A2"]))})
    if results.get("F"):
        out.update({"11f_obali": (fig_f(results["F"]), explain_f(results["F"]))})
    b1 = results.get("B1")
    if b1:
        out.update({"11x_slovenija_delez": (fig_slovenia_share(b1), explain_slovenia_share(b1)),
                    "11x_slovenija_rang": (fig_slovenia_rank(b1), explain_slovenia_rank(b1)),
                    "11x_slovenija_sprememba": (fig_slovenia_change(b1), explain_slovenia_change(b1))})
        if isinstance(b1.get("thousands"), list):
            out.update({"11x_slovenija_stevilo": (fig_slovenia_count(b1), explain_slovenia_count(b1))})
    return out


# ======================================================================================== run
def load_results() -> dict:
    from analysis.viz_theme import ROOT
    return json.loads((ROOT / "reports" / "hypotheses2_b_results.json").read_text(encoding="utf-8"))


def run() -> dict:
    from collectors.common import PROCESSED, RAW
    e_path, g_path = RAW / "eurostat_isoc_sks_itspt.csv", PROCESSED / "metro_map_data.csv"
    out = {"inputs_sha256": file_hashes([e_path, g_path])}
    eurostat = pd.read_csv(e_path, dtype={"geo": str, "unit": str, "flag": str, "time": str}, keep_default_na=False, na_values=[""])
    out["A2"] = run_a2(eurostat)
    out["F"] = run_f(pd.read_csv(g_path, dtype={"cbsa_code": str}))
    out["B1"] = slovenia_explore(eurostat)
    return _clean(out)


def main() -> None:
    from analysis.viz_theme import ROOT
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    res = run()
    path = ROOT / "reports" / "hypotheses2_b_results.json"
    path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    hide = ("values", "metros", "withheld", "series", "by_country", "level_2021", "thousands", "flagged_cells")
    show = {k: {kk: ({x: y for x, y in vv.items() if x not in hide} if isinstance(vv, dict) else vv)
                for kk, vv in v.items() if kk not in hide} for k, v in res.items() if k != "inputs_sha256"}
    print(json.dumps(show, indent=2))
    print(f"written {path}")


if __name__ == "__main__":
    main()
