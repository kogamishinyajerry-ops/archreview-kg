# P74-01 Opening Provenance Consistency Summary

## Result

P74-01 adds Opening Provenance Consistency to the 3D evidence layer. The
`layout_3d` summary now counts openings with:

- semantic provenance
- at least one explicit measurement field
- explicit host-wall provenance
- all three preview provenance surfaces

Viewer/Studio now exposes `opening_provenance_consistency` with per-opening
samples and `missing_provenance` prompts.

## Boundaries

- Coverage only; missing signals are review prompts, not failures.
- No inferred measurements, host walls, or opening semantics.
- No wall void boolean operations.
- No rule-engine, `issues.json`, or `review_state.json` semantic changes.
- No BIM completeness claim.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_layout_3d.py` failed before implementation on missing summary keys and missing Viewer consistency data.
- GREEN check: `./.venv/bin/python -m pytest -q tests/test_layout_3d.py` passed after implementation: 14 passed, 5 warnings.
- Local affected Studio check: `./.venv/bin/python -m pytest -q tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_layout_3d.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 19 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 428 passed, 1 skipped, 5 warnings.
