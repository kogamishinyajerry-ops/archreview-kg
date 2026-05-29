# M6 Round 1 — archreview-test-judge verdict
**Date:** 2026-05-16
**Auditor:** archreview-test-judge (independent)
**Project's claim:** overall 100.0/100, ninety_nine_plus: true (all 12 dims at 10.0)

## Verdict
- Judge overall: **88.0 / 100**
- Judge ninety_nine_plus: **false**
- Overrides applied: **5**

The project is in genuinely good shape — code is clean, the KG is real, the
queries do execute, the demo video really renders and contains an honesty
shot, and the docs do not contain the obvious "production-ready / enterprise /
100% accurate" marketing phrases the scorer looks for. **But** the internal
scorer's "100.0 / 99+" claim hides four real soft spots: a tautological
query (Q4 hardcoded empty=empty), a precision/recall measurement built
entirely on synthetic reviewer labels, a quickstart that exceeds the
strict 80-line cap I was told to enforce, and an `F1 = 1.00` README badge
that, while technically accurate for the adversarial battery, is the
kind of badge that misleads a casual reader skimming the front page.
Those are not catastrophic, but they are exactly the things the
"100 / 100 / 99+" claim is supposed to certify *against*.

## Per-dimension audit

### 1. code_quality
- Project claim: 10.0
- Evidence checked:
  - `ruff check archkg/` → `All checks passed!` (exit 0)
  - `mypy archkg/` → `Success: no issues found in 103 source files`
  - `pytest -q` → `527 passed, 1 skipped in 37.49s` (skip = optional `ifcopenshell` module, legitimate)
- Verdict: **keep 10.0**
- Reason: All three independently re-run, all clean. No flakiness on rerun.

### 2. kg_persistence
- Project claim: 10.0
- Evidence checked:
  - `.archkg/kg.db` exists, schema_version table = `kg.v1`
  - 12 expected tables all present (clause / drawing / edge / entity / feedback_event / issue / project / reviewer / rule / run / schema_version / sheet)
  - Row counts non-trivial: 33 projects, 33 drawings, 33 runs, 25 rules, 148 issues, 22 reviewers, 3045 feedback events
- Verdict: **keep 10.0**
- Reason: KG file is real, schema is the claimed `kg.v1`, and the counts are consistent across `quality_score.json` and a live SQL probe.

### 3. kg_coverage
- Project claim: 10.0 (33/33 runs ingested)
- Evidence checked:
  - `suite_manifest.json` lists 33 active cases, all 33 appear in `run` table
- Verdict: **keep 10.0**
- Reason: 1.0 coverage on the manifest is real; the manifest itself is honest about which cases are `active` vs `known_gap`.

### 4. cross_project_query
- Project claim: 10.0 (10/10 canonical queries correct)
- Evidence checked:
  - 8 of 10 queries return non-trivial row sets that match the Python expected (Q1=25 rows, Q2=11, Q3=4, Q5=26, Q6=1, Q7=1, Q8=127, Q10=33)
  - **Q4 is hardcoded**: `archkg/kg/query.py:200` ships SQL `"SELECT 'python_only' AS marker WHERE 0"` and expected `lambda store: []`. Both sides return empty by construction; the "correct=true" is a tautology, not a verification.
  - Q9 expected is also 0 in the current KG, but Q9's SQL is real (`SELECT r.rule_id, COUNT(DISTINCT c.clause_id) ... JOIN clause c`); the empty result is a genuine "no rule_id prefix matches a standard_id" finding, which is sad but not dishonest.
- Verdict: **override → 8.5**
- Reason: Q4 should not count as a verified query — the module's own comment calls it "Python-vs-Python sanity check until we add a normalised clause edge". -1.5 (10% of dim weight) is fair for a 1-of-10 free pass.

### 5. web_ui_e2e
- Project claim: 10.0 (6/6 flows pass at p95 < 30s)
- Evidence checked:
  - `index_html`, `project_list`, `project_drawings`, `heatmap`, `issue_detail`, `annotate_feedback` all return 200 with p95 ≤ 2ms — these are in-process Flask test-client calls, not real HTTP, but the scorer states ≤ 30s threshold and they pass that comfortably.
  - `archkg/kg/web.py:240/252` does register `errorhandler(404)` and `errorhandler(500)` → pilot_readiness's `error_pages_wired` claim cross-checks.
