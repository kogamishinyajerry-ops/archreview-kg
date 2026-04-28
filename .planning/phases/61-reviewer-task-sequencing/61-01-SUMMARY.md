# P61-01 Summary: Reviewer Task Sequencing

## Delivered

- Added `archkg.viewer.reviewer_task_sequence` with `reviewer_task_sequence.v1` JSON and Markdown output.
- Wired CLI and Studio runs to generate `reviewer_task_sequence.json` / `.md`.
- Rendered the task sequence in report and Viewer.
- Added task sequence artifacts to handoff packages.
- Added tests for task ordering, missing-artifact degradation, Viewer rendering, raster run output, and handoff copying.
- Updated README, READINESS, CHANGELOG, ROADMAP, and STATE.

## Guardrails

- The task sequence is guidance only.
- It does not confirm issues, mutate `issues.json` or `review_state.json`, promote preview issues, or certify compliance.
- Per-sheet preview tasks remain preview-only and must not be used with `archkg review-state`.

## Validation

- `pytest tests/test_reviewer_task_sequence.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_viewer_studio.py::test_run_pipeline_extracts_walls_from_png tests/test_handoff_package.py::test_handoff_package_copies_review_artifacts_without_mutating_run -q` -> 5 passed.
- `ruff check archkg/viewer/reviewer_task_sequence.py archkg/cli/main.py archkg/viewer/studio.py archkg/viewer/server.py archkg/annotate/report.py tests/test_reviewer_task_sequence.py tests/test_viewer_studio.py tests/test_handoff_package.py` -> passed.
- `mypy archkg/viewer/reviewer_task_sequence.py archkg/cli/main.py archkg/viewer/studio.py archkg/viewer/server.py archkg/annotate/report.py` -> passed.
- `pytest tests/test_reviewer_task_sequence.py tests/test_handoff_package.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_viewer_studio.py::test_run_pipeline_extracts_walls_from_png tests/test_cli_review.py -q` -> 31 passed.
- `ruff check .` -> passed.
- `mypy archkg` -> passed.
- Real multi-page smoke from `samples/generated_complex_sheet_set.pdf` wrote 28 ordered tasks and surfaced the sequence in report, Viewer, JSON, and Markdown.
- Multi-page handoff smoke copied `reviewer_task_sequence.json` / `.md` and `handoff-check` returned `handoff_ready`.
- `archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json` -> PASS active=7 pending=0 failed=0 known_gap=0.
- `archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p54/handoff_run` -> evidence_ready, blockers=0, warnings=0, active=7, real_active=3, known_gap=0.
- `pytest -q` -> 400 passed.
