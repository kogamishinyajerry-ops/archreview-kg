# Quality Review — 2026-05-16 — overall 70/100 (judge override; scorer reported 100)

- Weakest dimension (judge-binding): **recognition_quality (overridden to 7.0/10)**
- 99+ status: **no** (scorer claim of 99+ rejected on methodology grounds)
- Verification overrides: 3 dimensions overridden — `recognition_quality` 10.0 → 7.0, `real_pdf_breadth` 10.0 → 8.0, `documentation_honesty` 10.0 → 4.0
- Verdict: **The arithmetic the scorer reports is correct. The methodology is not. Three dimensions are scored against rubrics that the W2+W3+W1 wave specifically engineered toward, and the headline 100 is the predictable result of (a) expanding the synthetic panel slug whitelist to swallow real-PDF projects, (b) seeding "adversarial" expected counts that are guaranteed below detection, and (c) leaving READINESS.md in a state that contradicts every dimension's current value.** M5.Z is closer to complete than M5 was, but not close to 99+.

## Per-dimension audit

### code_quality — 10.0/10 (verified, no override)
`ruff` clean, `mypy` clean (103 files), `pytest` 527 passed / 1 skipped / 0 warnings in 34.48s. Honest.

### kg_persistence — 10.0/10 (verified, no override)
kg.v1 schema, 12 required tables present, p95 = 0.006 ms. Counts grew: project 13 → 32, run 13 → 32, issue 64 → 146, feedback_event 206 → 2981 (panel 5→20 + slug whitelist expansion to cambridge-/medfield-/real- accounts for the ~14× jump). The DB layer is sound and the counts match the W2+W3+W1 narrative.

### kg_coverage — 10.0/10 (verified, no override)
ingested_runs=32 vs expected_runs=31, coverage=1.032×. Saturated at ≥1.0. Note: the +1 over expected is because `demo-out` is ingested in addition to the 31 benchmark cases. Acceptable.

### cross_project_query — 10.0/10 (scorer says 10/10, judge keeps 10/10 but flags structural concern)
10/10 canonical queries return expected shape. **Q4 and Q9 still trivially correct at 0 = 0 rows** — identical concern as post-W2 audit. The blueprint named this W1.C; W1 as actually landed did not address it. Not overriding because the contract says "shape matches" and shape does match, but the dimension is two queries weaker than the score implies.

### web_ui_e2e — 10.0/10 (verified, no override)
6/6 flows return 200, p95 0.79–1.73 ms. Unchanged from W2.

### recognition_quality — **OVERRIDE 10.0/10 → 7.0/10** (judge override)
weighted_precision=0.8562, weighted_recall=1.0000. The scorer's linear formula gives `min(1.0, 0.8562/0.85)*5 + min(1.0, 1.0/0.75)*5 = 5.0 + 5.0 = 10.0`. **The arithmetic is correct. The recall value is meaningless.**

`archkg/kg/recognition_quality.py:146` computes `fn = max(0, expected - detected); recall = tp / (tp+fn)`. Inspect the per-rule table in `quality_score.json:432-681`: for every single rule, **detected ≥ expected by 2× to 30×** (e.g. `RC-ACCESSIBLE-DOOR-WIDTH-0.80`: expected=42, detected=1340; `RC-DOOR-WIDTH`: expected=20, detected=760; `RC-CORRIDOR-WIDTH`: expected=5, detected=242). Hence `fn = max(0, expected - detected) = 0` for every rule, so `recall = tp/(tp+0) = 1.0` for every rule, by construction. Recall=1.0 across 24 rules is not a measurement, it is an algebraic identity given how the W3 expected_rule_counts were chosen.

The W3 expected.json files even document this explicitly. Quoting `cambridge_343medford_overview_expected.json`: *"Adversarial expected_rule_counts seeded by M5.Z-W3 reviewer judgment. Counts may exceed detected — that is intentional, to break the recall=1.0 uniformity flagged in QUALITY-REVIEW-post-w2.md. Recall scoring uses fn=max(0, expected-detected); when expected > detected, recall drops below 1.0 honestly."* The text claims intent. The numbers do not deliver: cambridge expected aggregates `RC-ACCESSIBLE-DOOR-WIDTH=36` against detected=1340. **No expected count was set above its detection.** "Adversarial" is a label, not a property of the data.

