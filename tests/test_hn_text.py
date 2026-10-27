"""Hacker News text analysis (analysis/hn_text) on SYNTHETIC data with planted structure."""
import numpy as np
import pandas as pd
import pytest

from analysis import hn_text as ht
from hn_synth import make_hn


@pytest.fixture(scope="module")
def synth():
    posts, text = make_hn(posts_per_month=40, seed=1)
    posts["month"] = pd.to_datetime(posts["thread_month"]).dt.to_period("M").dt.to_timestamp()
    return posts.merge(text, on="post_id")


def test_binary_segmentation_finds_a_planted_step():
    rng = np.random.default_rng(0)
    x = np.r_[rng.normal(0.3, 0.02, 60), rng.normal(0.8, 0.02, 60)]
    assert ht.binary_segmentation(x) == [pytest.approx(60, abs=2)]


def test_binary_segmentation_finds_nothing_in_noise():
    x = np.random.default_rng(1).normal(0.5, 0.02, 120)
    assert ht.binary_segmentation(x) == []


def test_binary_segmentation_fixed_number_and_short_series():
    x = np.r_[np.zeros(30), np.ones(30), np.zeros(30)] + np.random.default_rng(2).normal(0, 0.01, 90)
    b = ht.binary_segmentation(x, n_bkps=2)
    assert len(b) == 2 and abs(b[0] - 30) <= 2 and abs(b[1] - 60) <= 2
    assert ht.binary_segmentation(np.arange(5)) == []


def test_remote_change_point_lands_near_2020(synth):
    s = ht.monthly_share(synth, "remote")
    months = ht.break_months(s, ht.binary_segmentation(s.to_numpy(), n_bkps=1))
    assert months[0] in ("2020-03", "2020-04", "2020-05")


def test_two_proportion_and_before_after(synth):
    r = ht.two_proportion(10, 100, 30, 100)
    assert r["diff_pp"] == pytest.approx(20) and r["ci_low_pp"] < 20 < r["ci_high_pp"]
    ba = ht.before_after(synth, "ai_ml")
    assert ba["diff_pp"] > 10 and ba["n_before"] > 0 and ba["n_after"] > 0


def test_cutoff_puts_nov_2022_thread_before_chatgpt(synth):
    ba = ht.before_after(synth, "ai_ml")
    n_before = (synth["month"] <= pd.Timestamp("2022-11-01")).sum()
    assert ba["n_before"] == n_before


def test_pretrend_gap_flat_series_has_no_gap():
    idx = pd.period_range("2016-01", "2024-12", freq="M").to_timestamp()
    s = pd.Series(0.1, index=idx)
    g = ht.pretrend_gap(s)
    assert g["slope_pp_per_year"] == pytest.approx(0, abs=1e-6) and g["mean_gap_pp"] == pytest.approx(0, abs=1e-6)


def test_junior_decline_has_negative_pre_slope(synth):
    g = ht.pretrend_gap(ht.monthly_share(synth, "junior"))
    assert g["slope_pp_per_year"] < 0


def test_topic_model_recovers_planted_topics_and_shares_sum_to_one(synth):
    shares, terms = ht.topic_model_monthly(synth, k=6, min_df=5)
    assert list(shares.columns) == ["month", "topic", "share"]
    assert len(terms) == 6
    per_month = shares.groupby("month")["share"].sum()
    assert np.allclose(per_month, 1.0)
    joined = " ".join(terms["top_terms"])
    for word in ("kubernetes", "pytorch", "react", "swift", "security", "pandas"):
        assert word in joined


def test_topic_names_override_and_weights_method(synth):
    shares, terms = ht.topic_model_monthly(synth, k=6, min_df=5, names={0: "my topic"})
    assert terms.loc[0, "label"] == "T1: my topic"
    W, _, _, _, keep = ht.fit_topics(synth["text"], k=6, min_df=5)
    w = ht.monthly_topic_shares(synth["month"], W, keep, [f"t{i}" for i in range(6)], method="weights")
    assert np.allclose(w.groupby("month")["share"].sum(), 1.0)
    with pytest.raises(ValueError):
        ht.monthly_topic_shares(synth["month"], W, keep, [f"t{i}" for i in range(6)], method="nope")


def test_logistics_words_are_not_topic_terms(synth):
    _, terms = ht.topic_model_monthly(synth, k=6, min_df=5)
    assert "remote" not in " ".join(terms["top_terms"]).split(", ")


def test_negation_diagnostic_counts_obvious_negations():
    df = pd.DataFrame({"remote": [1, 1, 1, 0], "junior": [1, 1, 0, 0],
                       "text": ["No remote work, onsite only", "Fully remote team", "remote: not available",
                                "onsite"]})
    d = ht.negation_diagnostic(df)
    assert d.loc["remote", "flagged_posts"] == 3 and d.loc["remote", "with_obvious_negation"] == 2
    df2 = pd.DataFrame({"remote": [0], "junior": [1], "text": ["no interns please"]})
    assert ht.negation_diagnostic(df2).loc["junior", "with_obvious_negation"] == 1


def test_validation_sample_is_reproducible_and_unlabelled(synth):
    a, b = ht.make_validation_sample(synth, 100), ht.make_validation_sample(synth, 100)
    assert len(a) == 100 and a["post_id"].tolist() == b["post_id"].tolist() and a["post_id"].is_unique
    assert (a["label_remote"] == "").all() and (a["label_junior"] == "").all()


def test_wilson_interval():
    lo, hi = ht.wilson(8, 10)
    assert 0.4 < lo < 0.8 < hi < 1.0
    assert np.isnan(ht.wilson(0, 0)[0])


def test_validate_flags_precision_recall():
    posts = pd.DataFrame({"post_id": ["1", "2", "3", "4", "5"], "remote": [1, 1, 0, 0, 1], "junior": [1, 0, 0, 0, 0]})
    lab = pd.DataFrame({"post_id": ["1", "2", "3", "4", "5"], "label_remote": [1, 0, 1, 0, ""],
                        "label_junior": [1, 0, 0, 1, 0]})
    v = ht.validate_flags(lab, posts)
    r = v.loc["remote"]       # labelled rows 1-4: tp=1 (id1), fp=1 (id2), fn=1 (id3), tn=1 (id4); id5 unlabelled
    assert (r["labelled"], r["true_pos"], r["false_pos"], r["false_neg"]) == (4, 1, 1, 1)
    assert r["precision"] == pytest.approx(0.5) and r["recall"] == pytest.approx(0.5)
    j = v.loc["junior"]
    assert j["precision"] == pytest.approx(1.0) and j["recall"] == pytest.approx(0.5)
    assert "fewer than 20" in j["warning"]


def test_run_writes_output_without_touching_real_data(data_dir, monkeypatch):
    posts, text = make_hn(posts_per_month=20, seed=3, start="2019-01", end="2021-12")
    posts.to_csv(data_dir / "raw" / "hn_whoishiring_posts.csv", index=False)
    text.to_csv(data_dir / "raw" / "hn_whoishiring_text.csv", index=False)
    monkeypatch.setattr(ht, "RAW", data_dir / "raw")
    monkeypatch.setattr(ht, "PROCESSED", data_dir / "processed")
    out = ht.run(k=6, out=data_dir / "processed" / "hn_topics_monthly.csv")
    saved = pd.read_csv(data_dir / "processed" / "hn_topics_monthly.csv")
    assert list(saved.columns) == ["month", "topic", "share"] and len(saved) == len(out)
