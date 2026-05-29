# M5.Z Blueprint — Final Push to 99+

> Created: 2026-05-16
> Owner: Claude (Opus 4.7, acting as project lead)
> Authorization: User granted full autonomy, blueprint-driven iteration to >= 99/100
> Parent: `.planning/M5-BLUEPRINT.md` (the M5.Z cluster the parent promised)

## Premise

M5 is structurally complete on 8 of 10 dimensions. The current `quality_score.json`
shows avg dimension 8.91/10 but overall capped at 20/100 by the weakest-dim
meta-rule. The headline number is real, but it is dragged by one structural gap
(`real_pdf_breadth = 2/10`) and three small polishes the test-judge already
flagged.

The work below is *closing* M5, not opening a new milestone. Re-platforming or
adding new product surfaces is explicitly out of scope.

## Quantitative target

| Dimension              | Now   | After W1-W4 | Path                                                |
|------------------------|-------|-------------|-----------------------------------------------------|
| code_quality           | 9.0   | 10          | Filter SWIG `DeprecationWarning` in pytest config   |
| kg_persistence         | 10    | 10          | Already at ceiling                                  |
| kg_coverage            | 10    | 10          | Saturated                                           |
| cross_project_query    | 10    | 10          | Replace trivial 0-row Q4/Q9 with non-trivial JOINs  |
| web_ui_e2e             | 10    | 10          | Already at ceiling                                  |
| recognition_quality    | 9.52  | 10          | Break recall=1.0 uniform by adding adversarial expected_rule_counts; lift precision via per-rule re-tuning where the audit flags FPs |
| real_pdf_breadth       | 2.0   | 10          | 3 → 15+ active real_public_pdf cases                |
| calibration            | 8.6   | 10          | Populate 0.0-0.4 confidence bins via calibrated detection-time confidence + larger feedback panel |
| feedback_loop          | 10    | 10          | Already at ceiling                                  |
| documentation_honesty  | 10    | 10          | Hold the line; add invariant test                   |
| **Overall (meta)**     | **20**| **>= 99**   | Weakest dim must reach 10 (with one allowed 9.5+)   |

## Wave structure

Each wave ends with a spawn of the `archreview-test-judge` subagent. The judge
writes `QUALITY-REVIEW.md`; if it flags a regression the wave is reopened, not
moved past. The judge's verdict is the score.

### W1 — Recognition, calibration, query polish (low external dependency)

This wave needs no PDFs. Pure code + fixture work.

**W1.A — Adversarial expected_rule_counts (recognition_quality)**

The judge flagged recall=1.0 across all 24 rules as suspicious — likely
"expected ⊂ detected" by construction. Counter-move:

- Add `expected_rule_counts` to `samples/understanding_benchmarks/real/medfield_a1_first_floor_expected.json` and
  `samples/understanding_benchmarks/toy/sample_clean_full.json` (already partially
  seeded in M5.I-01).
- Include rules the reviewer expects to NOT trigger on that fixture
  (e.g., RC-STAIR-* on a sheet with no stair → expected=0, detected>0 means FP).
- Re-run KG ingest. Recognition_quality recall will drop below 1.0 (honest), and
  precision will become per-rule tunable.

**W1.B — Detection-time Beta calibration (calibration)**

The Beta-posterior calibrator already lands posteriors via feedback events
(M5.I-02). But detection-time confidence is still the uncalibrated rule-based
value. Counter-move:

- In `archkg/rules/*` (or the equivalent confidence emitter), apply
  `calibrated_confidence = beta_posterior_mean(rule_id, default=prior)` at
  detection time.
- Result: low-confidence bins (0.0-0.4) populate naturally because some rules
  with poor reviewer agreement now emit lower confidence on next run.
- Re-run `archkg kg calibration` — `mean_abs_deviation` should drop and at least
  4 of 5 bins should be populated.

**W1.C — Non-trivial Q4 and Q9 (cross_project_query)**

The judge noted Q4 (rule+clause pairs) and Q9 (distinct clauses per rule by
standard prefix) match `count=0` trivially. Counter-move:

- Re-seed the test KG with one fixture that exercises rule→clause edges and
  multi-standard clause prefixes (GB 50016 / GB 50352 / GB 50096).
- Update `archkg/kg/queries.py` canonical-query fixtures so Q4 and Q9 return
  non-zero rows. Keep the SQL-vs-Python parity check.

### W2 — real_pdf_breadth phase 1: Medfield per-sheet split

Existing artifact: `tmp/p28-real/medfield-floorplans-elevations.pdf` (9 pages).
Existing cases: A-1, A-2, full-set (3 active).

**Split** the remaining 7 sheets into independent active cases:

| Page | Likely sheet      | New case_id                          |
|------|-------------------|--------------------------------------|
| 1    | Title / cover     | medfield-cover (status: known_gap, not a plan) |
| 2    | Site plan         | medfield-site-plan                   |
| 3    | A-0 / index       | medfield-a0-index (known_gap if pure index) |
| 5    | A-3 third floor   | medfield-a3-third-floor              |
| 6    | A-4 fourth floor  | medfield-a4-fourth-floor             |
| 7    | A-5 fifth floor   | medfield-a5-fifth-floor              |
| 8    | A-6 elevations    | medfield-a6-elevations (likely known_gap — recognizer is plan-tuned) |
| 9    | A-7 elevations    | medfield-a7-elevations (likely known_gap) |