- Verdict: **keep 10.0**
- Reason: Flask app boots, all 6 flows return 200, error handlers are wired. The flows are smoke-level, not user-journey-level, but the dimension's rubric only asks "loads and serves issue/quality pages" which is true.

### 6. recognition_quality
- Project claim: 10.0 (weighted P=0.87, R=0.94, all 25 rules measured)
- Evidence checked:
  - Module `archkg/kg/recognition_quality.py` computes TP/FP from `feedback_event` confirm/reject rows and FN from `expected_rule_counts` in benchmark expect files. The math is honest.
  - **However**: all 22 reviewers in the KG are synthetic (`demo-reviewer-alice/bob/.../extra-NN`); each `extra-*` reviewer has exactly 146 events — clearly programmatically generated. Precision/recall is therefore measured against **synthetic labels**, not real human verdicts.
  - Some rules have `expected = 1` (e.g. RC-BALCONY-RAILING-HEIGHT-RESI, RC-ELEVATOR-REQUIRED) which makes recall trivially 1.0 if the rule fires at all. That inflates the weighted recall.
  - The synthetic nature **is disclosed** in `READINESS.md:40` ("合成审稿员 ... 命名前缀 demo-reviewer- 在 KG 中可直接识别，从不与真实审稿员混淆"). So this is honest-but-disclosed, not hidden.
- Verdict: **override → 8.0**
- Reason: -2 for synthetic-only labels driving the headline 10.0. Disclosure mitigates but does not nullify the issue — the scorer presents `weighted_precision: 0.8682` next to a "10.0" without surfacing that the labels are entirely synthetic. A reviewer skimming `quality_score.json` would not see the caveat.

### 7. real_pdf_breadth
- Project claim: 10.0 (18 active real_public PDFs, threshold ≥ 15)
- Evidence checked:
  - 29 `*_provenance.json` files under `samples/understanding_benchmarks/real/`
  - Each provenance references a public `source_url` (Cambridge MA / Medfield MA / Hopkins MN city sites)
  - Sourced PDFs in `tmp/p86-multisrc/` verified via `file`: `brookline-217kent.pdf` is "PDF document, version 1.7, 12 pages", `cambridge-207lexington.pdf` is "PDF document, version 1.6", etc. — the magic bytes are real.
  - One probe (`austin-interior-remodel.pdf`) is HTML masquerading as `.pdf` (file says "HTML document text") — but it is NOT in any `*_provenance.json` and is NOT marked active in the manifest. The system correctly excluded the bad source.
  - Jurisdictional bias (MA-heavy) is explicitly acknowledged in each provenance file (`jurisdiction_bias_acknowledgment` field).
- Verdict: **keep 10.0**
- Reason: 18 ≥ 15 threshold; PDFs are real on disk; bad sources excluded; jurisdictional bias openly disclosed. This dimension is the most honest one.

### 8. calibration
- Project claim: 10.0 (mean abs deviation = 0.0362, threshold ≤ 0.04)
- Evidence checked:
  - 5 bins reported, lowest bin (0.0–0.2) has `sample_size: 0` and is excluded from MAD (`min_samples_per_bin: 5`).
  - Remaining 4 bins: observed precisions 0.35 / 0.55 / 0.7286 / 0.8838 vs midpoints 0.3 / 0.5 / 0.7 / 0.9 — deviations 0.05 / 0.05 / 0.029 / 0.016. MAD = 0.0362, just under the 0.04 threshold for 10.0.
  - This is suspiciously close to the threshold but not implausible — the calibration data has plenty of samples (2720 in the top bin, 140 in the 0.6–0.8 bin) so the precisions are stable.
- Verdict: **keep 10.0**
- Reason: Math is honest. MAD is under threshold. The empty first bin is a transparency gap (no low-confidence detections to calibrate) but the scorer correctly excludes it.

