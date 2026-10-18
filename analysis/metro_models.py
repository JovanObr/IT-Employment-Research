"""Small, dependency-free helpers for the metro analysis: feature prep, OLS with robust (HC1) standard
errors, and repeated k-fold cross-validation. Kept in one place so notebooks stay readable and every
number in a report can be regenerated."""
from __future__ import annotations

import numpy as np
import pandas as pd

COMMON = ["wfh_share_pct_acs2019", "wfh_change_pp", "bachelors_plus_pct_acs2019", "log_pop", "log_inc",
          "log_rent", "median_age_acs2019", "hpi_growth_pre_pct", "hpi_growth_pct"]
PREDICTORS = {
    "A": ["log_it_emp", "preA", "log_lq", "log_estab_size"] + COMMON,   # IT employment outcome
    "B": ["log_size", "preB", "log_eq"] + COMMON,                        # IT establishment outcome
}
OUTCOME_COL = {"A": "yA", "B": "yB"}
SUBSET_COL = {"A": "usable", "B": "usable_estab"}
LABELS = {
    "log_it_emp": "IT jobs 2019 (log)", "preA": "IT job growth 2015-19", "log_lq": "IT concentration (LQ, log)",
    "log_estab_size": "Avg IT establishment size (log)", "log_size": "Total employment (log)",
    "preB": "IT establishment growth 2015-19", "log_eq": "IT establishment density (log)",
    "wfh_share_pct_acs2019": "Work-from-home share 2019", "wfh_change_pp": "Work-from-home change (pp)",
    "bachelors_plus_pct_acs2019": "Bachelor's or higher (%)", "log_pop": "Population (log)",
    "log_inc": "Median household income (log)", "log_rent": "Median rent (log)",
    "median_age_acs2019": "Median age", "hpi_growth_pre_pct": "House-price growth 2015-19",
    "hpi_growth_pct": "House-price growth 2019-24",
}


def prepare(p: pd.DataFrame) -> pd.DataFrame:
    """Add log-scale outcomes (percent log points) and log predictors."""
    p = p.copy()
    L = np.log
    p["yA"] = L(p["emp_it_2024"] / p["emp_it_2019"]) * 100
    p["yB"] = L(p["estabs_it_2024"] / p["estabs_it_2019"]) * 100
    p["preA"] = np.log1p(p["it_growth_pre_pct"] / 100) * 100
    p["preB"] = L(p["estabs_it_2019"] / p["estabs_it_2015"]) * 100
    p["log_size"] = L(p["emp_total_2019"]); p["log_it_emp"] = L(p["emp_it_2019"])
    p["log_estab_size"] = L(p["it_avg_estab_size_2019"]); p["log_lq"] = L(p["it_location_quotient_2019"])
    p["log_eq"] = L(p["it_estab_quotient_2019"]); p["log_pop"] = L(p["population_acs2019"])
    p["log_inc"] = L(p["median_hh_income_acs2019"]); p["log_rent"] = L(p["median_gross_rent_acs2019"])
    return p.replace([np.inf, -np.inf], np.nan)


def fit(df: pd.DataFrame, y: str, cols: list[str]) -> dict:
    """OLS on standardised predictors. Coefficient = change in outcome (log points) per +1 SD of the predictor."""
    d = df.dropna(subset=cols + [y])
    X = d[cols].astype(float)
    Xa = np.column_stack([np.ones(len(d)), ((X - X.mean()) / X.std()).values])
    yv = d[y].values
    b = np.linalg.lstsq(Xa, yv, rcond=None)[0]
    n, k = Xa.shape
    e = yv - Xa @ b
    bread = np.linalg.inv(Xa.T @ Xa)
    meat = (Xa * e[:, None]).T @ (Xa * e[:, None])
    se = np.sqrt(np.diag(bread @ meat @ bread * n / (n - k)))  # HC1: robust to unequal variance
    tab = pd.DataFrame({"coef": b[1:], "se": se[1:], "t": b[1:] / se[1:]}, index=cols)
    tab["ci_lo"], tab["ci_hi"] = tab["coef"] - 1.96 * tab["se"], tab["coef"] + 1.96 * tab["se"]
    return {"table": tab, "n": n, "r2": 1 - (e ** 2).sum() / ((yv - yv.mean()) ** 2).sum(), "y_sd": yv.std(), "data": d}


def cv_r2(df: pd.DataFrame, y: str, cols: list[str], reps: int = 20, k: int = 5) -> tuple[float, float]:
    """Out-of-sample R2 (mean, sd over repeated random k-fold splits). Negative = worse than guessing the mean."""
    d = df.dropna(subset=cols + [y])
    X = d[cols].astype(float)
    Xa = np.column_stack([np.ones(len(d)), ((X - X.mean()) / X.std()).values])
    yv, out = d[y].values, []
    for s in range(reps):
        idx = np.random.default_rng(s).permutation(len(d))
        sse = sst = 0.0
        for f in np.array_split(idx, k):
            tr = np.setdiff1d(idx, f)
            bt = np.linalg.lstsq(Xa[tr], yv[tr], rcond=None)[0]
            sse += ((yv[f] - Xa[f] @ bt) ** 2).sum(); sst += ((yv[f] - yv[tr].mean()) ** 2).sum()
        out.append(1 - sse / sst)
    return float(np.mean(out)), float(np.std(out))


def run(p: pd.DataFrame, which: str) -> dict:
    """Fit outcome 'A' (IT employment) or 'B' (IT establishments) on its usable metros."""
    sub = p[p[SUBSET_COL[which]]]
    res = fit(sub, OUTCOME_COL[which], PREDICTORS[which])
    res["cv_mean"], res["cv_sd"] = cv_r2(sub, OUTCOME_COL[which], PREDICTORS[which])
    return res
