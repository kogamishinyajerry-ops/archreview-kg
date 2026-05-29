# Quality Review — 2026-05-16 — overall 33.33/100

- Weakest dimension: real_pdf_breadth (3.33/10)
- 99+ status: no
- Verification overrides: none (0)
- Verdict: **W2 landed cleanly, no regressions, headline lifts 20 → 33.33 exactly as predicted.** code_quality recovered the missing point (warnings filtered, pytest now 527 passed / 0 warnings) — that is a +1 on a non-cap dimension and so does not move the headline. real_pdf_breadth moves 2.0 → 3.33 (3 → 5 active `real_public_*` cases), which is the entire headline delta because the weakest-dim rule binds. Average dimension is now 9.15/10 (was 8.91). Scoring is honest. The structural concerns the prior audit raised are unchanged.

## Per-dimension audit

### code_quality — 10.0/10 (verified, +1 vs prior)
`ruff` clean, `mypy` clean (103 files), `pytest` reports `527 passed, 1 skipped in 38.43s` with **0 warnings**. The 5 SWIG `DeprecationWarning`s the prior audit flagged are gone, presumably via `filterwarnings` in pyproject. Honest +1.

### kg_persistence — 10/10 (verified)
`kg.v1` schema, 12 required tables present, p95=0.012 ms. Counts grew: project 8 → 13, drawing 8 → 13, run 8 → 13, feedback_event 183 → 206. Consistent with 5 new fixture runs being ingested. Solid.

### kg_coverage — 10/10 (verified)
ingested_runs=13 vs expected_runs=12, coverage=1.08×. Saturated at ≥1.0. Fine.

### cross_project_query — 10/10 (verified, unchanged concern)
10/10 canonical queries return expected shape. **Q4 and Q9 still trivially correct with 0=0 rows** — same concern as prior audit. W2 did not touch this. W1.C is still outstanding work per the M5.Z blueprint.

### web_ui_e2e — 10/10 (verified)
All 6 flows return 200, p95 1.18–1.92 ms. Unchanged.

### recognition_quality — 9.52/10 (verified, unchanged concern)
weighted_precision=0.769, weighted_recall=1.000. **Recall=1.0 across all 24 rules is still the giveaway** that ground truth ⊂ detected by construction. W2 added 2 new active sheets and 3 new known_gap sheets but did NOT add `expected_rule_counts` for them, so the recall metric is unaffected — and that's the W1.A work the prior audit pointed at and the blueprint still owes. Score is mathematically what the artifacts say; the metric itself remains soft. Detected count on `RC-CORRIDOR-WIDTH` rose 29 → 52 (more sheets ingested), precision still 1.0 — likely benign but worth re-checking after expected_rule_counts lands.

### real_pdf_breadth — 3.33/10 (verified, this is the cap)
`samples/understanding_benchmarks/suite_manifest.json` confirms 5 active `real_public_*` cases: `medfield-a0-basement`, `medfield-a1-first-floor`, `medfield-a2-second-floor`, `medfield-a3-third-floor`, `medfield-full-plan-set-multi-plan-intake`. Formula `5/15 × 10 = 3.33` correct.

