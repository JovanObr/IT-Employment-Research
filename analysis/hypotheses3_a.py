"""Round 3, Stream A: the pre-registered test H (docs/hypotheses/round3/H.md).

H   Slovenia's survey dip is not in the employment register: share of persons in employment in SKD J62 + J63 (SURS 0700921S),
    d = mean 2023 minus mean 2021; p from the null distribution of d simulated with the month-to-month noise of 2015-2019 (AR(1)).
    Predicted d > 0. (Newey-West on the 24 months is reported as a secondary: in synthetic tests it rejected a true null about
    30 % of the time with this little data, so it is not the primary.)

Follow the registration exactly; any change after the real run is a dated amendment in the registration file.

    python -m analysis.hypotheses3_a        # runs H on data/raw/surs_0700921S.csv, writes reports/hypotheses3_a_results.json
"""
from __future__ import annotations

import json
import logging
import subprocess

import numpy as np
import pandas as pd

from analysis.hypotheses import file_hashes
from analysis.hypotheses_b import newey_west

log = logging.getLogger("covid_it_data")
TOTAL = "SKD dejavnost - SKUPAJ"
ALL_PERSONS = "1 Delovno aktivno prebivalstvo - SKUPAJ"
EMPLOYEES = "11 Zaposlene osebe - skupaj"
IT = ("J62", "J63")
LAGS = 6
BASE, TARGET, TARGET2 = 2021, 2023, 2024
CALIB = ("2015-01-01", "2019-12-01")
SLOW = ("2022-01-01", "2023-12-01")
SURVEY = {2021: 4.8, 2023: 3.8, 2024: 4.3, 2025: 4.5}      # Eurostat isoc_sks_itspt, SI, PC_EMP (reports/hypotheses2_b_results.json, B1)


# ---------------------------------------------------------------------------------------- data
def _is(activity: pd.Series, code: str) -> pd.Series:
    return activity.str.strip().str.startswith(code + " ")


def share_series(df: pd.DataFrame, status: str = ALL_PERSONS, codes=IT) -> pd.DataFrame:
    """Monthly: persons in the IT divisions, the total, and the share s = 100 x it / total."""
    d = df[df["status"].str.strip() == status]
    tot = d[d["activity"].str.strip() == TOTAL].set_index("month")["value"]
    it = sum(d[_is(d["activity"], c)].set_index("month")["value"] for c in codes)
    out = pd.DataFrame({"it": it, "total": tot}).dropna().sort_index()
    out["s"] = 100 * out["it"] / out["total"]
    return out


# ---------------------------------------------------------------------------------------- tests
def year_shift(s: pd.Series, base: int = BASE, target: int = TARGET, lags: int = LAGS) -> dict:
    """d = mean(target year) - mean(base year): OLS of s on a constant and a target-year indicator, Newey-West."""
    idx = pd.DatetimeIndex(s.index)
    keep = (idx.year == base) | (idx.year == target)
    y = s[keep].to_numpy(float)
    x = (idx[keep].year == target).astype(float)
    r = newey_west(y, np.column_stack([np.ones_like(x), x]), lags=lags)
    from scipy import stats
    half = stats.t.ppf(0.975, r["df"]) * r["se"][1]
    return {"n": int(r["n"]), "mean_base": float(y[x == 0].mean()), "mean_target": float(y[x == 1].mean()), "d": float(r["beta"][1]),
            "se": float(r["se"][1]), "ci_lo": float(r["beta"][1] - half), "ci_hi": float(r["beta"][1] + half), "p": float(r["p"][1]),
            "df": int(r["df"])}


def d_null(phi: float, sd: float, n_sim: int = 10_000, seed: int = 0) -> np.ndarray:
    """Null distribution of d = mean(months 25-36) - mean(months 1-12) for 36 months of AR(1) noise with no change."""
    rng = np.random.default_rng(seed)
    sd0 = sd / np.sqrt(max(1 - phi ** 2, 1e-6))
    e = np.empty((n_sim, 36))
    e[:, 0] = rng.normal(0, sd0, n_sim)
    for k in range(1, 36):
        e[:, k] = phi * e[:, k - 1] + rng.normal(0, sd, n_sim)
    return e[:, 24:].mean(axis=1) - e[:, :12].mean(axis=1)


