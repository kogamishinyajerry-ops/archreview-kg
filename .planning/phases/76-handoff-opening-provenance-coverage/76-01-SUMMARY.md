# P76-01 Handoff Opening Provenance Coverage Summary

## Result

P76-01 surfaces opening provenance coverage in handoff packages. When
`layout_ifc_export.json` includes `opening_provenance`, `archkg
handoff-package` now writes the same semantic, measurement, host-wall, and
all-three counts into:

- `handoff_manifest.json`
- `handoff_summary.md`
- package-root `index.html`

The UI text keeps the coverage preview-only: missing signals are review prompts,
not compliance failures.

## Boundaries

- No rule-engine, `issues.json`, or `review_state.json` changes.
- No host-wall, semantic, or measurement inference.
- No wall void boolean operations.
- No BIM completeness or review-grade IFC claim.
- No required IfcOpenShell dependency.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_package_surfaces_opening_provenance_coverage` failed before implementation with missing `opening_provenance`.
- GREEN check: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py::test_handoff_package_surfaces_opening_provenance_coverage` passed after implementation.
- Local handoff regression: `./.venv/bin/python -m pytest -q tests/test_handoff_package.py` passed: 31 passed, 5 warnings.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_package.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 37 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 430 passed, 1 skipped, 5 warnings.
