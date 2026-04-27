# P38-02 SUMMARY: Protected Graph Routing

## Outcome

Implemented protected routing from multi-sheet classification to graph-builder input.

## Implementation Notes

- Added `archkg.ingest.sheet_routing` with `sheet_routing.v1`.
- CLI and Studio full review runs now write `sheet_routing.json`.
- Routing applies only when:
  - the run has multiple pages
  - exactly one page is a high-confidence graph-eligible `plan`
  - every other page is a high-confidence non-plan sheet
- Routing falls back to legacy all-page graph input for single-page runs, classification mismatch, no eligible plan, multiple eligible plans, unknown pages, or low-confidence non-plan pages.
- Viewer, Studio, standalone `archkg viewer`, and `report.md` render the routing decision.
- `archkg control-sync` includes `sheet_routing.json` in run snapshots.

## Validation

- `.venv/bin/python -m pytest -q tests/test_sheet_routing.py tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_review_pipeline.py::test_review_routes_title_first_multi_sheet_pdf_to_plan_page tests/test_review_pipeline.py::test_report_md_contains_clause_text tests/test_control_sync.py::test_run_snapshot_includes_sheet_classification_artifact tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: 340 tests passed.

## Next

Consider P39 multi-plan graph outputs if complex plan sets require more than one graph, or issue export/BCF-like packaging if the review lifecycle becomes the next bottleneck.
