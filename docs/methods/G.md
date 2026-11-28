# G: Did ICT hiring in each EU country follow its own central bank, or one common shock? (round 3)

> Methods dossier (template `docs/methods/TEMPLATE.md`), written by Stream B after the single real run. Every number is copied from
> `reports/hypotheses3_b_results.json` (or from the registration for the synthetic calibration).

## 1. Question and registration
- **Question.** Chapter 2 says layoffs came "after dearer money". EU countries raised rates at different times (Czechia and Hungary in June
  2021, Poland and Romania in late 2021, the euro area in July 2022). Did a country's own rate rise go with a fall in its ICT job vacancy
  rate, beyond what all countries went through in the same quarter?
- **Prediction.** Yes, negative: b < 0.
- **Registration.** `docs/hypotheses/round3/G.md`, commit `849b2ea` (2026-11-28 13:56:22 +0100). The collector ran after it (13:56:35 the
  same day); the single real run followed. Amendments: none.
- **Changed before registration (on metadata and simulated data only).** The indicator code is `JVR` (the plan's "JOBRATE" does not exist);
  Bulgaria and Croatia take the euro-area rate for the whole window (their own 3-month series end in 2018-06 and 2019-12); Sweden turned
  out to follow the euro area closely, so four countries (CZ, HU, PL, RO) carry the variation, not five.
- **Known before registering.** Indeed peaks by country (US 02/2022, UK 04/2022, DE 05/2022, FR 07/2022) and the tracker's quarterly counts
  (Europe 4 -> 31 from 2022Q1 to 2022Q2, US 21 -> 174), both from `docs/hypotheses/round3/README.md`; the counts and flags of the vacancy
  table (never a value); the coverage of the rate table and how far each own rate departed from the euro area's in 2021-2023 (HU 6.23,
  PL 3.32, CZ 3.08, RO 2.85, SE 0.30, DK 0.17 points).

## 2. Data
| Dataset | Provider | URL | Retrieved | File in the repo | SHA-256 (first 12) | Period used | Unit / level |
|---|---|---|---|---|---|---|---|
| Job vacancy statistics `jvs_q_nace2` | Eurostat | https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/jvs_q_nace2 | 2026-11-28 | `data/raw/eurostat_jvs_q_nace2.csv` | `9acdd16370db` | 2018Q1-2024Q4 (2015Q1-2018Q4 for the noise scale) | country x quarter, job vacancy rate % (JVR, size class TOTAL, NSA) |
| Money market interest rates `irt_st_m` | Eurostat | https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/irt_st_m | 2026-11-28 | `data/raw/eurostat_irt_st_m.csv` | `3f4c8e78a322` | 2017Q3-2024Q3 (lags) | country x month, 3-month rate % (IRT_M3) |

- Licence: Eurostat, free reuse with attribution (`data/manifest.json`).
- Re-create: `python collect.py --sources eurostat_g` (`collectors/eurostat_g.py`, which calls the unchanged `collectors.eurostat.collect`
  with filters `JVR`, `TOTAL`, sections `J` and `B-S`, and `IRT_M3`). No manual step. Eurostat revises data: compare the hashes above first.

## 3. From raw data to the test sample
1. **Load** both CSVs as strings (`run` in `analysis/hypotheses3_b.py`, line 426): 8,851 vacancy rows, 5,273 rate rows.
2. **Vacancy rate** (`vacancy`, line 75): section J, NSA, size class TOTAL, the 27 EU countries; quarters x countries. Flags kept alongside.
3. **Outcome** y(c,t) = v(c,t) - v(c,t-4) (`build_panel`, line 99).
4. **Rate** (`quarterly_rates`, line 56): mean of the three monthly 3-month rates of a quarter (missing if a month is missing).
   `rate_paths` (line 65): own rate for CZ, DK, HU, PL, RO, SE; the euro-area series `EA` for the other 21 countries.
5. **Exposure** x(c,t) = r(c,t-1) - r(c,t-5) (`yoy_exposure`, line 70).
6. **Window** 2019Q1-2024Q4, rows with both values (`panel_from_wide`, line 89): **646 of 648**; the two missing rows are France 2020Q1
   and 2021Q1 (France has no 2020Q1 value). 27 countries, 24 quarters; every other country has all 24.

