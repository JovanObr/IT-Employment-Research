# Milestone 3 (due Thursday 2026-11-19): test two pre-registered hypotheses (Stream B agent): A (Slovenia, ICT specialists) and B (San Francisco vs. Austin)

## Context
Milestone 3 tests four narrow hypotheses with statistical tests. They are **pre-registered** in `docs/hypotheses/PREREGISTRATION.md`:
hypotheses, samples, the one primary test each, thresholds and decision rules were written and committed before any test was run.
Stream A does C (announced layoffs vs. 10-K headcount) and D (repeat announcements and the stock price) in `analysis/hypotheses.py`.
**You do A and B exactly as registered.** Stream A then combines the four primary p-values with the Holm correction
(`analysis.hypotheses.holm`) and writes the results notebook.

## The one rule that matters most
**Do not look at the outcome before the code is finished and tested.** Concretely: do not plot or print Slovenia's ICT share against other
countries, or the San Francisco and Austin quarterly series, until `tests/test_hypotheses_b.py` passes on synthetic data. Then run the real
analysis **once**. If you find a bug after that, fix it, add a dated amendment at the end of the registration saying what changed and why,
and rerun; never change a test, sample or threshold because of the result. Checking that the data exist (columns, codes, years) is fine.

## Rules (as before)
- Branch `milestone3/hypotheses-b`. Pull `main` first; read `AGENTS.md`, `docs/STATUS.md`, `docs/hypotheses/PREREGISTRATION.md` (sections
  Common rules, A, B), `analysis/hypotheses.py` (for the style and for `holm`, `file_hashes`, `mde`).
- **Files you own:** `analysis/hypotheses_b.py` (new), `tests/test_hypotheses_b.py` (new), your section of `docs/STATUS.md`, and amendments
  to the registration (append only). Do not edit Stream A's files; requests go under *Requests between streams* in `docs/STATUS.md`.
- Tests: synthetic data only, no network. `pytest -q` and `python -m compileall -q .` green before you push. Never commit `data/raw/`.

## Deliverables
### H1 `analysis/hypotheses_b.py`
- `test_a(eurostat: DataFrame, country="SI", years=(2021, 2024)) -> dict` with at least: `x_si`, `mean_others`, `sd_others`, `t`, `p` (two-sided,
  Student t with 25 df, as registered), `predicted_sign` (t > 0), `rank` (1 = largest change), `n_countries`, `values` (change per country).
  EU-27 list hard-coded; unit `PC_EMP`; Greece is `EL`. Raise a clear error if any of the 27 lacks either year.
- `secondary_a(...)`: rank p (rank / 27); the same for 2019 -> 2024 with a `crosses_break` warning; relative change in %; Slovenia vs. `EU27_2020`;
  Shapiro-Wilk p for the 26 other changes (if < 0.05, flag the primary p as approximate).
- `placebo_a(...)`: the primary test for each of the other 26 countries against the rest; share with p < 0.05.
- `quarterly_series(qcew, cbsa) -> Series`: NAICS 5415, private ownership, mean of the three monthly employment levels per quarter, indexed by
  quarter. Map CBSA 41860 (San Francisco-Oakland) and 12420 (Austin-Round Rock) to QCEW area codes (`C4186`, `C1242`; check them, and apply
  `config/qcew_code_crosswalk.csv` if a code changed in 2023). Disclosed quarters (`disclosure_code` set) are missing, never zero.
- `test_b(sf: Series, austin: Series, post_start="2022Q2") -> dict`: d_t = log(SF) - log(Austin); pre-trend check on 2019Q1-2022Q1 (linear
  trend, OLS, p for the slope); primary regression d_t = a + b * post (+ trend if the pre-trend p < 0.05, as registered), **Newey-West
  standard errors with 4 lags** (write it with numpy, or use `statsmodels` if you add it to `requirements.txt`; test it against a known case).
  Return `b`, `se`, `ci_lo`, `ci_hi`, `p` (two-sided), `predicted_sign` (b < 0), `trend_added`, `pretrend_p`, `n_pre`, `n_post`.
- `placebo_b(qcew)`: the same b for every pair among the 30 metros with the most NAICS 5415 jobs in 2019 and complete series; return the
  distribution, SF-Austin's rank, and the share of pairs with |b| at least as large.
- `secondary_b(...)`: without 2020Q1; establishments instead of employment.
- `run()` -> dict with `inputs_sha256` (`hypotheses.file_hashes`), `A` and `B` (primary, secondary, placebo); `main()` writes
  `reports/hypotheses_b_results.json` (`python -m analysis.hypotheses_b`).

### H2 Tests (`tests/test_hypotheses_b.py`, synthetic only)
- A: a planted outlier country is found (p < 0.01, positive t) and a country drawn from the same distribution is not; rank and placebo behave;
  a missing country raises.
- B: a planted post-hike drop (e.g. -0.10 log points) is found with the right sign; a pure random walk without a break gives p > 0.05 in most
  seeds (check the false-positive rate over about 200 simulated series is near 5 %, which also checks your Newey-West code); the trend is added
  exactly when the pre-trend test says so; disclosed quarters stay missing.
- Each test function's output has the keys above; `p` is in (0, 1].

### H3 Run once and report
After H2 is green, run `python -m analysis.hypotheses_b` on the real data once. In your STATUS line write: the primary estimate, its interval and
p for A and B; whether the pre-trend check added a trend; the placebo results; anything unexpected in the data (estimated values, disclosed
quarters). **Do not write a conclusion** ("supported" or not): that needs the Holm correction across all four tests, which Stream A does.

## Schedule (milestone due Thursday 2026-11-19)
| When | What |
|---|---|
| Sun 15 Nov | H1 for A (`test_a`, `secondary_a`, `placebo_a`) and its tests; push the branch |
| Mon 16 Nov | H1 for B (`quarterly_series`, `test_b` with Newey-West checked, `placebo_b`, `secondary_b`) and its tests; push |
| Tue 17 Nov, noon | H3: one real run, STATUS line with estimates, intervals, p-values; **open the pull request** |
| Wed 18 Nov | Review fixes only; Stream A combines all four tests (Holm) and finishes the results notebook |
| Thu 19 Nov | Milestone |

## Prompt to paste into the agent
"You are the Stream B agent on this repository. Read AGENTS.md, docs/STATUS.md, docs/hypotheses/PREREGISTRATION.md (Common rules, A, B),
analysis/hypotheses.py and docs/tasks/MILESTONE_3.md. Work on branch milestone3/hypotheses-b. Implement A and B exactly as registered; do not
look at the outcome data (Slovenia's ICT share vs. other countries, the San Francisco and Austin quarterly series) until the synthetic tests
pass; then run the real analysis once. Open the pull request on Tuesday 17 November at noon. Never change a registered test, sample or threshold because of a result; a bug fix goes in a dated
amendment at the end of the registration. Do not edit Stream A's files. Report estimates, intervals and p-values in STATUS but no conclusion."
