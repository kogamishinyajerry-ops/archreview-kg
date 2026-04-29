# P77-01 Bundle Opening Provenance Triage Summary

## Result

P77-01 adds opening provenance triage to `archkg handoff-bundle-index`.
For each handoff package it now reads `opening_provenance` from
`handoff_manifest.json`, surfaces semantic/measurement/host/all-three counts in the
bundle package rows, and adds a summary-level weak-package counter.

Bundle Markdown and HTML now show:

- Total opening provenance counts (`opening_provenance_semantic_count`,
  `opening_provenance_measurement_count`, `opening_provenance_host_count`,
  `opening_provenance_all_three_count`).
- Total weak coverage packages (`opening_provenance_weak_package_count`) where weak
  means missing any required signal.
- Per-package `Opening Provenance` text and `Weak Coverage` columns to support
  manager review dispatch.

The implementation is read-only and does not alter package states or
readiness gates.

## Boundaries

- No rule-engine, `issues.json`, or `review_state.json` changes.
- No explicit or inferred opening semantic/measurement/host inference.
- No wall-void boolean operations.
- No required IfcOpenShell dependency.
- No BIM/review-compliance interpretation of weak coverage.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py`
  failed before implementation and now passes.
- TDD check: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py` passed.
- Local smoke check: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py` passed.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py tests/test_handoff_package.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed.
- `./.venv/bin/python -m pytest -q` passed.

