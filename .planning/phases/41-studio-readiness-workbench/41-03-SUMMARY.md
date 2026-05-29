# P41-03 SUMMARY: Bounded Review-State Operations

## Outcome

Added bounded local review-state updates for primary candidate issues.

## Implementation Notes

- New `archkg review-state <run_dir> <issue_id> --status ...` command updates `review_state.json`.
- Updates are accepted only when `issue_id` exists in primary `issues.json`.
- `issues.json`, rule output, and per-sheet preview issues remain unchanged.
- `review_workbench.json` now includes `review_state_operations` with command templates.
- Viewer/Studio and `report.md` render those operation templates.
- `review-state` refreshes `review_workbench.json` after writing review state.

## Validation

- `.venv/bin/python -m pytest -q tests/test_review_state.py tests/test_feedback.py::test_cli_review_state_updates_single_issue_without_mutating_issues tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_review_pipeline.py::test_report_md_contains_clause_text tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning`
- `.venv/bin/python -m pytest -q tests/test_review_state.py tests/test_feedback.py tests/test_review_pipeline.py tests/test_viewer_studio.py tests/test_control_sync.py`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p41/review_state_ops_smoke`
- `.venv/bin/archkg review-state tmp/p41/review_state_ops_smoke <issue_id> --status rejected --reviewer Codex --note "P41-03 smoke"`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p41/suite_result_p41_03.json --markdown tmp/p41/suite_result_p41_03.md`
- `.venv/bin/python -m pytest -q`

Result: targeted tests 9 passed; touched-file tests 55 passed; ruff passed; mypy passed; CLI smoke updated `review_state.json` and refreshed `review_workbench.json` without mutating `issues.json`; benchmark suite PASS active=3 pending=1 failed=0 known_gap=1; full pytest 348 passed.

## Next

Continue P41 with source-preview cross-highlighting, or move to P42 rerun diff/resolution tracking once the workbench flow is sufficient for repeated manual review.
