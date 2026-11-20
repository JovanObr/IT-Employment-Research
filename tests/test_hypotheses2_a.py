"""Round 2 tests C2 and E: a planted effect must be found, a null must not be (synthetic data only)."""
import numpy as np
import pandas as pd

from analysis import hypotheses2_a as h2


# ---------------------------------------------------------------------------------------- C2
def _c2_data(n=500, effect=-0.08, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for t in (2024, 2025):
        ann = rng.random(n) < 0.12
        rows.append(pd.DataFrame({"cik": np.arange(n), "year": t, "announced": ann.astype(int),
                                  "outcome": rng.standard_t(4, n) * 0.08 + 0.02 + effect * ann, "sic3": "737",
                                  "log_assets": rng.normal(size=n)}))
    return pd.concat(rows, ignore_index=True)


def test_c2_finds_a_planted_cut_and_not_a_null():
    r = h2.test_c2(_c2_data(), n_perm=1000, n_boot=300)
    assert r["p"] < 0.01 and r["predicted_sign"] and r["ci_hi"] < 0 and set(r["by_year"]) == {2024, 2025}
    assert h2.test_c2(_c2_data(effect=0.0, seed=3), n_perm=1000, n_boot=200)["p"] > 0.05


def test_c2_permutation_keeps_group_sizes_within_year():
    d = _c2_data(n=60)
    null = h2.perm_within(d["outcome"].to_numpy(), d["announced"].to_numpy(), d["year"].to_numpy(), 5, np.random.default_rng(0))
    assert len(null) == 5 and np.isfinite(null).all()


def test_c2_year_difference_alone_does_not_create_an_effect():
    """2025 has more announcers AND lower growth for everyone; shuffling within year must not call that an effect."""
    rng = np.random.default_rng(5)
    a = pd.DataFrame({"cik": range(400), "year": 2024, "announced": (rng.random(400) < 0.05).astype(int), "outcome": rng.normal(0.10, 0.05, 400)})
    b = pd.DataFrame({"cik": range(400), "year": 2025, "announced": (rng.random(400) < 0.40).astype(int), "outcome": rng.normal(-0.10, 0.05, 400)})
    d = pd.concat([a, b], ignore_index=True)
    assert h2.test_c2(d, n_perm=1000, n_boot=200)["p"] > 0.05


def test_c2_placebo_rate_is_near_five_percent():
    fp = h2.placebo_c2(_c2_data(n=300, effect=0.0, seed=7), n_rep=120, n_perm=150)["false_positive_rate"]
    assert fp <= 0.12


def test_sample_c2_builds_year_pairs_and_drops_jumps_and_non_tech():
    heads = pd.DataFrame({"cik": [1, 1, 1, 2, 2, 2, 3, 3], "period_year": [2023, 2024, 2025] * 2 + [2023, 2024],
                          "employees": [100, 90, 95, 100, 5000, 5100, 100, 80]})
    uni = pd.DataFrame({"cik": [1, 2, 3], "is_tech": [True, True, False], "sic": ["7372", "3674", "2834"]})
    ann = pd.DataFrame({"cik": [1, 2], "date": pd.to_datetime(["2024-03-01", "2025-05-01"])})
    d = h2.sample_c2(heads, uni, ann).set_index(["cik", "year"])
    assert (1, 2024) in d.index and d.loc[(1, 2024), "announced"] == 1 and d.loc[(1, 2025), "announced"] == 0
    assert (2, 2024) not in d.index and d.loc[(2, 2025), "announced"] == 1      # 100 -> 5000 is a parsing jump
    assert 3 not in d.index.get_level_values(0) and d.loc[(2, 2025), "sic3"] == "367"


def test_announcements_are_unique_per_company_and_day():
    lay = pd.DataFrame({"company": ["A", "A", "B"], "date": ["2024-01-02", "2024-01-02", "2024-02-01"]})
    m = pd.DataFrame({"layoffs_company": ["A", "B"], "cik": [1.0, 2.0]})
    a = h2.announcements(lay, m)
    assert len(a) == 2 and a["cik"].dtype.kind == "i"


# ---------------------------------------------------------------------------------------- E
def test_earnings_dates_reads_only_8k_item_202():
    sub = {"filings": {"recent": {"form": ["8-K", "8-K", "10-Q", "8-K"], "filingDate": ["2024-02-01", "2024-03-01", "2024-05-01", "2024-05-02"],
                                  "items": ["2.02,9.01", "5.02", "", "7.01,2.02"]}}}
    assert h2.earnings_dates(sub) == ["2024-02-01", "2024-05-02"]


def test_window_uses_business_days_and_stays_in_the_year():
    w = h2.window_days(["2024-02-07"], 2024)                          # a Wednesday
    assert len(w) == 7 and np.datetime64("2024-02-02") in w and np.datetime64("2024-02-12") in w
    assert all(np.is_busday(d) for d in w)
    assert len(h2.window_days(["2024-01-02"], 2024)) == 5               # the days before 1 January belong to 2023


def _releases(ncomp=150, seed=0):
    rng = np.random.default_rng(seed)
    rel = {}
    for c in range(ncomp):
        days = []
        for y in range(2021, 2026):
            for q in (2, 5, 8, 11):
                days.append(str((pd.Timestamp(f"{y}-{q:02d}-01") + pd.Timedelta(days=int(rng.integers(0, 25)))).date()))
        rel[c] = days
    return rel


def _events(rel, n=900, share_near=0.0, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        c = int(rng.integers(0, len(rel)))
        if rng.random() < share_near:
            d = pd.Timestamp(rel[c][int(rng.integers(0, len(rel[c])))]) + pd.Timedelta(days=int(rng.integers(-2, 3)))
        else:
            d = pd.Timestamp("2021-01-01") + pd.Timedelta(days=int(rng.integers(0, 365 * 5)))
        rows.append({"cik": c, "date": d.normalize()})
    return pd.DataFrame(rows).drop_duplicates(["cik", "date"])


def test_e_finds_planted_clustering_and_not_random_timing():
    rel = _releases()
    t = h2.event_table(_events(rel, share_near=0.15), rel, start="2021-01-01", end="2025-12-31")
    r = h2.test_e(t, n_sim=2000, n_boot=200)
    assert r["p"] < 0.01 and r["predicted_sign"] and r["ci_lo"] > 1
    t0 = h2.event_table(_events(rel, share_near=0.0, seed=4), rel, start="2021-01-01", end="2025-12-31")
    r0 = h2.test_e(t0, n_sim=2000, n_boot=200)
    assert r0["p"] > 0.05 and 0.75 < r0["ratio"] < 1.3


def test_e_null_rate_is_near_five_percent():
    rel = _releases(ncomp=80, seed=2)
    rej = [h2.test_e(h2.event_table(_events(rel, n=300, seed=s), rel, start="2021-01-01", end="2025-12-31"), n_sim=1000, n_boot=20)["p"] < 0.05
           for s in range(60)]
    assert np.mean(rej) <= 0.12


def test_e_needs_three_releases_in_the_year_and_shift_moves_the_calendar():
    rel = {1: ["2024-02-07", "2024-05-08"]}                              # only two releases in 2024
    ann = pd.DataFrame({"cik": [1], "date": [pd.Timestamp("2024-02-07")]})
    assert h2.event_table(ann, rel).empty
    assert h2.shift_releases({1: ["2024-02-07"]}, 45) == {1: ["2024-03-23"]}


def test_weekend_announcement_moves_to_monday():
    rel = {1: ["2024-02-12", "2024-05-08", "2024-08-07", "2024-11-06"]}  # 12 Feb 2024 is a Monday
    ann = pd.DataFrame({"cik": [1], "date": [pd.Timestamp("2024-02-17")]})  # Saturday -> Monday 19 Feb, 5 business days after
    t = h2.event_table(ann, rel)
    assert t.loc[0, "date"] == pd.Timestamp("2024-02-19") and t.loc[0, "near"] == 0
    ann2 = pd.DataFrame({"cik": [1], "date": [pd.Timestamp("2024-02-10")]})  # Saturday -> Monday 12 Feb = release day
    assert h2.event_table(ann2, rel).loc[0, "near"] == 1