Each new ACTIVE case (not known_gap) requires:
- `samples/understanding_benchmarks/real/<case_id>_run/drawing_understanding.json`
- `samples/understanding_benchmarks/real/<case_id>_expected.json`
  (with `expected_rule_counts`)
- `samples/understanding_benchmarks/real/<case_id>_provenance.json`
- Entry in `suite_manifest.json` with explicit shared-source note

Realistic active uplift: A-3, A-4, A-5 (3 plan sheets). Plus site-plan if it
parses reasonably. Plus the existing 3. That's 6-7 active vs 15 target.

If shared-source bias caps the score (judge may penalize), W2 alone gets us to
~6-7/10, not 10/10. W3 is mandatory.

### W3 — real_pdf_breadth phase 2: multi-source acquisition

Source 8-10 PDFs from diverse municipal building departments. Per case:

1. WebSearch / WebFetch to find a publicly-downloadable architectural plan PDF
   (no records request).
2. Save to `tmp/p86-real/<case_id>.pdf`.
3. Run `archkg viewer <pdf>` to produce baseline `drawing_understanding.json`.
4. Hand-curate `expected.json` from a 20-minute inspection (component count
   ranges, semantic kinds, evidence signals, expected_rule_counts).
5. Commit `samples/understanding_benchmarks/real/<case_id>_*.json` + add to
   `suite_manifest.json`.

Target sources (from M5-STATUS.md hints + research):

- Boston-area: Cambridge MA, Newton MA, Brookline MA
- Mid-Atlantic: Arlington VA, Montgomery County MD, Washington DC
- West coast: Berkeley CA, San Francisco CA, Portland OR
- Texas: Austin city planning open data

Threshold for "counts as a case": active iff `expected_rule_counts` is populated
AND the recognizer produces non-empty `drawing_understanding.json`. Otherwise
it's `status: known_gap` and only contributes documentation honesty.

### W4 — Code quality + honesty polish

- `pyproject.toml`: add `[tool.pytest.ini_options] filterwarnings = ["ignore::DeprecationWarning:swig.*"]`
- `READINESS.md`: replace the 3/15 line with the new ratio; add an "M5 final push
  closeout" subsection citing the final `quality_score.json` and judge verdict.
- `tests/test_documentation_honesty_invariants.py`: assert that README/READINESS
  do not contain forbidden phrases ("all rules", "fully automated compliance",
  "production-ready audit", etc.) and that any "X/Y" ratio in TL;DR matches the
  current suite manifest count.

### W5 — Final verification x2 + close

- Day N: spawn archreview-test-judge → expect overall >= 99.
- Day N+1: spawn archreview-test-judge again → confirm reproducibility.
- Update `.planning/m5/M5-STATUS.md` with closeout table.
- Mark M5 complete in ROADMAP.md and CHANGELOG.md.
- Commit `quality_score_m5_final.json` and `QUALITY-REVIEW-m5-close.md`.

## Gating rules (the dedicated test agent)

The `archreview-test-judge` subagent (`.claude/agents/archreview-test-judge.md`)
is the only voice that scores this project. Rules of engagement:

1. After every wave, spawn the judge with the repo root path. Wait for verdict.
2. If overall dropped: wave is reopened. No move-forward.
3. If overall flat: investigate why (likely judge override or unmeasurable
   regression). Fix before next wave.
4. If overall up but a previously-best dimension regressed: blocking.
5. Judge cannot be argued with mid-wave. If it says 78, the project is 78.
6. Score MUST be committed to disk (`quality_score.json` next to the report)
   after every spawn, even on regressions.

## Hard process discipline (carryover from M5 parent)

- No new handoff bundle navigation fields. P78-P85 pattern stays frozen.
- All commits: `feat(M5.Z.W?-NN): <summary>` with footer `confidence: low|med|high`.
- One git commit per atomic unit; no batching.
- Pre-existing 527 tests must continue to pass.

## Exit criteria for M5 (= exit criteria for M5.Z)

1. Test-judge reports overall >= 99 across two consecutive runs on different
   days.
2. All 10 dimensions >= 9, at least 7 dimensions == 10.
3. No regression vs the highest historical score per dimension.
4. CHANGELOG and ROADMAP updated with the closeout commit.
5. M5 final score and judge report committed to repo.

## Out of scope (recur from parent for clarity)

- New product surfaces (no M6 work; no new CLI commands beyond what calibration
  needs).
- Authentication, multi-user, cloud hosting.
- ML-based recognizer rewrite.
- Notion sync of KG content (KG stays local).

## Risk register (M5.Z-specific)

| Risk                                                    | Mitigation                                                                                    |
|---------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| Cannot find 12 truly-public PDFs without records request| Stop honestly at whatever count is achievable; let `real_pdf_breadth` cap overall, document gap |
| Per-sheet Medfield split blurs metric semantics         | Document shared source in each case provenance; judge may still cap at 0.8x for shared-source bias |
| Adversarial expected_rule_counts surfaces real precision regressions | Repair recognizer where the FP is fixable; otherwise honestly let precision drop and document |
| Detection-time calibrator changes downstream rule output| Treat as a real behavioral change; update fixtures, do not paper over                          |
| WebFetch returns paywalled or login-required pages      | Skip case; do not fake a PDF source                                                            |
