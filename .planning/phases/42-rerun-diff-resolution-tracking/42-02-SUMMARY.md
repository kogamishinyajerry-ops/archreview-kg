# P42-02 SUMMARY: Viewer Review Diff Surface

## Outcome

Rendered re-run diff status in Viewer/Studio.

## Implementation Notes

- New `archkg.viewer.review_diff` loads `review_diff.json` into a display model with summary rows, per-current-issue status lookup, visible diff rows, and resolved rows.
- Viewer/Studio pass the diff view into the shared result template.
- The workbench panel now includes a "Re-run Diff" card with unchanged / changed / new / resolved counts and sample rows.
- Current-run issue rows show a `Diff ...` pill when the after-run issue appears in `review_diff.json`.
- Missing `review_diff.json` explains that the diff has not been run yet; it does not imply no changes.
- The UI remains read-only and does not mutate `review_state.json`, `issues.json`, rule output, or per-sheet preview issues.

## Validation

- `.venv/bin/python -m pytest -q tests/test_viewer_review_diff.py tests/test_review_diff.py tests/test_viewer_studio.py::test_standalone_viewer_renders_review_diff_status tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- Viewer smoke: re-rendered `tmp/p42/review_diff_after/index.html` and asserted `Re-run Diff`, `Diff 未变化 · unchanged`, and `review_diff.json`.
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p42/suite_result_p42_02.json --markdown tmp/p42/suite_result_p42_02.md`
- `.venv/bin/python -m pytest -q`

Result: targeted tests 12 passed; viewer smoke passed; ruff passed; mypy passed; benchmark suite PASS active=3 pending=1 failed=0 known_gap=1; full pytest 360 passed.

## Next

Move to P43 release readiness gate: define a rubric based on real benchmark evidence, readiness artifacts, issue lifecycle, and known gaps rather than rule count.
