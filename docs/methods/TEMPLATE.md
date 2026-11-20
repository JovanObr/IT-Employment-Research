# <Hypothesis id>: <one-line question>

> One dossier per hypothesis, in `docs/methods/<id>.md` (for example `docs/methods/C2.md`). Written by the hypothesis owner after the
> single real run. Goal: someone who has never seen the code can answer any question about how the result was produced, and
> can reproduce it. Every number below is copied from the results file, never retyped from memory.

## 1. Question and registration
- Question in one sentence, and the prediction (direction).
- Registration: file, section, commit hash and time (`git log -1 --format="%h %ad" -- <file>`).
- Amendments: each with date, what changed, why, and whether the primary estimate changed.
- What we already knew before registering (copy the disclosure).

## 2. Data
One row per dataset the test reads.

| Dataset | Provider | URL | Retrieved | File in the repo | SHA-256 (first 12) | Period used | Unit / level |
|---|---|---|---|---|---|---|---|

- Licence or terms (from `data/manifest.json`).
- How the file is (re)created: the exact command (`python collect.py --sources ...`), and any manual step (hand download, CONTACT_EMAIL).

## 3. From raw data to the test sample (every step, in order)
Numbered steps, each with: what is done, why, the function that does it (`module.function`, file and line), and the row count after it.
1. Load ... (n = ...)
2. Filter ... because ... (n = ...)
3. Define the variables: exact formula of the outcome and of the exposure / groups (e.g. `log(emp_2024 / emp_2023)`).
4. Rows dropped and why (missing, parsing errors, withheld data), with counts.
Final sample: n = ..., groups ..., period ....

## 4. The test
- Primary test: name, formula, one- or two-sided, alpha.
- Why this test and not the obvious alternatives (data shape, assumptions, what could distort the result).
- Assumptions and how they were checked (with the check's result).
- Secondary tests and what each one is for.
- Placebo: how it is built, number of repetitions, false-positive rate obtained.
- Power: minimum detectable effect, and how it was computed.
- Multiple testing: the family, and the Holm-adjusted p-value.

## 5. Code
- Where it lives: functions with file paths, the entry point, and the exact command that produces the results file.
- Synthetic tests that check it (`tests/...::test_...`) and what each proves (planted effect found, null not found, edge cases).
- Short code excerpt of the core computation (10-20 lines), copied from the file.

## 6. Results
| Quantity | Value |
|---|---|
| estimate (unit) | |
| 95 % interval | |
| p (raw) | |
| p (Holm) | |
| predicted sign? | |
| verdict | |
Placebo result, secondary results, and anything unexpected in the data.

## 7. How to read it, and its limits
- Two or three sentences in plain Slovenian, as they would appear in the presentation.
- Limits: what the test cannot show, measurement issues, alternative explanations.

## 8. Likely questions and answers
At least five, the kind a professor or a curious listener would ask ("why not a t-test?", "is the data normalised?", "what if ...").
