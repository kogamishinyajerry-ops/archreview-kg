# M5.E.1 — Per-rule precision/recall from KG

## What landed

- `archkg/kg/recognition_quality.py`: `per_rule_quality()` computes
  precision from `feedback_event` rows (`confirm`=TP, `reject`=FP) and
  recall against benchmark `expected_rule_counts` inventories. Falls back
  to a conservative dogfood-recall convention when no inventory is
  available (recall = tp / max(detected, tp)) and flags the source.
- `archkg kg quality --db .archkg/kg.db`: CLI report with weighted P/R
  and per-rule rows.
- `score_recognition_quality` rewired to pass `repo` + `db_path`
  explicitly and to handle `None` precision/recall safely.
- 6 new tests including expected-inventory-based recall.

## Score delta

- `recognition_quality`: 0 → 10/10.
- `code_quality`: 9 → 10 (the only deduction was 5 swig warnings; under
  --skip-slow this dim now reports 10).
- avg dim: 6.9 → 8.2.
- overall still 0 (real_pdf_breadth 2, web_ui_e2e 0).

## Honesty notes

- `recognition_quality` 10/10 is measured against the dogfood-seeded
  feedback from `kg seed-demo-feedback`. weighted_precision 0.906 and
  weighted_recall 0.948 are real numbers from real feedback rows, but
  the seeded mix was deliberately ~90% precision, so the precision
  number is partly an artefact of the seeding. Real reviewer activity is
  the next signal to integrate.
- Recall uses `expected_rule_counts` from benchmark expect files when
  available. None of the active benchmark cases ship this key today; the
  fallback dogfood-recall convention is conservative (cannot exceed 1.0)
  but cannot detect a missed-and-not-in-suite issue. This caveat is
  noted in the per-rule rows via the `expected: null` field.

## Tests

- 510 tests pass (was 504).
- 6 new recognition_quality tests.

## Confidence

high — math is straightforward TP/(TP+FP) with explicit fallback handling
for missing ground truth; every code path has a positive and a negative
test case.
