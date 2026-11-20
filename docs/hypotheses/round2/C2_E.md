# Round 2 pre-registration, Stream A: hypotheses C2 and E

Written 2026-11-20, **before the outcome data of C2 were collected and before any test of E was run**. Commit this file first; the commit is
the registration. Common rules: `docs/hypotheses/round2/README.md` (and round 1, "Common rules"). Family: A2, F, C2, E (one Holm correction).

## Design checks done before registration (counts only)
- E: 905 tracker announcements (unique company and date) from 350 companies matched to SEC filers; for all 350 the cached SEC submissions
  list their 8-K filings; 9,229 of them carry item 2.02 ("Results of Operations and Financial Condition", the earnings release);
  331 companies have at least 4.
- C2: 492 tech companies have a 10-K headcount for end-2023; 48 of them have a tracker announcement in 2024. One year alone gives low power
  (minimum detectable shift about 9 %, against the 7 % seen in the exploratory finding), so C2 pools 2024 and 2025. No 2024 or 2025
  headcount had been collected at registration.

## Disclosure
- C2 is suggested by round 1's exploratory result (headcount change 2022 -> 2023: announcers -7 % vs. non-announcers, p < 0.001).
  That result used 2022-2023 data; **C2 uses only 2023-2025 headcounts and 2024-2025 announcements**, which did not suggest it.
- E: no earnings dates had been looked at against announcement dates before registration.

---

## C2. Announced layoffs show up in the same year's headcount (replication on new years)
**Hypothesis.** Among US tech companies, those that announce a layoff in year t have a larger fall in employees from end of t-1 to end of t
than those that do not, for t = 2024 and 2025 pooled.
- **Data.** 10-K headcounts (`collectors/sec_headcount.py`, rules as of this commit, including `recheck`), period years 2023, 2024, 2025:
  `python collect.py --sources sec_headcount_2425` (new source name, same code, years 2024 and 2025; 2023 is already collected).
  Tracker: `layoffs_clean.csv` + `sec_company_matches.csv`. Universe: `sec_universe_sic.csv`, `is_tech`.
- **Unit.** Company-year (t = 2024, 2025) with a headcount for both t-1 and t; |log change| > ln 10 dropped as a parsing error (as in round 1).
- **Exposure.** At least one tracker announcement dated in calendar year t by a company matched to the CIK.
- **Outcome.** log(employees_t / employees_{t-1}).
- **Primary test.** Difference in medians, announced - not announced, pooled over both years; two-sided permutation test that shuffles the
  announced label **within each year** (10,000 permutations; the group sizes per year stay fixed). Predicted: negative.
- **Effect and interval.** The same difference with a 95 % bootstrap interval resampling companies (all of a company's years together), 5,000 times.
- **Why this test.** Headcount changes have heavy tails (acquisitions, occasional parsing errors), so medians and a permutation test, not means
  and a t-test; shuffling within year keeps the comparison inside each year, so a difference between 2024 and 2025 cannot create an effect.
- **Secondary.** Each year alone (same test); Mann-Whitney on the pooled sample; OLS with log assets (latest panel value in t-1) and SIC 3-digit
  dummies, errors clustered by company.
- **Placebo.** Shuffle announcements across companies within year 1,000 times; share of shuffles with p < 0.05 (expected about 5 %).
- **Power.** Reported from the counts once the data are collected and before the comparison is made (pooled spread of the outcome, group sizes),
  as the minimum detectable difference at 80 % power.
- **Limits.** Headcount is one day a year and read from text; announcements can concern staff abroad; acquisitions change headcount; a company
  can cut and hire in the same year.

## E. Layoff announcements cluster around quarterly earnings releases
**Hypothesis.** Tracker layoff announcements fall within three business days of the same company's earnings release more often than they
would if their timing were unrelated to earnings releases.
- **Data.** Tracker announcements of companies matched to an SEC filer (`layoffs_clean.csv`, `sec_company_matches.csv`); earnings releases = filing
  dates of the company's 8-K filings that list item 2.02, from the cached SEC submissions (`data/cache`, the same reply `collectors/sec.py` uses;
  the code reads them with `collectors.common.fetch`, so a missing cache entry is downloaded with CONTACT_EMAIL).
- **Unit.** One announcement per company and date, 2020-03-11 (start of the tracker) to 2026-06-30, kept only if the company has at least
  3 earnings releases in that calendar year (so the company's release calendar is known that year). Weekend dates move to the next Monday.
- **Window.** The announcement is "near" a release if it is within 3 business days before or after it (a 7-business-day window around each release).
- **Expected under no relation.** For each announcement, p_i = share of the year's business days (Mon-Fri) that lie in that company's windows that year.
  E = sum of p_i.
- **Primary test.** Observed count O of announcements near a release vs. the null distribution of the count when every announcement is moved to
  a random business day of its own year (same company, same windows), 10,000 simulations; two-sided p = 2 x min(P(S >= O), P(S <= O)), capped
  at 1. Predicted: O > E.
- **Effect and interval.** O / E with a 95 % bootstrap interval resampling companies (5,000 times).
- **Why this test.** It compares each announcement with the calendar of its own company and year, so companies with many or few releases, and
  years with different numbers of announcements, are each held to their own expected rate; the simulation makes no distributional assumption.
- **Secondary.** Only after the release (days 0..+3) vs. only before (-3..-1); windows of 1 and 5 business days; 2022-2023 only (the main wave).
- **Placebo.** The same test with every release date shifted by +45 calendar days (moved to a business day), i.e. halfway between real releases;
  repeated with shifts of -45, +30, -30 days; each should find no clustering. Reported with the result.
- **Power.** About 4 releases a year make windows cover roughly 8 % of business days; with about 700 usable announcements the expected count is
  about 55, and an excess of about 20 announcements (O / E about 1.35) is detectable at 80 % power. The exact figure is reported from the
  usable sample before the comparison is made.
- **Limits.** The tracker date is the date of the news report, which can lag the company's own statement by a day or two (the window covers this);
  8-K item 2.02 marks the release of results, not the earnings call itself; clustering would show timing, not why companies choose it.

## Amendments
(none)
