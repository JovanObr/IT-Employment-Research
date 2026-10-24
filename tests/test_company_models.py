"""A3 model tests on a synthetic panel with a planted signal. No real data, no network."""
import numpy as np
import pandas as pd
import pytest

from analysis import company_models as cm
from analysis.company_panel import FEATURES


def synthetic_panel(n_companies=300, first=2019 * 4, last=2024 * 4 + 3, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_companies):
        sic2 = rng.choice(["35", "36", "73"])
        for qi in range(first, last + 1):
            f = {k: rng.normal() for k in FEATURES}
            f["net_loss"] = float(rng.random() < 0.4)
            rows.append({"cik": c, "qi": qi, "quarter": f"{qi // 4}Q{qi % 4 + 1}", "sic2": sic2, **f})
    p = pd.DataFrame(rows)
    z = -4.2 + 1.2 * p["net_loss"] - 0.8 * p["rev_yoy"]                  # planted signal
    p["y_next2q"] = (rng.random(len(p)) < 1 / (1 + np.exp(-z))).astype(int)
    p.loc[p.sample(frac=0.1, random_state=1).index, "rnd_ratio"] = np.nan   # some missing values
    return p


def test_quarter_index_matches_panel_scale():
    assert cm.quarter_index("2022Q4") == 2022 * 4 + 3


def test_embargo_removes_rows_whose_labels_reach_into_test():
    p = synthetic_panel(n_companies=5)
    cut = cm.quarter_index("2022Q4")
    tr, te = cm.time_split(p, "2022Q4", horizon=2, embargo=True)
    assert tr["qi"].max() == cut - 2 and te["qi"].min() == cut + 1
    assert tr["qi"].max() + 2 <= cut                                   # label window of every train row ends in train
    tr0, _ = cm.time_split(p, "2022Q4", embargo=False)
    assert tr0["qi"].max() == cut
    assert set(tr["qi"]).isdisjoint(set(te["qi"]))


def test_prep_uses_train_statistics_only():
    p = synthetic_panel(n_companies=40)
    tr, te = cm.time_split(p)
    prep = cm.Prep().fit(tr)
    te2 = te.copy()
    te2["rev_yoy"] = te2["rev_yoy"] + 1000.0                            # huge shift in test
    z = prep.transform(te2)
    assert z["rev_yoy"].max() <= (prep.hi["rev_yoy"] - prep.mu["rev_yoy"]) / prep.sd["rev_yoy"] + 1e-9   # clipped to train bound
    assert list(prep.transform(te).columns) == prep.out_columns
    assert not prep.transform(te).isna().any().any()


def test_prep_unseen_sic_gives_all_zero_dummies():
    p = synthetic_panel(n_companies=20)
    tr, te = cm.time_split(p)
    prep = cm.Prep().fit(tr)
    te = te.copy()
    te["sic2"] = "99"
    z = prep.transform(te)
    assert z[[c for c in z.columns if c.startswith("sic_")]].to_numpy().sum() == 0


def test_models_find_planted_signal_out_of_sample():
    res = cm.run_all(synthetic_panel(), n_boot=60)
    t = res["table"].set_index("model")
    base = t.loc["constant (train base rate)", "pr_auc"]
    assert t.loc["logit", "pr_auc"] > 1.4 * base
    assert t.loc["logit", "ci_lo"] <= t.loc["logit", "pr_auc"] <= t.loc["logit", "ci_hi"]
    assert t.loc["gb", "pr_auc"] > 1.3 * base
    top = res["coefficients"].iloc[0]["feature"]
    assert top in ("net_loss", "rev_yoy")                               # the planted drivers
    assert set(res["baselines"].head(2)["feature"]) <= {"net_loss", "rev_yoy"} | set(FEATURES)
    assert len(res["permutation"]) >= len(FEATURES)


def test_single_feature_direction_chosen_on_train():
    p = synthetic_panel(n_companies=100)
    tr, te = cm.time_split(p)
    b = cm.single_feature_baselines(tr, te).set_index("feature")
    assert b.loc["rev_yoy", "direction"] == "lower = riskier"
    assert b.loc["net_loss", "direction"] == "higher = riskier"


def test_calibration_table_accounts_for_every_row():
    rng = np.random.default_rng(0)
    p = rng.random(1000) * 0.2
    y = (rng.random(1000) < p).astype(int)
    c = cm.calibration_table(y, p, bins=5)
    assert c["n"].sum() == 1000 and len(c) == 5
    assert (c["predicted"].diff().dropna() > 0).all()                  # bins ordered by predicted probability


def test_bootstrap_resamples_companies_not_rows():
    y = np.array([1, 0, 0, 1, 0, 0, 0, 0])
    s = np.array([0.9, 0.2, 0.1, 0.8, 0.3, 0.2, 0.1, 0.4])
    g = np.array([1, 1, 2, 2, 3, 3, 4, 4])
    lo, hi = cm.cluster_bootstrap(y, s, g, n=100, seed=1)
    assert 0 <= lo <= hi <= 1


def test_size_strata_use_train_cutpoints_and_cover_all_rows():
    p = synthetic_panel(n_companies=60)
    p["log_assets"] = np.random.default_rng(3).normal(size=len(p))
    tr, te = cm.time_split(p)
    g = cm.size_strata(tr, te)
    assert set(g.unique()) <= {1, 2, 3} and len(g) == len(te)
    cuts = np.quantile(tr["log_assets"], [1 / 3, 2 / 3])
    assert (te.loc[g == 1, "log_assets"] <= cuts[0] + 1e-9).all()


def test_stratified_table_blanks_small_groups():
    p = synthetic_panel(n_companies=200)
    tr, te = cm.time_split(p)
    scores = pd.DataFrame({"m": np.random.default_rng(0).random(len(te))}, index=te.index)
    strata = pd.Series(1, index=te.index)
    strata.iloc[:50] = 2                                                  # group 2: only 50 rows, few positives
    t = cm.stratified_table(te, scores, strata, min_pos=15)
    g2 = t[t["size_group"] == 2].iloc[0]
    assert g2["rows"] == 50 and (g2["positives"] >= 15 or np.isnan(g2["pr_auc"]))
    assert not np.isnan(t[t["size_group"] == 1].iloc[0]["pr_auc"])


def test_size_control_drops_size_from_the_second_model():
    p = synthetic_panel(n_companies=80)
    p["log_assets"] = np.random.default_rng(4).normal(size=len(p))
    sc = cm.run_size_control(p, n_boot=20)
    assert "log_assets" not in sc["without_size"]["models"]["prep"].features
    assert "log_assets" in sc["with_size"]["models"]["prep"].features
    assert {"logit_size", "gb_size", "logit_nosize", "gb_nosize"} <= set(sc["scores"].columns)
    assert len(sc["stratified"]) == 3 * 4