## 4. The test
- **Model.** OLS of y on x with country and quarter fixed effects (`TWFE`, line 117; Frisch-Waugh-Lovell through the annihilator of the
  dummies; `tests/test_hypotheses3_b.py::test_twfe_matches_dummy_regression` checks it equals the dummy regression).
- **Primary.** Restricted wild cluster bootstrap-t by country (null imposed, Rademacher weights, CR1 standard error, 9,999 replicates),
  two-sided, alpha 0.05 (`wild_cluster_p`, line 156).
- **Why not the ordinary cluster-robust p.** Only four countries carry the variation; on simulated panels with b = 0 the CR1 t-test rejected
  13-21 % of the time, the wild bootstrap 2.3-5.5 % with the real rate paths (registration, calibration table). The quarter effects absorb
  a common shock that moves with the rates (3.3 % false positives in that scenario).
- **Assumptions.** Countries are independent clusters; the exposure path of a country is not chosen in response to its ICT vacancies
  (partly violated: rates respond to the economy; the one-quarter lag reduces this); the year-on-year difference removes the seasonal
  pattern (NSA series).
- **Secondary.** Lags 0 and 2; without Slovenia (flag `u`); all industries (B-S, 26 countries); randomization inference on t; leave one
  own-rate country out; quoted descriptive facts. None can change the verdict.
- **Placebo.** Exposure paths reassigned among the 27 countries 1,000 times, the primary run on each (999 replicates): **3.9 %** with
  p < 0.05 (5 % expected).
- **Power (logged before b was estimated).** Noise scale from the two-way fixed-effect residuals of the outcome in 2015Q1-2018Q4 (median
  level-innovation sd 0.251, phi 0.7 assumed); smallest |b| found 80 % of the time: **0.16** points of vacancy rate per point of rate rise.
  At registration, in noise units: 0.61 per unit of innovation sd.
- **Multiple testing.** Round 3 family G, H; Holm (m = 2): H p = 0.0001 -> 0.0002; G p = 0.516 -> max(0.0002, 0.516) = **0.516**.

## 5. Code
- Entry points: `python collect.py --sources eurostat_g`, then `python -m analysis.hypotheses3_b` (refuses to run unless `G.md` is
  committed; about 50 minutes, mostly the power search and the placebo). Figure: `python -m analysis.web_figures_b` (`fig_countries`).
- Synthetic tests (`tests/test_hypotheses3_b.py`): quarterly mean needs 3 months and euro countries take EA; the lagged exposure; outcome,
  flags and panel on a hand-made file; TWFE = dummy regression; planted b = -1 found, null not found; a common shock moving with the rates is
  absorbed; CR1 over-rejects (documents why it is not the primary); reassignment keeps the set of paths; strong effect gives a small
  bootstrap p; the whole run on fake files laid out like the Eurostat CSVs.
- Core computation (`wild_cluster_p`):
```python
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
```

## 6. Results
| Quantity | Value |
|---|---|
| b (points of vacancy rate per point of rate rise, one quarter later) | **+0.024** |
| 95 % interval (CR1, 26 df) | -0.048 to +0.097 |
| p (raw, wild bootstrap) | 0.516 |
| p (Holm, round 3) | 0.516 |
| predicted sign? | no (positive) |
| verdict | **not supported** |
| CR1 p / randomization inference p | 0.496 / 0.580 |
| rows / countries / quarters | 646 / 27 / 24 |

Secondary (b, wild p): lag 0 +0.020 (0.487); lag 2 +0.016 (0.695); without Slovenia +0.024 (0.528); all industries B-S -0.007 (0.611),
so ICT minus all industries = +0.031; leave one out: without CZ -0.005 (0.876), without HU +0.029 (0.858), without PL +0.040 (0.319),
without RO +0.035 (0.359), without DK +0.021 (0.591), without SE +0.023 (0.538). No version is close to significance or consistently negative.

Descriptive (unweighted means, section J; exploratory, no test): the four early hikers' vacancy rate was 2.68 % (2019Q4), peaked at 3.55 %
in **2022Q1** and fell to 1.35 % (2024Q4); the 21 countries on the ECB rate: 2.53 %, peak 3.78 % in **2022Q1**, 2.58 %. Both groups turned
down in the same quarter although the early hikers had started raising rates about a year earlier. The early hikers then fell further,
but that fall continued in 2024 while their rates were being cut, so it does not follow the timing of their own rates (consistent with
b near zero); a regional Central-European cycle could explain it.