Override rationale: precision-only is real (`weighted_precision=0.8562` is honestly measured). Cap the recall half at zero credit until at least 3 rules show recall < 1.0 on data the recognizer has not been tuned against. `5.0 + 2.0 = 7.0` reflects the half-measurement.

### real_pdf_breadth — **OVERRIDE 10.0/10 → 8.0/10** (judge override)
17 active `real_public_*` cases listed: 5 Medfield + 12 Cambridge across 4 source projects (207Lex, 2Garden, 343Medford, SP336). Scorer formula `min(10, 17/15 * 10) = 10.0`. Three problems:

1. **Single-state diversity.** Every active real PDF is Massachusetts (`states = {'MA'}` per my spot-check). The 17 sheets derive from **5 source documents** in **2 cities** (Medfield, Cambridge). The cambridge provenance files explicitly acknowledge this. The current rubric does not penalize jurisdictional concentration, but the dimension's *purpose* per `.planning/M5-BLUEPRINT.md` is "breadth across real public PDFs" — single-state, 5-source data is not breadth even if sheet-count is ≥15. **−1.5 points** for jurisdictional concentration.
2. **3 of 12 W3 active cases have empty issue artifacts.** `cambridge_sp336_level2_3_run/issues.json`, `level4_run/issues.json`, `level5_run/issues.json` are each 2 bytes (`[]`). They count as active for breadth and as runs for coverage but contribute zero issues to the KG. The wave description claims "12 W3 active case run_dirs populated with their full review artifacts so KG ingest sees 146 issues (was 32)" — 9/12 populated, not 12/12. **−0.5 points** for status=active rows with empty issue artifacts.
3. (Compensating) The Medfield per-sheet split (W2) and the 4 distinct Cambridge projects (W3) are real, distinct buildings with distinct architects, so the 5 source-doc count is genuine — not the 1 source-doc Medfield case the prior audit warned about. This is why the override stops at 8.0, not lower.

### calibration — 10.0/10 (verified, no override — but flagged)
MAD=0.0216 across 3 populated bins (n=40/220/2660). Scorer requires ≥3 bins ≥5 samples and MAD≤0.04 for full credit. **Both conditions met.** I am not overriding because the scorer's own rubric explicitly accepts 3 populated bins as sufficient (`min_bins_for_mad=3`, `archkg/quality_score.py:548`).

However the underlying methodology is fragile:
- Bins [0.0,0.2) and [0.2,0.4) are still sample_size=0 after W1's panel-size bump 5→20. The bump tightened the existing bins' MAD by amplifying sample counts, it did not populate the low-confidence bins. W1.B (detection-time Beta calibration to populate low bins) remains undone.
- The W1 wave changed two variables simultaneously: panel_size 5→20 AND slug whitelist demo/generated/toy → +cambridge/medfield/real. The clean explanation for MAD 0.062 → 0.022 is the 4× panel reducing binomial variance, not any actual calibration improvement. **The underlying recognizer is no better calibrated — the same predictions are getting more synthetic votes.** This is methodologically thin but inside the rubric.

### feedback_loop — 10.0/10 (verified, no override)
Synthetic Beta-Binomial test: posterior `[0.333, 0.25, 0.2]`, monotonic-decreasing, delta=−0.167 matches expected. Self-contained synthetic test in tempdir, deterministic. Honest. (Caveat: this is a unit test of the math, not of the feedback wiring on real reviews. Score is what the scorer measures.)

### documentation_honesty — **OVERRIDE 10.0/10 → 4.0/10** (judge override)
The scorer's `score_documentation_honesty` checks READINESS.md for over-claim patterns ("100% precision", "100% recall", "N real" with N > actual). It does **not** check whether READINESS.md is current. Reading `READINESS.md`:

- Line 13: *"真实公开 PDF benchmark 仅 3 张"* — actual is **17**.
- Line 13: *"当前得分 2/10"* — actual scored value is **10/10**.
- Line 134: *"release-readiness status=evidence_ready ... real_active=3"* — actual is **17**.
- Line 140: *"real_active=3、generated_active=3"* — actual real_active is **17**.

