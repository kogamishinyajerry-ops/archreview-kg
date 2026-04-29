# P72-01 Opening Measurement Provenance Summary

## Result

P72-01 adds explicit opening measurement provenance to the 3D evidence layer. `door_opening` and `window_opening` objects now include `properties.opening_measurement` only when the source graph provides explicit fields:

- `Door.width_m`
- `Door.properties.height_m`
- `Door.properties.sill_height_m`
- `Door.properties.head_height_m`

When explicit `height_m` exists, the 3D preview object uses that height and the corresponding default opening-height assumption is not applied to that object. Missing fields still use existing explicit visualization assumptions.

## Boundaries

- Opening measurements are preview provenance only.
- They are not rule-engine facts, compliance findings, wall-void geometry, fire/smoke/window safety evidence, or design-grade BIM data.
- No neural reconstruction, window inference, boolean void subtraction, multi-floor stacking, or mandatory IfcOpenShell dependency was added.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_layout_3d.py` failed before implementation on missing explicit height handling and missing Viewer measurement surface.
- GREEN check: `./.venv/bin/python -m pytest -q tests/test_layout_3d.py` passed after implementation.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_layout_3d.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_ifc_layout_export.py` passed: 14 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 423 passed, 1 skipped, 5 warnings.
