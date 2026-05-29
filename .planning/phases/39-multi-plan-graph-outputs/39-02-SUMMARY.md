# P39-02 SUMMARY: Per-Sheet Issue Preview

## Outcome

Implemented a preview artifact for candidate issues grouped by plan sheet.

## Implementation Notes

- Added `archkg.rules.sheet_issues` with `sheet_issues.v1`.
- Full CLI and Studio review runs now write `sheet_issues.json`.
- The artifact evaluates existing rules against every graph in `sheet_graphs.json`.
- Issues are grouped by page and include skipped-rule counts.
- The artifact is marked preview-only and not linked to `review_state.json`.
- Viewer, Studio, standalone `archkg viewer`, and `report.md` render the per-sheet preview summary.
- `archkg control-sync` includes `sheet_issues.json` in run snapshots.
- Primary `issues.json` and `review_state.json` remain unchanged.

## Validation

- `.venv/bin/python -m pytest -q tests/test_sheet_issues.py tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_review_pipeline.py::test_review_writes_sheet_graphs_for_multiple_plan_pages tests/test_review_pipeline.py::test_report_md_contains_clause_text tests/test_control_sync.py::test_run_snapshot_includes_sheet_classification_artifact tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: 343 tests passed.

## Next

Enter P40 benchmark expansion with multi-plan fixtures before promoting per-sheet issue previews into the primary issue lifecycle.
