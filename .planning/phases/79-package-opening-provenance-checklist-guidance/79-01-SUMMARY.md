# P79-01 Package Opening Provenance Checklist Guidance Summary

## Result

P79-01 adds package-local opening provenance guidance to the reviewer checklist.
When `archkg handoff-package` sees weak opening provenance coverage in
`layout_ifc_export.json`, the copied package checklist now gets an
`opening_provenance_guidance` object and the checklist Markdown renders an
`Opening Provenance Guidance` section with:

- source artifact
- coverage counts
- missing semantic / measurement / host-wall signals
- preview-only boundary warning
- package-local mutation policy

The source run checklist is unchanged, and package checklist `items[]` length is
unchanged.

## Boundaries

- No checklist item count or manager readiness changes.
- No source-run mutation.
- No rule-engine, `issues.json`, or `review_state.json` changes.
- No inferred opening provenance.
- No compliance, BIM completeness, or review-grade IFC claim.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_package_adds_opening_provenance_guidance_to_reviewer_checklist` failed before implementation with missing `opening_provenance_guidance`.
- GREEN check: the same targeted command passed after implementation: 1 passed, 5 warnings.
- Local targeted regression: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_package_adds_opening_provenance_guidance_to_reviewer_checklist tests/test_handoff_package.py::test_handoff_package_surfaces_opening_provenance_coverage tests/test_reviewer_task_checklist.py` passed: 4 passed, 5 warnings.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_package.py tests/test_handoff_bundle.py tests/test_reviewer_task_checklist.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 45 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 436 passed, 1 skipped, 5 warnings.