def sim_test(s: pd.Series, phi: float, sd: float, base: int = BASE, target: int = TARGET, n_sim: int = 10_000, seed: int = 0) -> dict:
    """Primary test: observed d against its simulated null; two-sided p = (#|d_null| >= |d| + 1) / (n_sim + 1); 95 % interval d +- 1.96 sd(null)."""
    idx = pd.DatetimeIndex(s.index)
    a, b = s[idx.year == base], s[idx.year == target]
    if len(a) != 12 or len(b) != 12:
        raise ValueError(f"need 12 months in {base} and {target}, got {len(a)} and {len(b)}")
    d = float(b.mean() - a.mean())
    null = d_null(phi, sd, n_sim, seed)
    sdn = float(null.std(ddof=1))
    return {"n": 24, "mean_base": float(a.mean()), "mean_target": float(b.mean()), "d": d, "null_sd": sdn,
            "ci_lo": d - 1.96 * sdn, "ci_hi": d + 1.96 * sdn, "p": float(((np.abs(null) >= abs(d)).sum() + 1) / (n_sim + 1)), "n_sim": n_sim}


def block_placebo(s: pd.Series, phi: float, sd: float, n_rep: int = 2000, block: int = 12, seed: int = 2,
                  start: str = None, end: str = None) -> float:
    """Checks the AR(1) noise model: 36-month series made of random 12-month blocks of the real detrended 2015-2019 residuals
    (no change built in), run through the primary test; returns the share with p < 0.05 (about 5 % if the model is adequate)."""
    start, end = start or CALIB[0], end or CALIB[1]
    w = s[(s.index >= start) & (s.index <= end)].to_numpy(float)
    t = np.arange(len(w), dtype=float)
    res = w - np.polyval(np.polyfit(t, w, 1), t)
    rng = np.random.default_rng(seed)
    null = d_null(phi, sd, 4000, seed + 1)
    hits = 0
    for _ in range(n_rep):
        starts = rng.integers(0, len(res) - block + 1, 36 // block)
        x = np.concatenate([res[k:k + block] for k in starts])
        d = x[24:].mean() - x[:12].mean()
        hits += ((np.abs(null) >= abs(d)).sum() + 1) / (len(null) + 1) < 0.05
    return hits / n_rep


def ar1_noise(s: pd.Series, start: str = CALIB[0], end: str = CALIB[1]) -> dict:
    """Linear trend over the calibration window; AR(1) of the residuals: coefficient and innovation sd."""
    w = s[(s.index >= start) & (s.index <= end)].to_numpy(float)
    t = np.arange(len(w), dtype=float)
    res = w - np.polyval(np.polyfit(t, w, 1), t)
    phi = float(np.dot(res[1:], res[:-1]) / np.dot(res[:-1], res[:-1]))
    sd = float(np.std(res[1:] - phi * res[:-1], ddof=1))
    return {"phi": phi, "sd": sd, "n": len(w)}


def simulate(phi: float, sd: float, shift: float = 0.0, n_sim: int = 2000, seed: int = 0, test: str = "sim", lags: int = LAGS) -> np.ndarray:
    """p-values of a test on simulated 36-month series (AR(1) noise; `shift` added to months 25-36). test = "sim" (primary) or "nw"."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=36, freq="MS")
    sd0 = sd / np.sqrt(max(1 - phi ** 2, 1e-6))
    null = d_null(phi, sd, 4000, seed + 7) if test == "sim" else None
    ps = np.empty(n_sim)
    for i in range(n_sim):
        e = np.empty(36)
        e[0] = rng.normal(0, sd0)
        for k in range(1, 36):
            e[k] = phi * e[k - 1] + rng.normal(0, sd)
        e[24:] += shift
        if test == "sim":
            d = e[24:].mean() - e[:12].mean()
            ps[i] = ((np.abs(null) >= abs(d)).sum() + 1) / (len(null) + 1)
        else:
            ps[i] = year_shift(pd.Series(e, index=idx), 2021, 2023, lags)["p"]
    return ps


def power(phi: float, sd: float, n_sim: int = 500, seed: int = 1) -> float:
    """Smallest shift (grid of 1/20 of the null sd of d) found with p < 0.05 at least 80 % of the time by the primary test."""
    sdn = float(d_null(phi, sd, 4000, seed).std())
    for k in range(1, 201):
        shift = k * sdn / 20
        if (simulate(phi, sd, shift, n_sim, seed) < 0.05).mean() >= 0.8:
            return float(shift)
    return float("nan")


def trend_gap(s: pd.Series, lags: int = LAGS) -> dict:
    """Mean deviation of 2022-2023 from the 2015-2019 linear trend (Newey-West on the deviations, constant only)."""
    fit = s[(s.index >= CALIB[0]) & (s.index <= CALIB[1])]
    t0 = pd.Timestamp(CALIB[0])
    months = lambda ix: (ix.year - t0.year) * 12 + (ix.month - t0.month)
    coef = np.polyfit(months(fit.index).to_numpy(float), fit.to_numpy(float), 1)
    w = s[(s.index >= SLOW[0]) & (s.index <= SLOW[1])]
    dev = w.to_numpy(float) - np.polyval(coef, months(w.index).to_numpy(float))
    r = newey_west(dev, np.ones((len(dev), 1)), lags=lags)
    return {"mean_deviation": float(r["beta"][0]), "se": float(r["se"][0]), "p": float(r["p"][0]), "n": int(r["n"]),
            "trend_per_year": float(12 * coef[0])}


def _noise(s: pd.Series) -> dict:
    n = ar1_noise(s)
    return {"phi": n["phi"], "sd": n["sd"]}


def run_h(df: pd.DataFrame, n_sim: int = 2000) -> dict:
    s = share_series(df)
    noise = ar1_noise(s["s"])
    mde = power(noise["phi"], noise["sd"])
    log.info("H design (before the comparison): AR(1) phi %.2f, sd %.4f; smallest shift found 80 %% of the time %.3f points",
             noise["phi"], noise["sd"], mde)
    prim = sim_test(s["s"], noise["phi"], noise["sd"])
    prim["predicted_sign"] = bool(prim["d"] > 0)
    prim["mde_points"] = mde
    prim["survey_change"] = SURVEY[TARGET] - SURVEY[BASE]
    yearly = s.groupby(s.index.year)[["it", "total", "s"]].mean()
    emp = share_series(df, status=EMPLOYEES)
    sec = {"persons_change_pct": float(100 * (yearly.loc[TARGET, "it"] / yearly.loc[BASE, "it"] - 1)),
           "persons_base": float(yearly.loc[BASE, "it"]), "persons_target": float(yearly.loc[TARGET, "it"]),
           "year_2024": sim_test(s["s"], noise["phi"], noise["sd"], BASE, TARGET2),
           "newey_west_6": year_shift(s["s"]), "slowdown": trend_gap(s["s"]),
           "phi_090": sim_test(s["s"], 0.9, noise["sd"]),
           "j62_only": sim_test((j := share_series(df, codes=("J62",))["s"]), **_noise(j)),
           "employees_only": sim_test(emp["s"], **_noise(emp["s"]))}
    plac = {"n_rep": n_sim, **noise, "block_months": 12,
            "share_p_below_005": block_placebo(s["s"], noise["phi"], noise["sd"], n_rep=n_sim)}
    yearly_out = [{"year": int(y), "it": float(r["it"]), "total": float(r["total"]), "share": float(r["s"]),
                   "survey": SURVEY.get(int(y))} for y, r in yearly.iterrows()]
    return {"primary": prim, "secondary": sec, "placebo": plac, "yearly": yearly_out}


def registration_commit() -> str | None:
    try:
        return subprocess.run(["git", "log", "--diff-filter=A", "--format=%h", "-1", "--", "docs/hypotheses/round3/H.md"],
                              capture_output=True, text=True, check=True).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def run() -> dict:
    from collectors.common import RAW
    path = RAW / "surs_0700921S.csv"
    if not path.exists():
        raise SystemExit("Missing data/raw/surs_0700921S.csv: commit and push docs/hypotheses/round3/H.md first, then python collect.py --sources surs")
    commit = registration_commit()
    if not commit:
        raise SystemExit("docs/hypotheses/round3/H.md is not committed: the registration must be committed before the real run")
    df = pd.read_csv(path, parse_dates=["month"])
    return {"inputs_sha256": file_hashes([path]), "registration_commit": commit, "H": run_h(df)}


def main() -> None:
    from analysis.viz_theme import ROOT
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    res = run()
    path = ROOT / "reports" / "hypotheses3_a_results.json"
    path.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "inputs_sha256"}, indent=2, default=float))
    print(f"written {path}")


if __name__ == "__main__":
    main()
