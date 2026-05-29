# P41-02 SUMMARY: Workbench Action Links

## Outcome

Added structured workbench action links and rendered them in Viewer/Studio plus `report.md`.

## Implementation Notes

- `review_workbench.json` now includes `action_links`.
- Actions cover:
  - source / overlay layers
  - component inventory
  - readiness blockers
  - sheet evidence
  - region candidates
  - candidate issues
  - review state
  - report / clauses
- Viewer/Studio renders the links as workbench click targets.
- `report.md` includes a "工作台动作入口" table.
- The links are navigation only and do not mutate review state.

## Validation

- `.venv/bin/python -m pytest -q tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_review_pipeline.py::test_report_md_contains_clause_text tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m pytest -q tests/test_review_pipeline.py tests/test_viewer_studio.py tests/test_control_sync.py`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p41/action_surface_smoke`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p41/suite_result_p41_02.json --markdown tmp/p41/suite_result_p41_02.md`
- `.venv/bin/python -m pytest -q`

Result: targeted tests passed; touched-file tests 41 passed; ruff passed; mypy passed; CLI smoke wrote action links; benchmark suite PASS with active=3 pending=1 failed=0 known_gap=1; full pytest 344 passed.

## Next

Decide whether P41-03 should implement bounded local review-state operations or improve visual cross-highlighting between workbench actions and source/overlay evidence.
