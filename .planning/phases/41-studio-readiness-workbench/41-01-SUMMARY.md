# P41-01 SUMMARY: Review Workbench Summary Artifact

## Outcome

Added `review_workbench.json` and rendered a "审图工作台总览" section in report and Viewer/Studio surfaces.

## Implementation Notes

- New module: `archkg/viewer/review_workbench.py`.
- Full CLI review writes `review_workbench.json`.
- Studio full review writes `review_workbench.json`.
- Studio inspect-only writes a partial workbench summary.
- Standalone viewer loads the workbench artifact and degrades with a missing-artifact warning for old runs.
- `report.md` includes a workbench overview table before rule readiness.
- `control-sync` now tracks `review_workbench.json` as a key artifact.

## Validation

- `.venv/bin/python -m pytest -q tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_review_pipeline.py::test_report_md_contains_clause_text tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_control_sync.py::test_run_snapshot_includes_sheet_classification_artifact`
- `.venv/bin/python -m pytest -q tests/test_review_pipeline.py tests/test_viewer_studio.py tests/test_control_sync.py`
- `.venv/bin/python -m ruff check archkg/viewer/review_workbench.py archkg/cli/main.py archkg/viewer/studio.py archkg/viewer/server.py archkg/annotate/report.py tests/test_review_pipeline.py tests/test_viewer_studio.py tests/test_control_sync.py`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: targeted tests passed; touched-file tests 41 passed; ruff passed; mypy passed; full suite 344 passed.

## Next

Continue P41 by turning the workbench overview into an action surface: cross-link source preview, candidate regions, component inventory, readiness blockers, candidate issues, and review-state actions.
