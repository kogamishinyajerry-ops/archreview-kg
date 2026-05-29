# P42-01 SUMMARY: Primary Issue Re-Run Diff

## Outcome

Added a read-only re-run diff artifact for primary rule-engine candidate issues.

## Implementation Notes

- New `archkg.review_diff` compares two run directories' primary `issues.json` files.
- New `review_diff.v1` schema records summary counts and per-item status: `unchanged`, `changed`, `new`, or `resolved`.
- Matching ignores random per-run `issue_id` and entity ID values; it uses rule card, source clause, page index, spatial ordering, occurrence index, and evidence fingerprinting.
- Changed items list field-level changes for bbox, severity, message, and evidence fields.
- New CLI: `archkg review-diff BEFORE_RUN AFTER_RUN -o AFTER_RUN/review_diff.json`.
- `control_sync` now recognizes `review_diff.json` when present.
- The diff is read-only and does not mutate `issues.json`, `review_state.json`, rule output, or per-sheet preview issues.

## Validation

- `.venv/bin/python -m pytest -q tests/test_review_diff.py`
- `.venv/bin/python -m pytest -q tests/test_review_diff.py tests/test_control_sync.py`
- `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p42/review_diff_before`
- `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p42/review_diff_after`
- `.venv/bin/archkg review-diff tmp/p42/review_diff_before tmp/p42/review_diff_after -o tmp/p42/review_diff_after/review_diff.json`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p42/suite_result_p42_01.json --markdown tmp/p42/suite_result_p42_01.md`
- `.venv/bin/python -m pytest -q`

Result: targeted tests 11 passed; identical-run CLI smoke reported unchanged=12 changed=0 new=0 resolved=0; ruff passed; mypy passed; benchmark suite PASS active=3 pending=1 failed=0 known_gap=1; full pytest 357 passed.

## Next

Move to P42-02: surface `review_diff.json` in Viewer/Studio/workbench so revision status is visible next to issue review state.