### 9. feedback_loop
- Project claim: 10.0 (monotonic decrease after 3 rejects, delta matches expected)
- Evidence checked:
  - Module `archkg/kg/feedback.py` runs a synthetic Beta-Binomial test: 1 confirm + 3 rejects should produce posterior mean trajectory 0.333 → 0.25 → 0.20, which it does.
  - This is a **math correctness test**, not an integration test of the feedback loop. It proves the Bayesian update is monotonic, not that the system captures real reviewer verdicts in production.
  - Separately confirmed via `archkg/cli/main.py:364`: `build_review_state(result.issues, ...)` and `write_review_state(..., out/"review_state.json")` — review verdicts are written to a separate artifact, not back into `issues.json`. The architecture matches the mandate.
- Verdict: **keep 10.0**
- Reason: The synthetic test is the right test for this dimension as scored, and the architectural separation (review_state.json ≠ issues.json) is real.

### 10. documentation_honesty
- Project claim: 10.0 (no overclaims detected)
- Evidence checked:
  - Scorer searches for: "production ready", "production-ready", "battle tested", "battle-tested", "fully automated review", "replaces human reviewer", "100% precision", "100% recall". None found in README or READINESS.
  - README does open with `⚠️ **当前定位**: 评估阶段工具，不是即开即用的生产服务` — explicit non-production disclaimer.
  - **BUT**: the README top-of-fold has a badge `F1-1.00 on 100-case battery`. The body (line 385) does clarify "985 TP / 0 FN / 0 FP across 21 targeted rules at F1=1.00" — i.e. on the synthetic adversarial battery, not on real PDFs. A casual reader skimming the badge could read this as "the system is F1=1.00 in general use", which would be false (real-world weighted P/R is 0.87 / 0.94).
  - The scorer's forbidden_phrases list does not catch the implicit F1=1.00 overclaim because it is in a shields.io badge, not prose.
- Verdict: **override → 8.5**
- Reason: -1.5 for the F1=1.00 badge at the top of README. The body text qualifies it, but a top-of-fold badge that boasts a metric only achieved on synthetic adversarial data is the textbook definition of an overclaim, even if the scorer's regex misses it. The fix is trivial (change the badge to "F1 1.00 — adversarial battery") but should not slide on a 10.0.

### 11. pilot_readiness (M6 new)
- Project claim: 10.0
- Evidence checked:
  - `docker-compose.yml` present (1286 bytes), healthcheck wired (`test: wget -qO- http://localhost:8765/`, interval 10s), service builds from `Dockerfile.pilot`. ✅
  - `Dockerfile.pilot` present (1114 bytes). ✅
  - `bin/archkg-pilot` present, executable bit set (`-rwxr-xr-x`). ✅
  - `docs/PILOT_QUICKSTART.md`: 88 lines total (`wc -l`), 8 `^## ` sections. The mandate says "≥5 sections AND ≤80 lines". **The 80-line cap is exceeded by 8 lines.** The internal scorer measures "content lines" (non-empty, non-header) = 57 and passes its own internal ≤80 content-line check. The two cap definitions disagree.
  - Flask error handlers (`@app.errorhandler(404)`, `@app.errorhandler(500)`) wired in `archkg/kg/web.py:240/252`. ✅
- Verdict: **override → 8.0**
- Reason: -2 because the mandate's strict 80-line cap is exceeded by 8 lines (`wc -l` = 88). The internal scorer uses a more generous "content lines" measurement (57 ≤ 80) and passes its own check — but the verdict is supposed to be the *judge's* read of the mandate, not the scorer's. Quickstart could be tightened by collapsing the two "Path A / Path B" install paths or trimming the troubleshooting section.

### 12. demo_video_quality (M6 new)
- Project claim: 10.0
- Evidence checked:
  - `archreview_kg_demo_final.mp4` exists, 44,800,102 bytes (~43 MB, ≫ 1 MB threshold). ✅
  - `ffprobe`: duration 283.38s (in [180, 360] range), resolution 1920x1080 (≥ 1080p). ✅
  - `storyboard.json`: 8 shots, each with `caption + start + end + duration` of correct types. Shot durations sum to ~257.97s of content + 7×0.8s gaps = ~263.57s + leading buffer ≈ 283.37s total — consistent with reported duration. ✅
  - Shot 7 is `kind: "limitations"` with caption "Honest limitations — over-detection, count-level recall, MA-only sourcing". Mandatory honesty shot present. ✅
  - `voiceover.wav` exists (~48 MB, WAVE PCM 16-bit stereo 44.1kHz, verified via `file`). ✅
  - `script.txt` exists (~4.7 kB), contains per-shot voiceover text including the explicit "MA-only sourcing" honesty admission and even references this judge agent by name ("an independent test agent — also in this repository, named archreview-test-judge").
