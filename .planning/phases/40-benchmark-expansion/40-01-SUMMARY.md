# P40-01 SUMMARY: Multi-Plan Benchmark Artifact Checks

## Outcome

Implemented multi-plan artifact checks in the understanding benchmark harness and added a deterministic active suite case.

## Implementation Notes

- `run_understanding_benchmark` now loads optional `sheet_graphs.json` and `sheet_issues.json`.
- Expected specs can check:
  - `sheet_graphs.graph_count`
  - required graph page indexes
  - per-sheet component counts
  - skipped page indexes
  - `sheet_issues.sheet_count`
  - total per-sheet issue count
  - required issue page indexes
  - required rule IDs by page
- Added deterministic generated active case `generated-multi-plan-sheets`.
- Added committed run artifacts:
  - `generated/multi_plan_run/drawing_understanding.json`
  - `generated/multi_plan_run/sheet_graphs.json`
  - `generated/multi_plan_run/sheet_issues.json`
- Packaged suite now has active=3, pending=1, failed=0.

## Validation

- `.venv/bin/python -m pytest -q tests/test_viewer_understanding_benchmark.py::test_understanding_benchmark_scores_sheet_graphs_and_sheet_issues tests/test_viewer_understanding_benchmark_suite.py::test_packaged_suite_manifest_tracks_medfield_active_real_case`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p40/suite_result.json`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: 344 tests passed; packaged suite PASS active=3 pending=1 failed=0 known_gap=0.

## Next

Add a real public or user-private multi-plan case as `known_gap` first, then promote only after reviewed expected inventory is complete.
