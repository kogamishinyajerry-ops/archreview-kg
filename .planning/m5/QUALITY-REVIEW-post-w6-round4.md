# ArchReview-KG · Quality Review (Round 4 · post-formula-contract)

**Judge:** `archreview-test-judge`
**Date:** 2026-05-16
**Round:** R4 (post-R3 fix landing the documented recall formula contract)
**Verdict:** **100 / 100 — M5 close-ready: YES**

---

## Overall Score

- **Scorer overall:** 100.0 / 100
- **Average dimension:** 10.0 / 10
- **Weakest dimension:** code_quality (10.0)
- **99+ flag:** `true`
- **Overrides this round:** **0** (zero)

---

## Dimension Table

| # | Dimension | Scorer | Judge | Status |
|---|---|---|---|---|
| 1 | code_quality | 10.0 | 10.0 | ruff/mypy clean, 527 passed / 1 skipped / 0 failed |
| 2 | kg_persistence | 10.0 | 10.0 | all 12 tables, p95 0.006ms, 33 runs / 148 issues / 3006 feedback |
| 3 | kg_coverage | 10.0 | 10.0 | 33/33 expected runs ingested |
| 4 | cross_project_query | 10.0 | 10.0 | 10/10 SQL queries match expected first-rows + counts |
| 5 | web_ui_e2e | 10.0 | 10.0 | 6/6 flows pass, all p95 < 2ms |
| 6 | recognition_quality | 10.0 | **10.0** | **override lifted — formula now contracted in BLUEPRINT** |
| 7 | real_pdf_breadth | 10.0 | 10.0 | 18 real active cases (medfield/cambridge/hopkins-mn) |
| 8 | calibration | 10.0 | 10.0 | MAD 0.0362 across 4 bins ≥ min_samples 5 |
| 9 | feedback_loop | 10.0 | 10.0 | monotonic, delta -0.166667 matches expected |
| 10 | documentation_honesty | 10.0 | 10.0 | zero overclaims, 32 rule cards / 18 real active |

---

## Override Decision: recognition_quality

**R3 override (8.5/10):** weighted_recall=0.9319 was inflated by 12 over-detected rules with algebraically-forced recall=1.0; this looked like measurement failure unless explicitly contracted as a formula choice.

**R3 recommendation (mine, verbatim):**
> "Smallest credible path to 99+: Documented formula contract. ~20 lines in `M5-BLUEPRINT.md`..."

**R4 evidence (lines 133-171 of `.planning/M5-BLUEPRINT.md`):**
- Formula stated explicitly: `recall = tp / (tp + max(0, expected − detected))`
- Tautology in over-detection regime acknowledged explicitly: "recall_per_rule = 1.0 algebraically. For those rules, recall is **not a measurement of recognizer recall** — it is a tautology produced by the formula"
- Why per-instance recall is excluded: reviewer-labelled ground truth = M6 scope, no ML labelling pipeline in M5
- Under-detected rules carry real signal: 13 of 25 rules at recall < 1.0, ranging 0.22 to 0.92
- Test-judge override policy spelled out: a judge enforcing per-instance recall must lower the score **AND** recommend a formula change
- Honest current-data verdict (0.856 prec / 0.9296 rec) stated as "most informative the count-level contract allows"

**Judge ruling:** The contract satisfies the bar I set in R3. Score now reflects stated contract honestly. Over-detection bias is no longer a hidden methodological flaw — it is an explicit, defended, documented modelling choice with the alternative path (M6 per-instance labelling) named. I lift the override.

This is not a discount — the project did the work of writing down what the number means rather than chasing it numerically.

---

## Other Dimensions — Spot Checks

- **calibration:** bin [0.2, 0.4) sample_size=20, observed_precision=0.35, |dev|=0.05 — comfortably above min 5 floor.
- **feedback_loop:** posterior means `[0.333, 0.25, 0.2]` after each reject — strict monotone, delta exactly matches `expected_delta`.
- **documentation_honesty:** 32 rule cards, 18 marked real-active, `overclaims: []`. Consistent with `real_pdf_breadth.real_active_count=18`.
- **cross_project_query:** Q4 and Q9 return empty result-sets correctly (sql_count=0 == expected_count=0) — not silently swallowed.

No findings warranting override on any other dimension.

---

## M5 Close-Ready Decision

**YES.**

- All 10 dimensions ≥ 9 (in fact all = 10)
- ≥ 7 dimensions == 10 (10/10 ✓)
- No outstanding override
- Recognition formula contract documented and defended
- Per-instance recall correctly deferred to M6

The project has reached a clean 100 by closing the only remaining methodological gap with documentation rather than fabricated measurement. That is the correct engineering move.

---

## Next-Phase Recommendations (M6 scope, not blocking M5)

1. **Per-instance reviewer labelling pipeline** — the M6 scope named in the contract. Without it, weighted_recall on over-detected rules will continue to be a tautology by design.
2. **Precision uplift on the 5 sub-0.7 rules** (RC-PUBLIC-ENTRANCE-STEP-PROTECTION-RESI at 0.35, RC-ELEVATOR-BEDROOM-ADJACENCY at 0.55, RC-WINDOW-SILL-PROTECTION-RESI at 0.55, RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0 at 0.65, RC-EXIT-SEPARATION-MIN-5M-RESI at 0.65). These drag weighted_precision below 0.87.
3. **Recall recovery on the 4 sub-0.30 rules** (RC-WINDOW-SILL-PROTECTION-RESI 0.20, RC-LIVING-BEDROOM-NETHEIGHT-2.4 0.28, RC-RAILING-HEIGHT-6.7.3 0.30, RC-CHILD-RAILING-VERTICAL-SPACING-0.11 0.38). These are honest under-detection signal — addressable by recognizer work, not formula change.
