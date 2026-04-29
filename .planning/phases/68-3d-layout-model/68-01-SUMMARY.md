# P68-01 Evidence 3D Layout Model Summary

Completed: 2026-04-29

## What Changed

- Added `archkg.layout_3d` with `layout_3d.v1` Pydantic schema, deterministic builder, JSON writer, Markdown summary writer, and `trimesh` GLB export.
- Full CLI and Studio review runs now write `layout_3d.json`, `layout_3d_summary.md`, and `layout_3d.glb`.
- Builder prefers `sheet_graphs.json` and falls back to `entity_graph.json`; missing or unsupported geometry returns `blocked` / `partial` states with explicit `blocked_reasons`.
- Modeled first-stage primitives: floor slabs, room volumes, corridor volumes, wall segments, door opening placeholders, stair placeholders, and dimension anchors.
- Viewer/Studio now render a `3D Layout Model` panel with status, counts, assumptions, blocked reasons, and artifact links.
- `review_workbench.json`, control sync snapshots, and handoff packages now include the 3D layout artifacts.
- Documented the P68 OSS research conclusion and project guardrails in README, READINESS, CHANGELOG, ROADMAP, STATE, and `docs/research/2026-04-29-3d-layout-model-oss-survey.md`.

## Boundary

`layout_3d` is a derived evidence/navigation layer. It does not replace the 2D graph, does not mutate rule output, does not confirm issues, and does not claim BIM/IFC correctness. Default floor thickness, wall height/thickness, room height, door height, and stair height are explicit assumptions for visualization only.

## Verification

- `./.venv/bin/python -m ruff check .` -> passed.
- `./.venv/bin/python -m mypy archkg` -> passed.
- `./.venv/bin/python -m mypy tests/test_layout_3d.py` -> passed.
- `./.venv/bin/python -m pytest -q tests/test_layout_3d.py tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_handoff_package.py::test_handoff_package_copies_review_artifacts_without_mutating_run tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_control_sync.py::test_run_snapshot_includes_sheet_classification_artifact` -> 9 passed, 5 warnings.
- CLI smoke: `archkg review samples/sample_clean.pdf -o tmp/p68-layout-smoke.EDurAa --project-meta samples/project_meta_demo.yaml --room-schedule samples/room_schedule_demo.yaml --stair-schedule samples/stair_schedule_demo.yaml` wrote `layout_3d.json` (64 KB), `layout_3d_summary.md` (1.1 KB), and `layout_3d.glb` (34 KB); `trimesh.load(..., force="scene")` read 61 geometry entries.
- `./.venv/bin/python -m pytest -q` -> 415 passed, 5 warnings.
- Notion mirror comment was written to page `34dc6894-2bed-81ca-843e-c26cbffcb6b9`, comment id `351c6894-2bed-81a2-9774-001dde5f3b31`.

## Follow-Up

- Consider `layout.ifc` export via IfcOpenShell once `layout_3d.v1` semantics stabilize.
- Add window/opening semantics only when the graph layer provides explicit source evidence.
- Evaluate CubiCasa/HEAT/RoomFormer/PolyRoom adapters only after real-drawing expected inventory can measure recognition benefit.
