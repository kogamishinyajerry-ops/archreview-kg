# Quality Review — 2026-05-16 — overall 20/100

- Weakest dimension: real_pdf_breadth (2.0/10)
- 99+ status: no
- Verification overrides: none (0)
- Verdict: **score is honest, but flatters the artifact set.** Average dimension score is 8.91/10; the meta-rule (`overall = weakest × 10`) caps the project at 20 because only 3 of the targeted 15 real public PDFs are actively wired in. Nine of ten dimensions are in good shape; one structural gap drags the headline number down by design.

## Per-dimension audit

### code_quality — 9.0/10 (verified)
Independent `.venv/bin/pytest -q` confirmed `527 passed, 1 skipped, 5 warnings in 41.48s`. ruff/mypy already reported clean. The −1 penalty is for the 5 pytest warnings (`DeprecationWarning: builtin type swigvarlink/SwigPyObject has no __module__ attribute`) emitted from a SWIG dependency, not project code. Reasonable, but trivially fixable with a `filterwarnings` entry. Honest score.

### kg_persistence — 10/10 (verified)
`archkg kg status` returned `schema: kg.v1`, `required_tables_present: True`, `query_p95_ms: 0.013`, file at `.archkg/kg.db` (172 KB). All 12 expected tables present. Counts (project=8, run=8, issue=32, feedback_event=184) cross-check with later evidence. Solid.

### kg_coverage — 10/10 (verified)
8 runs ingested vs 7 expected → coverage=1.14×. Independent SQL `SELECT COUNT(*) FROM run` returned 8. Note: scoring saturates at coverage ≥ 1.0, so the "extra" run is not credit-inflating, just slack.

### cross_project_query — 10/10 (verified)
Spot-checked Q1 and Q3 directly against `.archkg/kg.db`. Q3 SQL returned `[(confirmed, 26), (rejected, 5), (needs_info, 1)]` — exact match. Q1 yielded 24 rule rows, top counts `[6, 4, 1]` — same shape as scorer's expected_first. Q4 and Q9 are zero-result queries (`count=0` both sides) which technically count as "correct" by trivial equality; not a fraud, but the 10/10 includes two no-op cases. Worth tracking.

### web_ui_e2e — 10/10 (verified)
`grep` of `archkg/kg/web.py` confirmed 6 routes (5 GET + 1 POST): `/`, `/api/projects`, `/api/projects/<slug>/drawings`, `/api/heatmap`, `/api/issues/<int:issue_id>`, `/api/issues/<int:issue_id>/feedback`. `pytest tests/test_kg_web.py` passed (with feedback_calibration: 25 passed). All flows returned 200 with p95 < 2 ms — fine.

### recognition_quality — 9.52/10 (verified)
`archkg kg quality` returned weighted_precision=0.769, weighted_recall=1.000 across 24 rules. Matches scorer exactly. The 0.5-point deduction reflects precision 0.77 < 0.85 target. **Soft signal worth flagging**: recall=1.0 across every single rule is suspicious — likely the eval set is structured so that ground-truth issues are always a subset of detected issues (which is by construction true if expected ⊂ detected). Precision dispersion 0.40–1.00 across rules is realistic; recall=1.0 uniformly is more an artifact of how the ground truth is sampled than a property of the recognizer. Score is fair, but recall=1.0 should not be marketed as "perfect recall on unseen data."

### real_pdf_breadth — 2.0/10 (verified, this is the cap)
Inspected `samples/understanding_benchmarks/suite_manifest.json` directly: 3 active cases with `fixture_kind` starting with `real_public_` (medfield-a1, medfield-a2, medfield-full-plan-set-multi-plan-intake), all sourced from one Medfield document. Target is 15, current is 3 (one source URL). Score formula `3/15 × 10 = 2.0` is correct. This is the real ceiling for the project. No override.

### calibration — 8.6/10 (verified)
`archkg kg calibration` returned mean_abs_deviation=0.062 across 3 populated bins (n=50/55/55) — matches. Bins [0.0,0.2) and [0.2,0.4) have 0 samples — low-confidence regime not exercised. Per-rule Beta calibrator landed, but the empirical evidence we can audit only covers the upper half of the confidence range. Note: scorer credits 8.6/10; given two empty bins, 8.6 is generous-but-defensible.

### feedback_loop — 10/10 (verified)
`test_feedback_loop_synthetic_test_is_monotonic_and_predictable` passed in the focused pytest run. Posterior trajectory `[0.333, 0.25, 0.2]` is monotonic non-increasing; delta=−0.167 matches expected. Mathematically clean.

### documentation_honesty — 10/10 (verified, with caveat)
Scorer found no overclaims. I grepped READINESS.md / README.md for phrases like "15 real", "all real", "full real PDF coverage" — no hits. README does declare "评估阶段工具，不是即开即用的生产服务" up top, which is the right tone. **One soft note**: README does not currently surface the 3/15 real-PDF gap in plain language. Not a fabrication, just absence. 10/10 is justified by the scorer's strict overclaim test, but the project could be more explicit.

## Recommended next phase

**Target: real_pdf_breadth (current 2.0 → 4.0+ in one phase).** The single highest-leverage move: source and wire in 3–4 additional real_public_pdf cases (different jurisdictions, ideally different drawing styles — e.g. one CDOT/state DOT plan, one school district, one private architectural review board). Each new active `real_public_pdf` case at `fixture_kind: real_public_pdf` and `status: active` adds 0.67 points. Reaching 6 active = 4.0/10, which lifts the meta-cap from 20 → 40 immediately, even without touching anything else. The smallest viable phase: add **3 cases**, get to 6, score → 40.

Important: scaling here is not just "find more PDFs" — each case needs a `run_dir`, `expect`, and `provenance` artifact set generated and committed, so plan ~half a day per case at current tooling speed. If `expect` JSON generation is still manual, that's the bottleneck to break first.

## Blockers

- **Only 3 active real_public PDFs vs 15 target.** Single-source (Medfield) — geographic and stylistic bias likely. This is the headline blocker for breaking past 30/100.
- **Recall=1.0 across all 24 rules.** Likely an eval-set construction artifact (expected ⊂ detected). Need adversarial/negative examples or genuine missed-issue cases before recognition_quality can be claimed at >9/10 on out-of-distribution PDFs.
- **Calibration has 2 empty bins (0.0–0.4).** No empirical evidence that low-confidence predictions are calibrated. Not blocking 99+, but blocks any claim of "calibrated across the full confidence range."
- **2 of 10 canonical queries return 0 rows.** Q4 (rule+clause pairs) and Q9 (distinct clauses per rule by standard prefix) match expected=0, but trivially. These should be re-validated on a corpus that exercises the JOINs.
- **5 pytest warnings unfiltered.** Easy −1 to recover.

The 8.91 average is real; the 20.0 overall is also real and not a bug — it correctly reflects that this project has built a fully functional KG/UI/calibration stack on a 20%-complete real-world fixture set.
