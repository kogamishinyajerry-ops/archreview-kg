# P40-02 SUMMARY: Real Multi-Plan Intake Gate

## Outcome

Added a real multi-plan intake gate to the packaged understanding benchmark suite without promoting it as recognition proof.

## Implementation Notes

- Pending suite rows now preserve optional:
  - `provenance`
  - `required_artifacts`
  - `promotion_rule`
- Added pending case `medfield-full-plan-set-multi-plan-intake`.
- Added provenance file:
  - `samples/understanding_benchmarks/real/medfield_full_plan_set_intake_provenance.json`
- The pending row records the Medfield public 9-page plan/elevation set as a future full-set benchmark target and requires full-run artifacts plus human expected inventory before promotion.

## Validation

- `.venv/bin/python -m pytest -q tests/test_viewer_understanding_benchmark_suite.py::test_benchmark_suite_runs_active_cases_and_tracks_real_pending tests/test_viewer_understanding_benchmark_suite.py::test_packaged_suite_manifest_tracks_medfield_active_real_case`
- `.venv/bin/python -m pytest -q tests/test_viewer_understanding_benchmark_suite.py tests/test_cli_understanding_benchmark.py`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p40/suite_result.json --markdown tmp/p40/suite_result.md`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: packaged suite PASS active=3 pending=2 failed=0 known_gap=0; 344 tests passed.

## Next

Run the real Medfield full plan set or a private complex plan set through full review, author reviewed expected inventory for selected plan sheets, and promote the row to `known_gap` first unless all checks pass.
