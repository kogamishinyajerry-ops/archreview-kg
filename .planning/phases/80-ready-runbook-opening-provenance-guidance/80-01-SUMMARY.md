# P80-01 Ready Runbook Opening Provenance Guidance Summary

## Result

P80-01 adds optional opening provenance guidance to the ready-runbook. When a
package has weak opening provenance guidance in the copied reviewer checklist,
`handoff_ready_runbook.json` now includes an `optional_review_actions` entry and
`handoff_ready_runbook.md` renders an `Optional Review Guidance` section with:

- the optional action title
- weak coverage reason
- pointer to `artifacts/reviewer_task_checklist.md`
- preview-only boundary warning

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

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_ready_runbook_surfaces_opening_provenance_guidance_without_blocking` failed before implementation with missing `optional_review_actions`.
- GREEN check: the same targeted command passed after implementation: 1 passed, 5 warnings.
- Local targeted regression: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_ready_runbook_surfaces_opening_provenance_guidance_without_blocking tests/test_handoff_package.py::test_handoff_ready_runbook_reports_ready_for_manager_intake tests/test_handoff_package.py::test_handoff_ready_runbook_guides_open_reviewer_checklist tests/test_handoff_package.py::test_handoff_package_adds_opening_provenance_guidance_to_reviewer_checklist` passed: 4 passed, 5 warnings.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_package.py tests/test_handoff_bundle.py tests/test_reviewer_task_checklist.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 46 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 437 passed, 1 skipped, 5 warnings.
