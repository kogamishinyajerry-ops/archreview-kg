# M5.H — Scorer honesty hardening (post-audit response)

## What this fixes

The test-judge audit of the post-M5.D state flagged two real
overstatements:

1. **recognition_quality 10/10 was a tautology.** The fallback
   `recall = tp / max(detected, tp)` collapses to 1.0 whenever every
   detection is labeled, which is true on every dogfood-seeded rule.
   The weighted recall of 0.918 was rebadged precision, not real recall.
2. **calibration 10/10 was vacuous.** Only one confidence bin (0.8-1.0)
   had samples; MAD averaged over a single bin cannot detect
   miscalibration across the confidence range.

## What landed

- `archkg/kg/recognition_quality.py`: removed the dogfood-recall
  fallback. Rules without benchmark `expected_rule_counts` now have
  `recall = None` and are excluded from the weighted aggregate.
- `archkg/quality_score.py:score_calibration`: requires
  `bins_used_for_mad >= 3` before scoring. Below threshold the dim is
  unmeasurable (0, measurable=False).
- `archkg/kg/ingest.py`: propagates entity confidence to issue
  confidence (max across linked entities), so calibration has varied
  bins to score against.
- `archkg cli kg seed-demo-feedback`: rebuilt to honor existing issue
  confidence and produce per-issue outcomes consistent with that
  confidence (deterministic RNG seed 42).
- `archkg/kg/query.py` Q6/Q7 tie-break fixed to match SQL's
  `ORDER BY n DESC, slug ASC LIMIT 1`.

## Score impact (this commit, full --full)

| dim                   | pre-audit | post-hardening |
| --------------------- | --------- | -------------- |
| code_quality          | 9         | 9              |
| kg_persistence        | 10        | 10             |
| kg_coverage           | 10        | 10             |
| cross_project_query   | 10        | 10             |
| web_ui_e2e            | 10        | 10             |
| recognition_quality   | 10        | **5.0**        |
| real_pdf_breadth      | 2         | 2              |
| calibration           | 10        | **0**          |
| feedback_loop         | 10        | 10             |
| documentation_honesty | 10        | 10             |
| **avg dim**           | **9.1**   | **7.6**        |
| **overall**           | **20**    | **0**          |

Scores dropped because they were honestly measured for the first time.
The meta-rule cap (overall <= weakest_dim * 10) brings overall back to
0 with calibration at 0.

## What's now genuinely measurable but failing

- **calibration**: detector entity confidence ranges 0.0 / 0.5 / 0.8 /
  0.85 / 0.9. Reviewer outcomes derived from synthetic 0.9-target
  blending. Resulting MAD = 21.7%, well above the 8% calibration target.
  The detector confidence today does not predict reviewer outcomes;
  real ML calibration work is required (e.g., temperature scaling on
  per-entity confidence, or replacing the rule-based confidence assignment
  with one fit on reviewer feedback). 0/10 is correct.
- **recognition_quality**: precision 0.84 (just under 0.85 target);
  recall 0 because no benchmark `expected_rule_counts` files exist.
  Adding those is human-review work.
- **real_pdf_breadth**: 3/15. Multi-day sourcing grind across municipal
  building departments.

## Confidence

high — the patch makes scores STRICTER, not laxer. Every change
removes a way to overstate quality. Final score is the honest baseline
for the remaining M5 work.