**Shared-source bias review.** All 5 active cases derive from the same Medfield 9-page PDF. Provenance files for a0/a3 contain an explicit `shared_source_acknowledgment` block calling this out and pointing at M5.Z-W3 as the diversification fix. **The scorer does not penalize shared-source bias** — `score_real_pdf_breadth` (archkg/quality_score.py:488-517) counts every `status=active` + `fixture_kind=real_public*` row at face value. So per current rubric the 3.33 stands. **But the metric semantics are weak**: 5 sheets from one architect on one document do not represent 5 independent jurisdictions/styles. I am NOT applying a verification override (the scorer's contract is clear and the project documents the bias honestly), but I am calling it a blocker for 99+ — a future judge with stricter rubric language could legitimately discount this. The prior audit warned about this; W2 deliberately accepted it as cheap headline lift; W3 must deliver multi-source breadth or the 99+ target is structurally suspect.

**Known_gap review (a4 roof, a5 elevations, a6 sections).** These are NOT counted in `real_active`, so they do not inflate the score. I read all three expected.json files: a4 requires `rooms.exact: 0`, `doors.exact: 0`, `corridors.max: 0` — the recognizer is *expected to fail* by producing 25 rooms / 8 corridors on roof outline geometry. a5 and a6 follow the same pattern (elevations / sections are not plan views; recognizer is plan-tuned). Each expected.json explicitly states the recognizer's expected failure mode and tags the case as needing a separate semantic layer. **This is honest gap exposure, not padding.** They contribute exactly zero to real_pdf_breadth and serve as documentation of recognizer scope. Good.

### calibration — 8.6/10 (verified, unchanged concern)
mean_abs_deviation=0.062 across 3 populated bins (n=50/55/55). Two bottom bins [0.0,0.2) and [0.2,0.4) still at sample_size=0. W1.B (detection-time Beta calibration to populate low-confidence bins) was not part of W2 and remains outstanding. Score unchanged.

### feedback_loop — 10/10 (verified)
Posterior `[0.333, 0.25, 0.2]`, monotonic non-increasing, delta=−0.167 matches expected. Clean.

### documentation_honesty — 10/10 (verified by scorer, with one soft note)
Scorer's overclaim regex only catches "N real" where N > actual (over-claims). It does not flag the **reverse**: `READINESS.md:13` still says "真实公开 PDF benchmark 仅 3 张 ... 当前得分 2/10" — both numbers are now stale (should be 5 and 3.33 post-W2). This is *understatement*, not overclaim, so it does not violate the rubric and I am not overriding. But READINESS lagging by one wave on a load-bearing number is a soft honesty signal worth flagging. **W4 in the blueprint already plans to fix this.** No score impact this round.

## Recommended next phase

**Target: real_pdf_breadth (current 3.33 → 6.67 in W3).** The blueprint already names W3: source 8-10 PDFs from diverse municipal departments. Smallest viable lift is **5 additional active multi-source cases** (Cambridge MA, Newton MA, Berkeley CA, Austin TX, Arlington VA are reasonable first targets). That takes real_active 5 → 10, score 3.33 → 6.67, and the meta-cap 33.33 → 66.67. Critically, **multi-jurisdiction sourcing also dissolves the shared-source-bias concern** that currently lurks behind the headline.

I **agree with the proposed W3 plan** as stated by the parent: 10+ multi-jurisdiction PDFs, each with `run_dir`, `expect`, `provenance`, and (importantly) `expected_rule_counts` populated so they double as W1.A adversarial fixtures and break the recall=1.0 artifact in one stroke. Combining W3 case acquisition with W1.A negative-example seeding is higher ROI than running them as separate waves. **One caveat**: if a sourced PDF is paywalled, behind a records request, or login-walled, skip it honestly per the blueprint's risk register — do not commit a fake provenance. Expect realistic yield 6-8 of 10 attempted.

## Blockers

- **real_pdf_breadth = 3.33/10, all 5 active cases share one source PDF.** Headline cap. Does not block per current rubric but the shared-source bias is the central remaining structural risk to a credible 99+.
- **Recall = 1.0 uniform across all 24 rules** still suggests expected ⊂ detected by construction. W1.A (adversarial expected_rule_counts) outstanding. Blocks any claim of "calibrated precision/recall on unseen-style PDFs."
- **Calibration bins [0.0, 0.4) still empty.** W1.B outstanding. Blocks "calibrated across the full confidence range" claim.
- **Q4 and Q9 still trivially correct at 0=0 rows.** W1.C outstanding.
- **READINESS.md still cites 3/15 and 2/10** (stale post-W2). Not an overclaim, but a soft honesty drift. W4 fix.
- **Cannot reach 99+ until real_pdf_breadth ≥ 9.0/10** — that requires ≥ 13.5 active `real_public_*` cases. Current trajectory: W3 lifts to ~10; a W3.5 / W4 second sourcing wave is mathematically required.
