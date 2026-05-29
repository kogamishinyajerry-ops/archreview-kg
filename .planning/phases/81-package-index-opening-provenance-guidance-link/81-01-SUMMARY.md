# P81-01 Package Index Opening Provenance Guidance Link Summary

## Result

P81-01 adds package-root static index navigation for ready-runbook optional
opening provenance guidance. When `handoff_ready_runbook.json` carries
`optional_review_actions`, the `Ready-To-Review Runbook` panel in `index.html`
now renders an `Optional Review Guidance` entry with:

- the optional action title
- weak coverage reason
- link to `handoff_ready_runbook.md#optional-review-guidance`
- link to the referenced package-local checklist artifact

The normal `next_actions` list remains empty for packages already ready for
manager intake, and the manager checklist gate remains complete.

## Boundaries

- No required next-action or manager readiness changes.
- No checklist item count changes.
- No source-run mutation.
- No rule-engine, `issues.json`, or `review_state.json` changes.
- No inferred opening provenance.
- No compliance, BIM completeness, or review-grade IFC claim.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_index_links_ready_runbook_opening_provenance_guidance` failed before implementation with missing `Optional Review Guidance` in `index.html`.
- GREEN check: the same targeted command passed after implementation: 1 passed, 5 warnings.
- Local targeted regression: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_index_links_ready_runbook_opening_provenance_guidance tests/test_handoff_package.py::test_handoff_ready_runbook_surfaces_opening_provenance_guidance_without_blocking tests/test_handoff_package.py::test_handoff_ready_runbook_reports_ready_for_manager_intake tests/test_handoff_package.py::test_handoff_ready_runbook_guides_open_reviewer_checklist tests/test_handoff_package.py::test_handoff_package_adds_opening_provenance_guidance_to_reviewer_checklist` passed: 5 passed, 5 warnings.
- `git diff --check` passed.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_package.py tests/test_handoff_bundle.py tests/test_reviewer_task_checklist.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 47 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 438 passed, 1 skipped, 5 warnings.
