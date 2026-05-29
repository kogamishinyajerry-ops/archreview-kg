# P83-01 Package Optional Guidance Note Summary

## Result

P83-01 adds package-local optional guidance review notes. The new
`archkg handoff-optional-guidance-note` command writes:

- `handoff_optional_guidance_note.json`
- `handoff_optional_guidance_note.md`

The note records reviewer, status, note text, optional guidance actions from
`handoff_ready_runbook.json`, and `candidate_issue_confirmation=false`.
Package `index.html` now renders an `Optional Guidance Review Note` panel.

## Boundaries

- No source-run mutation.
- No candidate issue confirmation.
- No `review_state.json` changes.
- No required next-action, manager-intake, or package-readiness changes.
- No inferred opening provenance.
- No compliance, BIM completeness, or review-grade IFC claim.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_optional_guidance_note_cli_writes_package_local_closeout` failed before implementation because the CLI command did not exist.
- GREEN check: the same targeted command passed after implementation: 1 passed, 5 warnings.
- Local targeted regression: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_optional_guidance_note_cli_writes_package_local_closeout tests/test_handoff_package.py::test_handoff_index_links_ready_runbook_opening_provenance_guidance tests/test_handoff_package.py::test_handoff_ready_runbook_surfaces_opening_provenance_guidance_without_blocking tests/test_handoff_package.py::test_handoff_ready_runbook_reports_ready_for_manager_intake tests/test_handoff_bundle.py::test_handoff_bundle_index_surfaces_package_index_optional_guidance` passed: 5 passed, 5 warnings.
- `git diff --check` passed.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_package.py tests/test_handoff_bundle.py tests/test_reviewer_task_checklist.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 49 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 440 passed, 1 skipped, 5 warnings.
