# P45-01 SUMMARY: Clear Packaged Suite Pending Row

## Outcome

Converted the remaining packaged `sample_clean_full` manual toy row into a committed deterministic active benchmark fixture.

## Implementation Notes

- Generated `sample_clean_full_run` from `samples/sample_clean.pdf` with demo project, room, and stair schedules.
- Committed the minimal benchmark artifacts: `drawing_understanding.json`, `sheet_graphs.json`, and `sheet_issues.json`.
- Updated `suite_manifest.json` to use `sample-clean-full-active` with provenance and an explicit toy-scope note.
- Added a packaged-suite release-readiness regression proving that the suite can now reach `evidence_ready` when representative run artifacts are complete.
- Updated README, READINESS, CHANGELOG, ROADMAP, STATE, and GSD config to record the P45 boundary: evidence-ready for benchmarked drawing classes only, not arbitrary real drawing certification.

## Validation

- `.venv/bin/archkg understanding-benchmark tmp/p45/sample_clean_full_run --expect samples/understanding_benchmarks/sample_clean_full.json --out tmp/p45/sample_clean_benchmark.json --markdown tmp/p45/sample_clean_benchmark.md`
- `.venv/bin/python -m pytest -q tests/test_viewer_understanding_benchmark_suite.py tests/test_release_readiness.py`
- `.venv/bin/python -m ruff check archkg tests`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p45/suite_result_p45_01.json --markdown tmp/p45/suite_result_p45_01.md`
- `.venv/bin/archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p45/sample_clean_full_run --out tmp/p45/release_readiness_p45_01.json --markdown tmp/p45/release_readiness_p45_01.md`
- `.venv/bin/python -m pytest -q`

Result: single-case benchmark PASS score=1.00; targeted tests 14 passed; ruff passed; mypy passed; packaged benchmark suite PASS active=5 pending=0 failed=0 known_gap=0; release-readiness smoke returned `evidence_ready` with blockers=0 warnings=0 active=5 real_active=2 known_gap=0; full pytest 369 passed.

## Next

Start the next maturity slice from a real-drawing value point: either add another reviewed real complex benchmark, or promote a bounded per-sheet preview issue review bridge without merging preview issues into primary rule output.
