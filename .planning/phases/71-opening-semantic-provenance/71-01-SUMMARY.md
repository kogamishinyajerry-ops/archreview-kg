# P71-01 Opening Semantic Provenance Summary

Completed: 2026-04-29

## What Changed

- `layout_3d` now writes `properties.opening_semantic` on `door_opening` and `window_opening` objects.
- Default Door entities keep `door_opening` semantics with provenance `entity_type=Door` and `explicit=false`.
- Explicit window evidence keeps `window_opening` semantics with provenance showing the source property (`opening_kind` or `is_window`) and source value.
- `layout_3d_summary.md` now includes an `Opening Semantics` section with door/window opening counts and boundary text.
- Viewer/Studio now render Opening Semantics counts and sample provenance rows in the 3D Layout Model panel.
- README, READINESS, CHANGELOG, ROADMAP, and STATE now record the P71 boundary.

## Boundary

Opening semantic provenance is audit metadata only. It explains why a graph-derived 3D preview object is shown as `door_opening` or `window_opening`; it does not create wall void geometry, perform neural recognition, promote preview evidence into `issues.json`, or change compliance conclusions.

## Verification

- `./.venv/bin/python -m ruff check .` -> passed.
- `./.venv/bin/python -m mypy archkg` -> passed.
- `./.venv/bin/python -m pytest -q tests/test_layout_3d.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_ifc_layout_export.py` -> 12 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` -> 421 passed, 1 skipped, 5 warnings.

The skipped test is the optional real IfcOpenShell smoke path, skipped because this host does not have `ifcopenshell` installed.

## Follow-Up

- Add measured opening dimensions only when the graph evidence carries explicit source fields.
- Add wall-host references only when the 2D graph provides explicit wall/opening linkage.
- Keep IfcOpenShell optional and do not treat IFC preview as review-grade BIM.
