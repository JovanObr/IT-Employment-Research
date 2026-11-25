"""Round 3, hypothesis H: synthetic tests (run before the real data exist) and the PC-Axis parser."""
import numpy as np
import pandas as pd

from analysis import hypotheses3_a as h
from collectors import surs

PX = '''CHARSET="ANSI";
CODEPAGE="windows-1250";
LANGUAGE="sl";
MATRIX="TEST";
STUB="SKD DEJAVNOST","DELOVNO AKTIVNO PREBIVALSTVO";
HEADING="MESEC";
VALUES("SKD DEJAVNOST")="SKD dejavnost - SKUPAJ","J62 Računalniško programiranje; svetovanje";
VALUES("DELOVNO AKTIVNO PREBIVALSTVO")="1 Delovno aktivno prebivalstvo - SKUPAJ","11 Zaposlene osebe - skupaj";
VALUES("MESEC")="2021M01","2021M02",
"2021M03";
TITLE[en]="ignored";
DATA=
100 101 102
90 91 "."
5 6 7
4 5 6;
'''.encode("windows-1250")


def test_px_parser_reads_order_quotes_and_missing():
    df = surs.tidy(surs.parse_px(PX))
    assert len(df) == 12
    row = df[(df["activity"].str.startswith("J62")) & (df["status"].str.startswith("11")) & (df["month"] == "2021-03-01")]
    assert row["value"].item() == 6
    assert df["value"].isna().sum() == 1
    assert df["activity"].str.contains("Računalniško programiranje; svetovanje").any()     # encoding and ; inside quotes


def _register(shift: float, seed: int = 0) -> pd.DataFrame:
    """A fake 0700921S: total 900k, J62 30k + J63 6k with noise; `shift` points added to the share in 2023."""
    rng = np.random.default_rng(seed)
    months = pd.date_range("2015-01-01", "2025-12-01", freq="MS")
    tot = 900_000 + np.arange(len(months)) * 300
    share = 4.0 + 0.02 * np.arange(len(months)) / 12 + rng.normal(0, 0.03, len(months))
    share = share + np.where(months.year == 2023, shift, 0) + np.where(months.year == 2021, 0, 0)
    it = share / 100 * tot
    rows = []
    for st in (h.ALL_PERSONS, h.EMPLOYEES):
        rows += [{"activity": h.TOTAL, "status": st, "month": m, "value": t} for m, t in zip(months, tot)]
        rows += [{"activity": "J62 Računalniško programiranje", "status": st, "month": m, "value": 0.85 * v} for m, v in zip(months, it)]
        rows += [{"activity": "J63 Druge informacijske dejavnosti", "status": st, "month": m, "value": 0.15 * v} for m, v in zip(months, it)]
    return pd.DataFrame(rows)


def test_share_series_adds_both_divisions():
    s = h.share_series(_register(0.0))
    assert abs(s["s"].iloc[0] - 100 * s["it"].iloc[0] / s["total"].iloc[0]) < 1e-12
    assert 3.9 < s["s"].iloc[0] < 4.1


def _primary(shift):
    s = h.share_series(_register(shift))["s"]
    n = h.ar1_noise(s)
    return h.sim_test(s, n["phi"], n["sd"], n_sim=4000)


def test_planted_shift_is_found():
    r = _primary(0.5)
    assert r["d"] > 0.4 and r["p"] < 0.001 and r["ci_lo"] > 0


def test_negative_shift_has_negative_sign():
    r = _primary(-0.5)
    assert r["d"] < -0.4 and r["p"] < 0.001


def test_primary_false_positive_rate_near_5_percent():
    ps = h.simulate(phi=0.6, sd=0.03, shift=0.0, n_sim=1000, seed=3)
    assert 0.03 <= (ps < 0.05).mean() <= 0.08


def test_newey_west_over_rejects_with_24_months():
    """Why Newey-West is not the primary: on the same null it rejects far more often than 5 %."""
    ps = h.simulate(phi=0.6, sd=0.03, shift=0.0, n_sim=600, seed=3, test="nw")
    assert (ps < 0.05).mean() > 0.15


def test_block_placebo_near_5_percent_when_noise_is_ar1():
    rng = np.random.default_rng(9)
    e = np.zeros(132)
    for k in range(1, 132):
        e[k] = 0.6 * e[k - 1] + rng.normal(0, 0.03)
    s = pd.Series(4 + e, index=pd.date_range("2015-01-01", periods=132, freq="MS"))
    n = h.ar1_noise(s)
    share = h.block_placebo(s, n["phi"], n["sd"], n_rep=600)
    assert share <= 0.15


def test_ar1_noise_recovers_phi():
    rng = np.random.default_rng(5)
    e = np.zeros(600)
    for k in range(1, 600):
        e[k] = 0.7 * e[k - 1] + rng.normal(0, 0.1)
    s = pd.Series(e + 0.001 * np.arange(600), index=pd.date_range("2015-01-01", periods=600, freq="MS"))
    r = h.ar1_noise(s, "2015-01-01", "2064-12-01")
    assert abs(r["phi"] - 0.7) < 0.1 and abs(r["sd"] - 0.1) < 0.02


def test_power_is_finite_and_sensible():
    m = h.power(phi=0.6, sd=0.03, n_sim=200)
    assert 0 < m < 0.5


def test_trend_gap_finds_a_slowdown():
    df = _register(0.0)
    s = h.share_series(df)["s"].copy()
    s[(s.index >= "2022-01-01") & (s.index <= "2023-12-01")] -= 0.3
    r = h.trend_gap(s)
    assert r["mean_deviation"] < -0.2 and r["p"] < 0.01