- Verdict: **keep 10.0**
- Reason: All 6 sub-checks pass independently. The video is real, the right length, the right resolution, and the honesty shot is mandatory-and-present. One minor flag: the script.txt mentions that the judge "has, on multiple iterations, said seventy, then ninety-two, then ninety-five, then one hundred" — that prior claim is asserted by the project, not verified by me. But the dimension I'm scoring is the *demo asset itself*, and the asset is well-built.

## Cross-cutting honesty notes
- The biggest gap between the "100.0/100" headline and reality is **synthetic reviewers**. 22 of the 22 reviewers are programmatic (`demo-reviewer-extra-NN` with exactly 146 events each). This is *disclosed* in `READINESS.md:40` but not surfaced in `quality_score.json` itself — a reader who only opens the JSON sees `weighted_precision: 0.87` and `score: 10.0` with no indication that the precision is computed against synthetic labels. The architecture is set up for real human feedback (review_state.json is separate, feedback_event table exists, calibration learns from rejections), but the **labels driving the M6 round-1 scores are entirely synthetic**.
- Q4 in canonical queries is a tautology (`[] == []`). The module's own comment admits this is a placeholder ("Python-vs-Python sanity check until we add a normalised clause edge"). It should not count toward "10/10 correct".
- The README's `F1-1.00 on 100-case battery` badge is technically accurate (the adversarial synthetic battery does score F1=1.00 because the candidate plans are constructed to make planted violations findable) but misleadingly placed at top-of-fold. A casual reader will infer the system itself has F1=1.00 in general use; the actual weighted P/R on the real-PDF benchmark is 0.87 / 0.94.
- The `austin-interior-remodel.pdf` HTML-disguised-as-PDF in `tmp/p86-multisrc/` was correctly *excluded* from the active manifest. That is good hygiene and reinforces credibility on the dimensions that did keep 10.0.
- The honesty shot in the demo video, the explicit non-production disclaimer at the top of README, the `READINESS.md` synthetic-reviewer disclosure, and the jurisdictional-bias acknowledgment in every provenance file are **all real honesty signals**. The project is not trying to lie — but the headline score does paper over residuals that a human evaluator would want surfaced.

## Recommendation for next round
1. **Decompose `recognition_quality` into `precision_synthetic` and `precision_real`**. Score the synthetic precision at 10.0 if the math is honest; gate the second sub-dimension at 0 until ≥1 real human reviewer (not `demo-reviewer-*`) confirms or rejects ≥50 issues. This prevents the same 10.0 from being claimed twice with different label sources.
2. **Drop Q4 from the canonical query set** until the `issue→clause` edge is implemented, OR make the SQL non-trivial enough that "correct=true" requires actual data agreement. Tautological passes inflate the cross_project_query score by 10%.
3. **Trim `PILOT_QUICKSTART.md` to ≤80 raw lines** (currently 88). Either collapse Path A / Path B into one section or move Troubleshooting to a separate doc.
4. **Swap the `F1-1.00` README badge** for `F1 1.00 — adversarial battery` or `F1 1.00 — synthetic`. The qualifier in the body text (line 385) should be in the badge itself.
5. **Add a `synthetic_label_disclosure` field to `quality_score.json`** that surfaces, next to `weighted_precision`, the count of distinct human (non-`demo-`) reviewers. Right now you have to read the schema, the SQL, and READINESS.md to discover that the number is zero.
6. **Reconsider what "ninety_nine_plus: true" means** when 1 of 12 dimensions (recognition_quality) is built on synthetic labels and 1 of 10 canonical queries is a tautology. The current rule "all ≥9 AND ≥75% at 10" passes mechanically, but the substantive bar (≥9 dimensions independently verifiable against artifacts on disk) is closer to 9/12 than 12/12.