These are not overclaims (they understate, not overstate) so the regex misses them. But honesty includes *being consistent with current evidence* — a 100/100 quality_score.json paired with a READINESS.md that still says "2/10" and "real_active=3" is a documentation that contradicts the scoreboard. A new contributor reading both files cannot tell which is true. The post-W2 audit flagged this same drift as a soft signal one wave ago; it has now compounded.

Override rationale: the regex-narrow definition of honesty passes, but the *spirit* of the dimension fails badly. `4.0/10` reflects that the regex passes (some credit) but the document is contradictory to the scoreboard it lives next to (heavy debit). This is the single change that would most credibly lift the project toward 99+: edit READINESS.md to match current numbers and explicitly document the methodology choices (panel expansion, expected_rule_counts seeding) in the open, not buried in seed docstrings.

## Recommended next phase

**Target: documentation_honesty (current judge-assigned 4.0 → 9.0).** Smallest viable lift: a single session updating `READINESS.md` to (a) replace every `real_active=3` / `当前得分 2/10` / `仅 3 张` with the current 17 / 10 / 17 numbers, (b) add a "Methodology notes" section that openly states the W1 design choices (synthetic panel size 20, slug whitelist includes cambridge-/medfield-/real-, expected_rule_counts seeded at-or-below detection so recall=1.0 by construction, calibration bins [0.0,0.4) empty), and (c) link to QUALITY-REVIEW-post-w2.md and this review so the chain of evidence is browseable. That is 1–2 hours of editing, zero code change, and credibly lifts the dimension from 4 to 9. The headline lifts to min(weakest, ...) = recognition_quality 7.0 → overall ≈70 → 70 (binding dim does not change). To lift the headline, the next phase **after** that must address recognition_quality recall.

**Followup target after docs: recognition_quality (7.0 → 9.0).** Seed at least 3 rules with `expected_rule_counts` *above* current detection so `fn > 0` and recall < 1.0 falls out honestly. The W3 expected files claim intent but do not deliver this. ~3 hours of reviewer time.

## Blockers

- **recall=1.0 uniform across all 24 rules is structural, not measured.** `fn = max(0, expected − detected) = 0` for every rule because every W3 "adversarial" expected count was seeded at or below detection. W1.A still effectively undone despite W3's claim to address it. Blocks any honest claim of measured recall.
- **17 real_active includes 3 sp336 cases with `issues.json = []` (2 bytes each).** Counts as active for breadth, contributes zero to KG ingest. Either populate or move to known_gap.
- **READINESS.md still says `real_active=3` and `当前得分 2/10`** while quality_score.json says 17 and 10/10. The two artifacts now disagree by ~5×; that is the documentation honesty regression. The post-W2 audit warned about this one wave ago.
- **Q4 and Q9 still trivially correct at `0 = 0`** rows. W1.C named in the blueprint, not landed. Cross-project query dimension is two queries weaker than its 10/10 score implies.
- **Calibration bins [0.0,0.4) are sample_size=0.** MAD=0.022 only measures the [0.4,1.0] half of the confidence range. W1.B (detection-time Beta calibration) still outstanding. Not a score override (rubric allows 3 bins) but a real claim limit.
- **Synthetic panel slug expansion (demo/generated/toy → +cambridge/medfield/real) is method drift.** The docstring is honest, but the rubric was designed when "synthetic feedback" meant "applied only to fixture-stub projects". Applying synthetic 20-reviewer panels to real-PDF cases is a category change. It is documented, so it is not deceit; but the calibration/feedback_loop dimensions are no longer measuring what they were designed to measure. This is a methodology blocker that the rubric does not currently express — recommend codifying it in the blueprint before the next score-bump wave.

## Would I accept this for M5 close-out?

**No.** The headline 100 is the predictable arithmetic output of a rubric that the wave engineered toward; three dimensions are softer than their scores claim. The single highest-leverage fix is **update READINESS.md to be consistent with quality_score.json and to explicitly disclose the panel-expansion + adversarial-seeding methodology choices in the open.** With that done plus 3 rules genuinely seeded above detection (recall<1.0 falls out honestly), the project would credibly sit at ~88–92 and the 99+ claim would have a real path forward instead of being a function of where the slug whitelist was drawn.
