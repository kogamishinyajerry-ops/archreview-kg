# P40-03 SUMMARY: Real Full-Set Known Gap

## Outcome

Promoted the Medfield full 9-page plan/elevation set from pending intake to a scored `known_gap` case.

## Implementation Notes

- Ran full-set review with:
  - `.venv/bin/archkg review tmp/p28-real/medfield-floorplans-elevations.pdf -o tmp/p40/medfield_full_plan_set_run --min-room-area-m2 3.0`
- Committed reduced run artifacts under:
  - `samples/understanding_benchmarks/real/medfield_full_plan_set_run/`
- Added expected spec:
  - `samples/understanding_benchmarks/real/medfield_full_plan_set_expected.json`
- Updated manifest case `medfield-full-plan-set-multi-plan-intake` from `pending_fixture` to `known_gap`.
- Current gap is explicit: primary full-set `drawing_understanding.json` reports `doors=0` and `has_openings=false`, while per-sheet artifacts exist and expose plan pages.

## Validation

- `.venv/bin/python -m pytest -q tests/test_viewer_understanding_benchmark_suite.py::test_benchmark_suite_records_known_gap_without_failing_suite tests/test_viewer_understanding_benchmark_suite.py::test_packaged_suite_manifest_tracks_medfield_active_real_case`
- `.venv/bin/python -m pytest -q tests/test_viewer_understanding_benchmark_suite.py tests/test_cli_understanding_benchmark.py`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p40/suite_result_p40_03.json --markdown tmp/p40/suite_result_p40_03.md`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: packaged suite PASS active=3 pending=1 failed=0 known_gap=1; 344 tests passed. The known-gap score is 0.8333 and failed checks are rooms count, doors count, door semantic kind, openings evidence signal, and has_openings benchmark signal.

## Next

Fix or redesign primary full-set drawing-understanding aggregation so selected plan-sheet openings can be represented without treating per-sheet preview issues as final compliance output.
