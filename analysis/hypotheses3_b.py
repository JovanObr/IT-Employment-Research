"""Round 3, Stream B: the pre-registered test G (docs/hypotheses/round3/G.md).

G   Own central bank vs. common shock: across the EU-27, country-quarter panel 2019Q1-2024Q4, OLS of the year-on-year change of the
    ICT (NACE J) job vacancy rate on the year-on-year change of the country's own 3-month interest rate one quarter earlier, with
    country and quarter fixed effects. The quarter effects absorb everything common to all countries in a quarter, so b is identified
    only from countries whose own rate moved differently. Predicted b < 0. The primary p is fixed in the registration (chosen there
    from the synthetic calibration in `calibrate`).

Choices the registration leaves open, fixed here before the real run:
- Quarterly rate = mean of the monthly 3-month rates of that quarter; a quarter needs all 3 months, otherwise it is missing.
- Countries with their own rate: CZ, DK, HU, PL, RO, SE (the six EU countries outside the euro area in 2019-2024 with a published
  3-month rate). Every other EU country, including BG and HR (own series end 2018-06 and 2019-12; both pegged to the euro), takes
  the euro-area rate (`EA`) for the whole window.
- Vacancy rate: indicator JVR, size class TOTAL, unadjusted (NSA) for every country (all 27 publish NSA for section J). Year-on-year
  differences remove the seasonal pattern.
- A row needs the outcome (both quarters of the difference) and the exposure; rows without them are dropped and counted.

    python -m analysis.hypotheses3_b        # runs G on data/raw/eurostat_jvs_q_nace2.csv + eurostat_irt_st_m.csv,
                                            # writes reports/hypotheses3_b_results.json
"""
from __future__ import annotations

import json
import logging
import subprocess

import numpy as np
import pandas as pd
from scipy import stats

from analysis.hypotheses import file_hashes

log = logging.getLogger("covid_it_data")

EU27 = ("AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
        "NL", "PL", "PT", "RO", "SE", "SI", "SK")
OWN_RATE = ("CZ", "DK", "HU", "PL", "RO", "SE")
EA = "EA"
WINDOW = ("2019Q1", "2024Q4")
CALIB = ("2015Q1", "2018Q4")           # noise model for the real-scale power, computed before b
LAG = 1
LOW_QUALITY_FLAGS = ("u", "e")         # secondary 2: countries with any such flag in an outcome quarter are left out
N_BOOT = 9_999
N_PERM = 9_999
N_PLACEBO = 1_000

# Seen before registration and quoted, not recomputed (docs/hypotheses/round3/README.md, "What has already been seen").
QUOTED = {
    "first_hikes": {"BoE": "2021-12-16", "Fed": "2022-03-16", "ECB": "2022-07-21"},
    "indeed_software_peaks": {"US": "2022-02", "UK": "2022-04", "DE": "2022-05", "FR": "2022-07"},
    "tracker_layoff_announcements": {"Europe": {"2022Q1": 4, "2022Q2": 31}, "US": {"2022Q1": 21, "2022Q2": 174}},
}


# ---------------------------------------------------------------------------------------- data
def quarterly_rates(irt: pd.DataFrame) -> pd.DataFrame:
    """Quarterly mean of the monthly 3-month rate; one column per geo; a quarter needs all 3 months."""
    d = irt[irt["int_rt"] == "IRT_M3"] if "int_rt" in irt.columns else irt
    d = d.assign(q=pd.PeriodIndex(pd.to_datetime(d["time"].astype(str)), freq="Q"), value=pd.to_numeric(d["value"], errors="coerce"))
    d = d.dropna(subset=["value"])
    g = d.groupby(["geo", "q"])["value"].agg(["mean", "count"])
    return g["mean"].where(g["count"] == 3).unstack("geo").sort_index()


def rate_paths(qr: pd.DataFrame, countries=EU27, own=OWN_RATE) -> pd.DataFrame:
    """Rate level per country (columns) and quarter: own rate for `own`, euro-area rate for the rest."""
    return pd.DataFrame({c: qr[c] if c in own else qr[EA] for c in countries})