Quoted, not recomputed (exploratory): first hikes BoE 2021-12-16, Fed 2022-03-16, ECB 2022-07-21; Indeed software-postings peaks US 02/2022,
UK 04/2022, DE 05/2022, FR 07/2022; tracker announcements Europe 4 -> 31 and US 21 -> 174 from 2022Q1 to 2022Q2.

## 7. How to read it, and its limits
- *Če bi povpraševanje po IT kadrih sledilo domači centralni banki, bi v Češki, Madžarski, Poljski in Romuniji, ki so obresti dvignile
  leto pred ECB, padlo prej. Ni: prosta delovna mesta v IKT so povsod začela padati v začetku leta 2022. Povezave med domačo obrestno
  mero in prostimi delovnimi mesti v IKT ne moremo dokazati; podatki se bolj skladajo s skupnim, mednarodnim sunkom.*
- What the interval rules out: a fall of more than about 0.05 points of vacancy rate per point of rate rise. The design could find 0.16
  with 80 % power, so an effect of the size we expected is unlikely; a small one cannot be excluded.
- Limits: a vacancy rate is hiring demand, not employment; four countries carry the variation; the 3-month rate is a proxy for policy; rates
  respond to the economy (an overheated labour market pushes both up, which biases b towards positive); a Central-European regional cycle
  is not absorbed by quarter effects common to all 27; section J includes publishing and telecoms; the 2015-2018 noise scale is calmer than
  2019-2024 (COVID), so the power is optimistic. Not supported is not proof of no effect.

## 8. Likely questions and answers
- **So interest rates did not matter?** This test cannot say that. It asks whether a country's **own** rate mattered beyond the common
  shock. The global rise in rates (Fed, ECB) is in the quarter effects, together with everything else that hit all countries at once.
- **Why vacancies and not layoffs or postings?** The tracker and Indeed data had already been looked at for this question (they suggested
  it); a fair test needs data that did not. Vacancy statistics are official, cover all 27 countries quarterly and had not been seen.
- **Why the wild bootstrap and not ordinary standard errors?** With four countries carrying the variation, the usual cluster-robust test
  found an effect that was not there 13-21 % of the time on simulated data; the wild bootstrap stayed near 5 %, checked before registration.
- **Is Hungary driving it?** Leaving out any one of the six own-rate countries does not change the conclusion (b between -0.005 and
  +0.040, all p > 0.3).
- **Why did the early hikers' vacancies fall more after 2022?** We do not know; the fall kept going while their rates were cut in 2024,
  which does not fit a rate story. A shared Central-European slowdown is one possibility; it is not tested.
- **Why are Bulgaria and Croatia on the ECB rate?** Their own 3-month rates are not published in the window, and both currencies were pegged
  to the euro, so their money-market rates had no independent path.

## Facts for the website (chapter 2 screen; Stream A writes it from these)
- Češka in Madžarska sta obresti prvič dvignili junija 2021, Poljska in Romunija konec leta 2021, ECB šele julija 2022.
- Kljub temu so prosta delovna mesta v IKT v obeh skupinah dosegla vrh v istem četrtletju, v začetku leta 2022 (zgodnje države 3,6 %,
  države z obrestno mero ECB 3,8 %).
- Hipoteza G ni potrjena: povezave med dvigom domače obrestne mere in padcem prostih delovnih mest v IKT ne najdemo (p = 0,52; ocena je
  celo malo pozitivna, +0,02 točke na točko obresti).
- To ne pomeni, da obresti niso pomembne: test meri le domačo centralno banko poleg skupnega sunka, ki je zadel vse države hkrati
  (Fed, ECB, svetovni tehnološki cikel).
- Zgodnje države so do konca 2024 padle globlje (na 1,4 % proti 2,6 %), a padale so tudi, ko so obresti že zniževale.
- Graf: `2w_drzave` (modro zgodnje države, oranžno države z obrestno mero ECB; navpični črti: prve podražitve).
