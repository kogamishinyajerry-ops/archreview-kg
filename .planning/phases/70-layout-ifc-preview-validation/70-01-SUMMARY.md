# P70-01 Layout IFC Preview Validation Summary

## What Changed

- `layout_3d.py` now treats explicit graph evidence as dedicated `window_opening` entities (`Door.properties.opening_kind == "window"` / `"window_opening"` or `is_window == true`), while non-explicit entries remain `door_opening`.
- `_ifc_class_for_object` in `layout_exporter` now maps `window_opening` to `IfcWindow`; window-openings are counted separately in `layout_ifc_export` report outputs.
- Regression tests now validate `window_opening` count in fake-module IFC export and include an optional real IfcOpenShell smoke test path guarded by `pytest.importorskip("ifcopenshell")`.
- Repository planning and developer docs were updated to record explicit window-opening semantics, optional dependency boundaries, and P70 validation instructions.

## Verification

- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_layout_3d.py tests/test_ifc_layout_export.py` passed on host.
- `./.venv/bin/python -m pytest -q` passed; `test_ifc_export_layout_cli_real_ifcopenshell_smoke`
  skipped (`ModuleNotFoundError: ifcopenshell`) on this host.