def yoy_exposure(paths: pd.DataFrame, lag: int = LAG) -> pd.DataFrame:
    """x(c,t) = r(c,t-lag) - r(c,t-lag-4), percentage points (rows quarters, columns countries)."""
    return paths.shift(lag) - paths.shift(lag + 4)


def vacancy(jvs: pd.DataFrame, nace: str = "J", s_adj: str = "NSA", countries=EU27) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vacancy rate (quarters x countries) and its flags, indicator JVR, size class TOTAL."""
    d = jvs[(jvs["nace_r2"] == nace) & (jvs["s_adj"] == s_adj) & jvs["geo"].isin(countries)]
    if "indic_em" in d.columns:
        d = d[d["indic_em"] == "JVR"]
    if "sizeclas" in d.columns:
        d = d[d["sizeclas"] == "TOTAL"]
    d = d.assign(q=pd.PeriodIndex(d["time"].astype(str).str.replace("-", "", regex=False), freq="Q"),
                 value=pd.to_numeric(d["value"], errors="coerce"), flag=d["flag"].fillna("").astype(str))
    v = d.pivot_table(index="q", columns="geo", values="value", aggfunc="first")
    f = d.pivot_table(index="q", columns="geo", values="flag", aggfunc="first")
    return v.sort_index(), f.reindex(v.index)


def panel_from_wide(y: pd.DataFrame, x: pd.DataFrame, window=WINDOW) -> pd.DataFrame:
    """Long panel (country, quarter, y, x) over the window, rows with both values only."""
    q = pd.period_range(window[0], window[1], freq="Q")
    yy = y.reindex(q).stack(future_stack=True).rename("y")
    xx = x.reindex(q).stack(future_stack=True).rename("x")
    p = pd.concat([yy, xx], axis=1).reset_index()
    p.columns = ["quarter", "country", "y", "x"]
    return p.dropna(subset=["y", "x"]).sort_values(["country", "quarter"]).reset_index(drop=True)


def build_panel(jvs: pd.DataFrame, irt: pd.DataFrame, nace: str = "J", lag: int = LAG, window=WINDOW,
                countries=EU27, s_adj: str = "NSA") -> pd.DataFrame:
    v, _ = vacancy(jvs, nace, s_adj, countries)
    y = v - v.shift(4)
    have = [c for c in countries if c in y.columns]
    x = yoy_exposure(rate_paths(quarterly_rates(irt), have), lag)
    return panel_from_wide(y[have], x, window)


def low_quality_countries(jvs: pd.DataFrame, nace: str = "J", window=WINDOW, flags=LOW_QUALITY_FLAGS) -> list[str]:
    """Countries with a `u` or `e` flag in any quarter that enters an outcome (window start - 4 quarters to window end)."""
    _, f = vacancy(jvs, nace)
    q = pd.period_range(pd.Period(window[0], "Q") - 4, window[1], freq="Q")
    f = f.reindex(q)
    return sorted(c for c in f.columns if f[c].fillna("").map(lambda s: any(ch in s for ch in flags)).any())


# ---------------------------------------------------------------------------------------- two-way fixed effects
class TWFE:
    """y on x with country and quarter dummies, through the annihilator M of the dummies (Frisch-Waugh-Lovell)."""

    def __init__(self, panel: pd.DataFrame):
        self.panel = panel
        cc = pd.Categorical(panel["country"])
        qq = pd.Categorical(panel["quarter"].astype(str))
        D = np.column_stack([np.eye(len(cc.categories))[cc.codes], np.eye(len(qq.categories))[qq.codes][:, 1:]])
        self.D = D
        self.Dpinv = np.linalg.pinv(D)
        self.k = int(np.linalg.matrix_rank(D)) + 1
        self.cluster = cc.codes
        self.G = len(cc.categories)
        self.n = len(panel)
        self.C = np.eye(self.G)[self.cluster].T                            # G x n cluster indicator

    def M(self, z: np.ndarray) -> np.ndarray:
        return z - self.D @ (self.Dpinv @ z)

    def _c1(self) -> float:
        return self.G / (self.G - 1) * (self.n - 1) / (self.n - self.k)

    def fit_many(self, xt: np.ndarray, yt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """b and CR1 cluster-robust se for each column of yt (already demeaned), one demeaned regressor xt."""
        sxx = xt @ xt
        b = (xt @ yt) / sxx
        e = yt - np.outer(xt, b) if yt.ndim == 2 else yt - b * xt
        s = self.C @ (xt[:, None] * e if e.ndim == 2 else xt * e)
        se = np.sqrt(self._c1() * (s ** 2).sum(axis=0) / sxx ** 2)
        return b, se

    def fit(self, x: np.ndarray, y: np.ndarray) -> dict:
        xt, yt = self.M(np.asarray(x, float)), self.M(np.asarray(y, float))
        b, se = self.fit_many(xt, yt)
        t = float(b / se)
        return {"b": float(b), "se_cr1": float(se), "t": t, "p_cr1": float(2 * stats.t.sf(abs(t), self.G - 1)),
                "n": self.n, "countries": self.G, "quarters": int(self.panel["quarter"].nunique())}


def wild_cluster_p(m: TWFE, x: np.ndarray, y: np.ndarray, n_boot: int = N_BOOT, seed: int = 0, chunk: int = 2000) -> float:
    """Restricted wild cluster bootstrap-t (null b = 0 imposed, Rademacher weights by country); two-sided
    p = (#|t*| >= |t| + 1) / (n_boot + 1)."""
    rng = np.random.default_rng(seed)
    xt, yt = m.M(np.asarray(x, float)), m.M(np.asarray(y, float))
    b, se = m.fit_many(xt, yt)
    t_obs = abs(b / se)
    u = yt                                                              # residual of y on the fixed effects alone (null imposed)
    hits, done = 0, 0
    while done < n_boot:
        k = min(chunk, n_boot - done)
        w = rng.choice((-1.0, 1.0), size=(m.G, k))[m.cluster]          # n x k
        z = m.M(u[:, None] * w)
        bs, ses = m.fit_many(xt, z)
        hits += int((np.abs(bs / ses) >= t_obs).sum())
        done += k
    return (hits + 1) / (n_boot + 1)


def _x_matrix(panel: pd.DataFrame) -> pd.DataFrame:
    return panel.pivot(index="quarter", columns="country", values="x")


def reassigned_x(panel: pd.DataFrame, xw: pd.DataFrame, perm: np.ndarray) -> np.ndarray:
    """Exposure of each row after giving country c the full exposure path of country perm[c]; rows whose new
    exposure is missing get the original (does not happen when all paths cover the window)."""
    cols = list(xw.columns)
    mapping = {c: cols[j] for c, j in zip(cols, perm)}
    new = xw.copy()
    for c in cols:
        new[c] = xw[mapping[c]]
    v = new.stack(future_stack=True).rename("x2").reset_index()
    v.columns = ["quarter", "country", "x2"]
    out = panel[["quarter", "country", "x"]].merge(v, on=["quarter", "country"], how="left")
    return out["x2"].fillna(out["x"]).to_numpy(float)


def randomization_p(m: TWFE, panel: pd.DataFrame, n_perm: int = N_PERM, seed: int = 1, stat: str = "t") -> dict:
    """Randomization inference: the countries' exposure paths are reassigned at random among the countries (the quarter
    and country effects stay), b is re-estimated; p = (#|stat*| >= |stat| + 1) / (n_perm + 1); stat = "t" (CR1) or "b"."""
    rng = np.random.default_rng(seed)
    xw = _x_matrix(panel)
    full = xw.reindex(columns=sorted(panel["country"].unique()))
    y = panel["y"].to_numpy(float)
    yt = m.M(y)
    obs = m.fit(panel["x"].to_numpy(float), y)
    s_obs = abs(obs["t"] if stat == "t" else obs["b"])
    hits = 0
    for _ in range(n_perm):
        xp = reassigned_x(panel, full, rng.permutation(full.shape[1]))
        b, se = m.fit_many(m.M(xp), yt)
        hits += abs(b / se if stat == "t" else b) >= s_obs
    return {"p": float((hits + 1) / (n_perm + 1)), "n_perm": n_perm, "stat": stat}


def fast_randomization_p(m: TWFE, X_perm: np.ndarray, y: np.ndarray, x: np.ndarray, stat: str = "t") -> float:
    """Same as `randomization_p` with the reassigned exposures given as an n x R matrix (used in simulations)."""
    yt = m.M(np.asarray(y, float))
    b0, se0 = m.fit_many(m.M(np.asarray(x, float)), yt)
    XT = m.M(X_perm)
    sxx = (XT ** 2).sum(axis=0)
    b = (XT.T @ yt) / sxx
    e = yt[:, None] - XT * b
    s = m.C @ (XT * e)
    se = np.sqrt(m._c1() * (s ** 2).sum(axis=0) / sxx ** 2)
    s_obs = abs(b0 / se0) if stat == "t" else abs(b0)
    s_p = np.abs(b / se) if stat == "t" else np.abs(b)
    return float(((s_p >= s_obs).sum() + 1) / (len(b) + 1))


# ---------------------------------------------------------------------------------------- tests on the panel
def test_g(panel: pd.DataFrame, n_boot: int = N_BOOT, n_perm: int = N_PERM, seed: int = 0) -> dict:
    m = TWFE(panel)
    x, y = panel["x"].to_numpy(float), panel["y"].to_numpy(float)
    r = m.fit(x, y)
    r["p_wild"] = wild_cluster_p(m, x, y, n_boot, seed)
    r["p_ri"] = randomization_p(m, panel, n_perm, seed + 1)["p"]
    r["ci95_cr1"] = [r["b"] - stats.t.ppf(0.975, m.G - 1) * r["se_cr1"], r["b"] + stats.t.ppf(0.975, m.G - 1) * r["se_cr1"]]
    r["countries_own_rate"] = sorted(set(panel["country"]) & set(OWN_RATE))
    return r


# ---------------------------------------------------------------------------------------- synthetic panels
def synthetic_rates(seed: int = 0, start: str = "2017Q1", end: str = "2024Q4") -> pd.DataFrame:
    """Quarterly 3-month-rate levels shaped like 2017-2024 (no real data): the euro area near -0.4 until mid-2022, then up to
    about 3.9; six countries with their own paths (two follow the euro, four hike early and far)."""
    rng = np.random.default_rng(seed)
    q = pd.period_range(start, end, freq="Q")
    t = np.arange(len(q), dtype=float)

    def ramp(t0: str, t1: str, lo: float, hi: float, later: float | None = None) -> np.ndarray:
        a, b = q.get_loc(pd.Period(t0, "Q")), q.get_loc(pd.Period(t1, "Q"))
        r = np.where(t < a, lo, np.where(t > b, hi, lo + (hi - lo) * (t - a) / max(b - a, 1)))
        if later is not None:
            c = q.get_loc(pd.Period("2024Q1", "Q"))
            r = np.where(t >= c, hi + (later - hi) * (t - c + 1) / (len(q) - c), r)
        return r

    ea = ramp("2022Q2", "2023Q3", -0.4, 3.9, 3.3)
    paths = {"EA": ea, "DK": ea + 0.2, "SE": ramp("2022Q2", "2023Q3", 0.0, 4.1, 3.5),
             "CZ": ramp("2021Q3", "2022Q3", 0.4, 7.2, 5.5), "HU": ramp("2021Q2", "2022Q4", 0.7, 15.0, 7.0),
             "PL": ramp("2021Q4", "2022Q4", 0.2, 7.0, 5.8), "RO": ramp("2021Q4", "2022Q4", 2.0, 7.5, 6.0)}
    return pd.DataFrame({k: v + rng.normal(0, 0.05, len(q)) for k, v in paths.items()}, index=q)


def simulate_panel(x: pd.DataFrame, b: float = 0.0, phi: float = 0.5, sd: float = 1.0, hetero: float = 0.0,
                   own_noise: float = 1.0, common: float = 0.0, rng=None, window=WINDOW) -> pd.DataFrame:
    """y(c,t) = mu_c + lambda_t + b x(c,t) + eps(c,t), eps the year-on-year difference of an AR(1) level noise (phi, sd_c).
    sd_c = sd * exp(N(0, hetero)) * (own_noise for countries with their own rate); lambda_t = -common * (mean exposure in t) + N(0,1):
    a common shock that moves with the rates (must be absorbed by the quarter effects)."""
    rng = rng or np.random.default_rng()
    q = pd.period_range(window[0], window[1], freq="Q")
    xw = x.reindex(q)
    G, T = xw.shape[1], len(q)
    sd = np.asarray(sd.reindex(xw.columns).to_numpy(float) if isinstance(sd, pd.Series) else sd, float)
    sdc = sd * np.exp(rng.normal(0, hetero, G)) * np.where(np.isin(xw.columns, OWN_RATE), own_noise, 1.0)
    lev = np.empty((G, T + 4))
    lev[:, 0] = rng.normal(0, 1, G) * sdc / np.sqrt(max(1 - phi ** 2, 1e-6))
    for k in range(1, T + 4):
        lev[:, k] = phi * lev[:, k - 1] + rng.normal(0, 1, G) * sdc
    eps = (lev[:, 4:] - lev[:, :-4]).T                                   # T x G
    lam = -common * xw.mean(axis=1).to_numpy() + rng.normal(0, 1, T)
    mu = rng.normal(0, 0.5, G)
    y = mu[None, :] + lam[:, None] + b * xw.to_numpy() + eps
    return panel_from_wide(pd.DataFrame(y, index=q, columns=xw.columns), xw, window)


def synthetic_exposure(seed: int = 0, lag: int = LAG) -> pd.DataFrame:
    return yoy_exposure(rate_paths(synthetic_rates(seed)), lag)


def perm_matrix(panel: pd.DataFrame, n_perm: int, rng) -> np.ndarray:
    xw = _x_matrix(panel)
    full = xw.reindex(columns=sorted(panel["country"].unique()))
    return np.column_stack([reassigned_x(panel, full, rng.permutation(full.shape[1])) for _ in range(n_perm)])


def calibrate(x: pd.DataFrame, n_sim: int = 400, b: float = 0.0, n_boot: int = 399, n_perm: int = 399, seed: int = 0,
              **dgp) -> dict:
    """Share of simulated panels with p < 0.05 for the CR1 t-test, the wild cluster bootstrap and randomization inference."""
    rng = np.random.default_rng(seed)
    p0 = simulate_panel(x, rng=np.random.default_rng(seed))
    m = TWFE(p0)
    X_perm = perm_matrix(p0, n_perm, rng)
    xv = p0["x"].to_numpy(float)
    rej = {"cr1": 0, "wild": 0, "ri_t": 0, "ri_b": 0}
    signs = 0
    for i in range(n_sim):
        p = simulate_panel(x, b=b, rng=rng, **dgp)
        y = p["y"].to_numpy(float)
        r = m.fit(xv, y)
        rej["cr1"] += r["p_cr1"] < 0.05
        rej["wild"] += wild_cluster_p(m, xv, y, n_boot, seed=int(rng.integers(1 << 31))) < 0.05
        rej["ri_t"] += fast_randomization_p(m, X_perm, y, xv, "t") < 0.05
        rej["ri_b"] += fast_randomization_p(m, X_perm, y, xv, "b") < 0.05
        signs += r["b"] < 0
    return {k: v / n_sim for k, v in rej.items()} | {"share_negative": signs / n_sim, "n_sim": n_sim}


def power_curve(x: pd.DataFrame, sd: float, primary: str, grid, n_sim: int = 200, seed: int = 5, **dgp) -> float:
    """Smallest |b| on the grid (tried as negative effects) found with p < 0.05 at least 80 % of the time by the primary."""
    for b in grid:
        c = calibrate(x, n_sim=n_sim, b=-abs(b), seed=seed, sd=sd, **dgp)
        if c[primary] >= 0.8:
            return float(abs(b))
    return float("nan")


# ---------------------------------------------------------------------------------------- run
def registration_commit() -> str | None:
    try:
        return subprocess.run(["git", "log", "--diff-filter=A", "--format=%h", "-1", "--", "docs/hypotheses/round3/G.md"],
                              capture_output=True, text=True, check=True).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


PHI_POWER = 0.7                        # persistence of the level noise assumed for the real-scale power (registration)
EARLY = ("CZ", "HU", "PL", "RO")       # own rate departs most from the euro area's in 2021-2023 (design check G1)


def noise_scale(jvs: pd.DataFrame, nace: str = "J", window=CALIB, countries=EU27) -> pd.Series:
    """Per country: sd of the two-way fixed-effect residual of the year-on-year outcome over the calibration window (no exposure);
    converted to the sd of the AR(1) level innovation that gives this year-on-year sd with phi = PHI_POWER."""
    v, _ = vacancy(jvs, nace, "NSA", countries)
    y = v - v.shift(4)
    p = panel_from_wide(y, pd.DataFrame(0.0, index=y.index, columns=y.columns), window)
    m = TWFE(p)
    r = pd.Series(m.M(p["y"].to_numpy(float)), index=p.index).groupby(p["country"]).std(ddof=1)
    return r * np.sqrt((1 - PHI_POWER ** 2) / (2 * (1 - PHI_POWER ** 4)))


def power_search(x: pd.DataFrame, sd, primary: str = "wild", n_sim: int = 200, seed: int = 5, start: float = 0.01,
                 steps: int = 6, n_boot: int = 399, **dgp) -> float:
    """Smallest |b| found with p < 0.05 at least 80 % of the time (b planted negative): doubling from `start`, then bisection."""
    pw = lambda b: calibrate(x, n_sim=n_sim, b=-b, seed=seed, sd=sd, phi=PHI_POWER, n_boot=n_boot, n_perm=99, **dgp)[primary]
    lo, hi = 0.0, start
    while pw(hi) < 0.8:
        lo, hi = hi, 2 * hi
        if hi > 100:
            return float("nan")
    for _ in range(steps):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if pw(mid) >= 0.8 else (mid, hi)
    return float(hi)


def group_series(jvs: pd.DataFrame, irt: pd.DataFrame, nace: str = "J", start: str = "2018Q1", end: str = WINDOW[1]) -> list[dict]:
    """For the figure: unweighted mean vacancy rate and 3-month rate of the early hikers (EARLY) and of the euro-area countries."""
    v, _ = vacancy(jvs, nace)
    qr = quarterly_rates(irt)
    r = rate_paths(qr)
    euro = [c for c in EU27 if c not in OWN_RATE]
    q = pd.period_range(start, end, freq="Q")
    out = []
    for t in q:
        out.append({"quarter": str(t), "vac_early": float(v.reindex(q).loc[t, list(EARLY)].mean()),
                    "vac_euro": float(v.reindex(q).loc[t, [c for c in euro if c in v.columns]].mean()),
                    "rate_early": float(r.reindex(q).loc[t, list(EARLY)].mean()), "rate_euro": float(qr[EA].reindex(q).loc[t])})
    return out


def placebo_g(panel: pd.DataFrame, n_rep: int = N_PLACEBO, n_boot: int = 999, seed: int = 7) -> dict:
    """Own-rate paths reassigned at random among the countries; the primary test on each; share with p < 0.05."""
    rng = np.random.default_rng(seed)
    m = TWFE(panel)
    X = perm_matrix(panel, n_rep, rng)
    y = panel["y"].to_numpy(float)
    ps = np.array([wild_cluster_p(m, X[:, j], y, n_boot, seed=int(rng.integers(1 << 31))) for j in range(n_rep)])
    return {"n_rep": n_rep, "n_boot": n_boot, "share_p_below_005": float((ps < 0.05).mean())}


def run_g(jvs: pd.DataFrame, irt: pd.DataFrame, n_boot: int = N_BOOT, n_perm: int = N_PERM, n_placebo: int = N_PLACEBO,
          power_sims: int = 200, power_boot: int = 399) -> dict:
    panel = build_panel(jvs, irt)
    full = len(pd.period_range(*WINDOW, freq="Q")) * len(EU27)
    xw = yoy_exposure(rate_paths(quarterly_rates(irt)))
    sd = noise_scale(jvs)
    mde = power_search(xw, sd, n_sim=power_sims, n_boot=power_boot)
    log.info("G design (before b): %d rows of %d; level-noise sd median %.3f; smallest |b| found 80 %% of the time %.4f",
             len(panel), full, float(sd.median()), mde)
    prim = test_g(panel, n_boot, n_perm)
    prim["p"] = prim["p_wild"]
    prim["predicted_sign"] = bool(prim["b"] < 0)
    prim["mde_b"] = mde
    prim["rows_dropped"] = full - len(panel)
    prim["noise_sd_level_median"] = float(sd.median())
    m = TWFE(panel)
    prim["residual_sd_outcome"] = float(np.std(m.M(panel["y"].to_numpy(float)) - prim["b"] * m.M(panel["x"].to_numpy(float)), ddof=1))

    def sub(p: pd.DataFrame, seed: int) -> dict:
        mm = TWFE(p)
        r = mm.fit(p["x"].to_numpy(float), p["y"].to_numpy(float))
        r["p_wild"] = wild_cluster_p(mm, p["x"].to_numpy(float), p["y"].to_numpy(float), n_boot, seed)
        return r

    lowq = low_quality_countries(jvs)
    bs = build_panel(jvs, irt, nace="B-S")
    sec = {"lag0": sub(build_panel(jvs, irt, lag=0), 11), "lag2": sub(build_panel(jvs, irt, lag=2), 12),
           "without_low_quality": {"dropped": lowq, **sub(panel[~panel["country"].isin(lowq)], 13)},
           "all_industries_BS": {"countries": int(bs["country"].nunique()), **sub(bs, 14)},
           "leave_one_out": {c: {k: v for k, v in sub(panel[panel["country"] != c], 20 + i).items() if k in ("b", "se_cr1", "p_wild", "n")}
                             for i, c in enumerate(OWN_RATE)},
           "quoted_not_recomputed": QUOTED}
    sec["difference_J_minus_BS"] = prim["b"] - sec["all_industries_BS"]["b"]
    plac = placebo_g(panel, n_placebo)
    return {"primary": prim, "secondary": sec, "placebo": plac, "series": group_series(jvs, irt),
            "panel_counts": panel.groupby("country").size().to_dict()}


def run() -> dict:
    from collectors.common import RAW
    paths = [RAW / "eurostat_jvs_q_nace2.csv", RAW / "eurostat_irt_st_m.csv"]
    if not all(p.exists() for p in paths):
        raise SystemExit("Missing Eurostat files: commit and push docs/hypotheses/round3/G.md first, then python collect.py --sources eurostat_g")
    commit = registration_commit()
    if not commit:
        raise SystemExit("docs/hypotheses/round3/G.md is not committed: the registration must be committed before the real run")
    jvs = pd.read_csv(paths[0], dtype=str)
    irt = pd.read_csv(paths[1], dtype=str)
    return {"inputs_sha256": file_hashes(paths), "registration_commit": commit, "G": run_g(jvs, irt)}


def load_results() -> dict:
    from analysis.viz_theme import ROOT
    return json.loads((ROOT / "reports" / "hypotheses3_b_results.json").read_text(encoding="utf-8"))


def main() -> None:
    from analysis.viz_theme import ROOT
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    res = run()
    path = ROOT / "reports" / "hypotheses3_b_results.json"
    path.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("inputs_sha256",)}, indent=2, default=float)[:6000])
    print(f"written {path}")


if __name__ == "__main__":
    main()
