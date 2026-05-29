# P38-01 SUMMARY: Advisory Multi-Sheet Classification Artifact

## Outcome

Implemented an advisory multi-sheet classification layer for full CLI and Studio review runs.

## Implementation Notes

- Added `archkg.ingest.sheet_classification` with `sheet_classification.v1`.
- Full review runs now write `sheet_classification.json` beside `issues.json`, `drawing_understanding.json`, `rule_input_readiness.json`, and sheet-region artifacts.
- Classifications include:
  - page index
  - sheet type
  - confidence
  - advisory graph eligibility
  - reason
  - evidence texts
  - primitive counts
- Viewer, Studio, standalone `archkg viewer`, and `report.md` render the same classification payload.
- Legacy runs without the artifact show an explicit missing-classification warning.
- `archkg control-sync` includes the artifact in run snapshots.
- This phase intentionally does not auto-skip pages or mutate `entity_graph.json`.

## Validation

- `.venv/bin/python -m pytest -q tests/test_sheet_classification.py tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_review_pipeline.py::test_report_md_contains_clause_text tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_control_sync.py::test_run_snapshot_includes_sheet_classification_artifact`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: 336 tests passed.

## Next

Enter P38-02: protected graph routing for pages classified as graph-eligible, with false-negative guards and legacy behavior fallbacks.
