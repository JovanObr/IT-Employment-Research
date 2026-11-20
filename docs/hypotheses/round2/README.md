# Round 2 of pre-registered hypotheses (milestone 4, due 2026-12-02)

Same rules as round 1 (`docs/hypotheses/PREREGISTRATION.md`, section "Common rules"), with these specifics:

- **Family:** A2, F (Stream B, registration `A2_F.md`) and C2, E (Stream A, registration `C2_E.md`). One Holm correction across the four.
  Round 1 is a separate, closed family; its verdicts do not change.
- **Each owner registers their own two in their own file and commits it before running anything on real data.** The commit is the
  registration. Design checks that only count rows (sample sizes, data availability, power from design facts) are allowed before it
  and are listed in the registration.
- **Disclosure matters more this round:** some of these questions come from results we have already seen (A2 from round 1's A,
  C2 from round 1's exploratory 2022 -> 2023 finding). Say exactly what was seen. A hypothesis suggested by data can only be confirmed
  on data that did not suggest it (C2 uses new 2024 headcounts for that reason).
- **Every test has:** one primary test (two-sided p), the predicted sign, a placebo, synthetic tests (planted effect found, null not
  found), a power statement, and a methods dossier from `docs/methods/TEMPLATE.md` after the run.
- **Verdict rule:** supported only if Holm-adjusted p < 0.05 and the predicted sign. Notebook 11 (`notebooks/11_hipoteze2_SL.ipynb`,
  Stream A) shows all four.
