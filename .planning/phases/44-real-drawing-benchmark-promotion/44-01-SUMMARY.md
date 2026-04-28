# P44-01 SUMMARY: Promote Real Full-Set Recognition Benchmark

## Outcome

Promoted the Medfield 9-page real public plan/elevation set from known_gap to active recognition benchmark.

## Implementation Notes

- `build_drawing_understanding` now accepts optional `sheet_graphs` evidence.
- New `merge_sheet_graph_evidence` adds `sheet_graph_summary`, updates aggregate component counts, benchmark signals, and evidence signals, and inserts aggregate inventory rows with `evidence_source=sheet_graphs_count`.
- CLI and Studio pass `sheet_graphs.json` into drawing-understanding generation for new runs.
- The benchmark harness also merges sheet graph evidence when scoring existing run directories.
- Medfield full-set and generated multi-plan fixture artifacts were refreshed to match the new multi-sheet understanding semantics.
- Per-sheet candidate issues remain preview-only; P44 does not change `issues.json`, `review_state.json`, rule evaluation, or compliance aggregation.

## Validation

- `.venv/bin/python -m pytest -q tests/test_viewer_drawing_understanding.py tests/test_viewer_understanding_benchmark.py tests/test_viewer_understanding_benchmark_suite.py`
- `.venv/bin/python -m ruff check archkg/viewer/drawing_understanding.py archkg/viewer/understanding_benchmark.py archkg/cli/main.py archkg/viewer/studio.py tests/test_viewer_drawing_understanding.py tests/test_viewer_understanding_benchmark.py tests/test_viewer_understanding_benchmark_suite.py`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p44/suite_result_p44_01.json --markdown tmp/p44/suite_result_p44_01.md`
- `.venv/bin/archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p43/readiness_after --out tmp/p44/release_readiness_p44_01.json --markdown tmp/p44/release_readiness_p44_01.md`

Result: targeted tests 17 passed; ruff passed; mypy passed; benchmark suite PASS active=4 pending=1 failed=0 known_gap=0; release-readiness smoke returned `demo_ready_with_known_gaps` with blockers=0 warnings=1 active=4 real_active=2 known_gap=0; full pytest 368 passed.

## Next

Resolve the remaining pending suite row, or replace it with a concrete active benchmark, then rerun release readiness.
