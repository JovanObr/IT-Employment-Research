"""A3, part 2: baseline layoff-risk models on the company-quarter panel (see analysis/company_panel.py).

Two small models, deliberately low-capacity (around 150 train positives): L2 logistic regression and a shallow
gradient-boosted tree. The split is by TIME. Because a row's label looks two quarters ahead, the last two training
quarters would otherwise carry labels from the test period; by default those rows are dropped (embargo = HORIZON).
Everything that is estimated (clip bounds, medians, scaling, models) uses TRAIN rows only.

Run:  python -m analysis.company_models
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from analysis.company_panel import FEATURES, HORIZON, SPLIT_LAST_TRAIN
from collectors.common import PROCESSED

log = logging.getLogger("covid_it_data")

LABEL = "y_next2q"
MISSING_FLAG_SHARE = 0.05   # a missing-value indicator is added for features missing in >= 5% of train rows


def quarter_index(label: str) -> int:
    """'2022Q4' -> 2022*4 + 3, same scale as the panel's `qi`."""
    return int(label[:4]) * 4 + int(label[5]) - 1


# ---------------------------------------------------------------------------------------- split
def time_split(panel: pd.DataFrame, last_train: str = SPLIT_LAST_TRAIN, horizon: int = HORIZON,
               embargo: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train: row quarters <= last_train (minus `horizon` quarters when embargo, so no training label reaches into
    the test period). Test: row quarters after last_train."""
    cut = quarter_index(last_train)
    train = panel[panel["qi"] <= cut - (horizon if embargo else 0)]
    test = panel[panel["qi"] > cut]
    return train.reset_index(drop=True), test.reset_index(drop=True)


# ---------------------------------------------------------------------------------------- preprocessing
class Prep:
    """Winsorise (train 1st-99th percentile), median-impute, standardise, add missing-value flags and SIC dummies.
    Fitted on train only; `transform` applies the stored train numbers to any rows."""

    def __init__(self, features=FEATURES, clip=(0.01, 0.99)):
        self.features, self.clip = list(features), clip

    def fit(self, df: pd.DataFrame) -> "Prep":
        X = df[self.features]
        self.lo, self.hi = X.quantile(self.clip[0]), X.quantile(self.clip[1])
        Xc = X.clip(self.lo, self.hi, axis=1)
        self.med = Xc.median()
        self.miss_cols = [c for c in self.features if X[c].isna().mean() >= MISSING_FLAG_SHARE]
        Xi = Xc.fillna(self.med)
        self.mu, self.sd = Xi.mean(), Xi.std().replace(0, 1.0)
        self.sic_levels = sorted(df["sic2"].astype(str).unique())
        self.out_columns = (self.features + [f"{c}_missing" for c in self.miss_cols]
                            + [f"sic_{l}" for l in self.sic_levels])
        return self

    def sic_dummies(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({f"sic_{l}": (df["sic2"].astype(str) == l).astype(float) for l in self.sic_levels},
                            index=df.index)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[self.features]
        flags = X[self.miss_cols].isna().astype(float).add_suffix("_missing")
        Z = (X.clip(self.lo, self.hi, axis=1).fillna(self.med) - self.mu) / self.sd
        return pd.concat([Z, flags, self.sic_dummies(df)], axis=1)

    def raw_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """For the tree model: untouched features (NaN kept, trees handle it) plus SIC dummies."""
        return pd.concat([df[self.features], self.sic_dummies(df)], axis=1)


# ---------------------------------------------------------------------------------------- models
def fit_models(train: pd.DataFrame, seed: int = 0, features=FEATURES) -> dict:
    prep = Prep(features).fit(train)
    y = train[LABEL].to_numpy()
    logit = LogisticRegression(C=0.5, max_iter=2000).fit(prep.transform(train), y)
    gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=100,
                                        l2_regularization=1.0, random_state=seed).fit(prep.raw_matrix(train), y)
    return {"prep": prep, "logit": logit, "gb": gb}


def predict(models: dict, df: pd.DataFrame) -> pd.DataFrame:
    p = models["prep"]
    return pd.DataFrame({"logit": models["logit"].predict_proba(p.transform(df))[:, 1],
                         "gb": models["gb"].predict_proba(p.raw_matrix(df))[:, 1]}, index=df.index)


def coefficients(models: dict) -> pd.DataFrame:
    """Logistic coefficients per 1 standard deviation of the (winsorised) feature; odds ratio = exp(coef)."""
    names = models["prep"].out_columns
    c = pd.DataFrame({"feature": names, "coef": models["logit"].coef_[0]})
    c["odds_ratio"] = np.exp(c["coef"])
    return c.reindex(c["coef"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def permutation_table(models: dict, test: pd.DataFrame, n_repeats: int = 10, seed: int = 0) -> pd.DataFrame:
    X = models["prep"].raw_matrix(test)
    r = permutation_importance(models["gb"], X, test[LABEL], scoring="average_precision",
                               n_repeats=n_repeats, random_state=seed)
    out = pd.DataFrame({"feature": X.columns, "pr_auc_drop": r.importances_mean, "sd": r.importances_std})
    return out.sort_values("pr_auc_drop", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------------------- evaluation
def cluster_bootstrap(y, score, groups, n: int = 300, seed: int = 0) -> tuple[float, float]:
    """95% interval for PR-AUC, resampling whole COMPANIES (rows of one company are strongly correlated)."""
    y, score, groups = np.asarray(y), np.asarray(score), np.asarray(groups)
    by = {g: np.flatnonzero(groups == g) for g in np.unique(groups)}
    keys = list(by)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = np.concatenate([by[keys[i]] for i in rng.integers(0, len(keys), len(keys))])
        if y[idx].sum() == 0:
            continue
        vals.append(average_precision_score(y[idx], score[idx]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def evaluate(test: pd.DataFrame, scores: pd.DataFrame, base_train: float, n_boot: int = 300) -> pd.DataFrame:
    y = test[LABEL].to_numpy()
    base = y.mean()
    rows = [{"model": "constant (train base rate)", "pr_auc": base, "ci_lo": np.nan, "ci_hi": np.nan, "lift": 1.0,
             "roc_auc": 0.5, "brier": brier_score_loss(y, np.full(len(y), base_train))}]
    for m in scores.columns:
        p = scores[m].to_numpy()
        lo, hi = cluster_bootstrap(y, p, test["cik"], n=n_boot)
        pr = average_precision_score(y, p)
        rows.append({"model": m, "pr_auc": pr, "ci_lo": lo, "ci_hi": hi, "lift": pr / base,
                     "roc_auc": roc_auc_score(y, p), "brier": brier_score_loss(y, p)})
    return pd.DataFrame(rows)


def single_feature_baselines(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Each feature on its own as a risk score; the direction (sign) is chosen on TRAIN only."""
    rows = []
    for f in FEATURES:
        med = train[f].median()
        sign = 1.0 if roc_auc_score(train[LABEL], train[f].fillna(med)) >= 0.5 else -1.0
        s = sign * test[f].fillna(med)
        rows.append({"feature": f, "direction": "higher = riskier" if sign > 0 else "lower = riskier",
                     "pr_auc": average_precision_score(test[LABEL], s), "roc_auc": roc_auc_score(test[LABEL], s)})
    return pd.DataFrame(rows).sort_values("pr_auc", ascending=False).reset_index(drop=True)


def calibration_table(y, p, bins: int = 5) -> pd.DataFrame:
    """Mean predicted vs observed rate in equal-count bins of the predicted probability (sanity check only)."""
    d = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    d["bin"] = pd.qcut(d["p"], bins, duplicates="drop", labels=False)
    return d.groupby("bin").agg(n=("y", "size"), predicted=("p", "mean"), observed=("y", "mean")).reset_index()


def run_all(panel: pd.DataFrame, embargo: bool = True, n_boot: int = 300, seed: int = 0,
            features=FEATURES) -> dict:
    train, test = time_split(panel, embargo=embargo)
    models = fit_models(train, seed, features)
    scores = predict(models, test)
    base_train = float(train[LABEL].mean())
    return {"train": train, "test": test, "models": models, "scores": scores, "base_train": base_train,
            "table": evaluate(test, scores, base_train, n_boot), "baselines": single_feature_baselines(train, test),
            "coefficients": coefficients(models), "permutation": permutation_table(models, test, seed=seed),
            "calibration": {m: calibration_table(test[LABEL], scores[m]) for m in scores.columns}}


def describe(res: dict) -> None:
    tr, te = res["train"], res["test"]
    log.info("Train: %d rows, %d positives (%.2f%%), %d companies | Test: %d rows, %d positives (%.2f%%), %d companies "
             "(%d with a positive)", len(tr), int(tr[LABEL].sum()), 100 * tr[LABEL].mean(), tr["cik"].nunique(),
             len(te), int(te[LABEL].sum()), 100 * te[LABEL].mean(), te["cik"].nunique(),
             te.loc[te[LABEL] == 1, "cik"].nunique())
    log.info("Out-of-sample results (95%% interval: bootstrap over companies):\n%s",
             res["table"].round(4).to_string(index=False))
    log.info("Single features on their own (direction chosen on train):\n%s", res["baselines"].round(4).to_string(index=False))
    log.info("Logistic regression, top coefficients (per 1 sd):\n%s", res["coefficients"].head(8).round(3).to_string(index=False))
    log.info("Gradient boosting, permutation importance on test (PR-AUC drop):\n%s",
             res["permutation"].head(8).round(4).to_string(index=False))
    for m, c in res["calibration"].items():
        log.info("Calibration, %s (5 equal-count bins; mean predicted overall %.3f vs observed %.3f):\n%s", m,
                 res["scores"][m].mean(), te[LABEL].mean(), c.round(4).to_string(index=False))


# ---------------------------------------------------------------------------------------- size control
SIZE = "log_assets"


def size_strata(train: pd.DataFrame, test: pd.DataFrame, n: int = 3) -> pd.Series:
    """Size group of every TEST row (1 = smallest), cut at the TRAIN quantiles of log assets (median-filled)."""
    med = train[SIZE].median()
    cuts = np.quantile(train[SIZE].fillna(med), np.linspace(0, 1, n + 1)[1:-1])
    return pd.Series(np.digitize(test[SIZE].fillna(med), cuts) + 1, index=test.index, name="size_group")


def stratified_table(test: pd.DataFrame, scores: pd.DataFrame, strata: pd.Series, min_pos: int = 15) -> pd.DataFrame:
    """PR-AUC of each score inside each size group; left empty (NaN) where there are fewer than `min_pos` positives."""
    rows = []
    for g in sorted(strata.unique()):
        m = (strata == g).to_numpy()
        y = test.loc[m, LABEL].to_numpy()
        base = y.mean()
        for model in scores.columns:
            ok = y.sum() >= min_pos
            pr = average_precision_score(y, scores.loc[m, model]) if ok else np.nan
            rows.append({"size_group": int(g), "model": model, "rows": int(m.sum()), "positives": int(y.sum()),
                         "base_rate": base, "pr_auc": pr, "lift": pr / base if ok else np.nan})
    return pd.DataFrame(rows)


def run_size_control(panel: pd.DataFrame, embargo: bool = True, n_boot: int = 300, seed: int = 0) -> dict:
    """Does anything besides company size carry signal? Refit both models WITHOUT log assets and compare, overall
    and inside size groups (where size is held roughly constant)."""
    no_size = [f for f in FEATURES if f != SIZE]
    with_size = run_all(panel, embargo, n_boot, seed)
    without = run_all(panel, embargo, n_boot, seed, features=no_size)
    test = with_size["test"]
    scores = pd.concat([with_size["scores"].add_suffix("_size"), without["scores"].add_suffix("_nosize")], axis=1)
    strata = size_strata(with_size["train"], test)
    return {"with_size": with_size, "without_size": without, "test": test, "scores": scores, "strata": strata,
            "stratified": stratified_table(test, scores, strata),
            "overall": evaluate(test, scores, with_size["base_train"], n_boot)}


def describe_size_control(sc: dict) -> None:
    log.info("SIZE CONTROL, overall test (models with and without log assets):\n%s",
             sc["overall"].round(4).to_string(index=False))
    log.info("Test rows by size group (cut at train terciles): %s", sc["strata"].value_counts().sort_index().to_dict())
    log.info("PR-AUC inside size groups (blank = fewer than 15 positives):\n%s",
             sc["stratified"].round(4).to_string(index=False))
    log.info("Logistic regression WITHOUT size, top coefficients:\n%s",
             sc["without_size"]["coefficients"].head(8).round(3).to_string(index=False))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    path = PROCESSED / "company_panel.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found - run: python -m analysis.company_panel")
    panel = pd.read_csv(path, dtype={"sic": str, "sic2": str})
    for embargo in (True, False):
        log.info("===== split: train up to %s, %s =====", SPLIT_LAST_TRAIN,
                 "last 2 train quarters dropped (labels would reach into the test period)" if embargo
                 else "no embargo (as first specified; mild label overlap)")
        res = run_all(panel, embargo=embargo)
        describe(res)
        describe_size_control(run_size_control(panel, embargo=embargo))
        if embargo:
            out = res["test"][["cik", "quarter", LABEL]].join(res["scores"])
            out.to_csv(PROCESSED / "company_predictions_test.csv", index=False)
            log.info("Test predictions -> %s", PROCESSED / "company_predictions_test.csv")


if __name__ == "__main__":
    main()
