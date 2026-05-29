# P68 3D Layout Model OSS Survey

Date: 2026-04-29

## Conclusion

No reviewed open-source project should be adopted as a direct "arbitrary PDF/raster architectural sheet to review-grade BIM" dependency for ArchReview-KG. The first production slice should remain repo-owned and deterministic: convert existing `sheet_graphs.json` / `entity_graph.json` evidence into a 2.5D navigation model, then export lightweight GLB for reviewer orientation.

This keeps the current truth hierarchy intact:

- 2D extraction artifacts remain source evidence.
- `layout_3d` is derived evidence for spatial understanding.
- Rule-engine results remain unchanged.
- Missing height, thickness, and vertical geometry are explicit assumptions, not inferred facts.

## References

| Project | Link | Useful Idea | Why Not First Hard Dependency |
|---|---|---|---|
| FloorplanTransformation | <https://github.com/art-programmer/FloorplanTransformation> | Raster-to-vector and 3D popup direction | Old stack and not aligned with ArchReview-KG evidence schemas |
| FloorplanToBlender3d | <https://github.com/grebtsew/FloorplanToBlender3d> | Fast floorplan-to-room visualization reference | Blender-centered visualization, not review truth or package-friendly evidence |
| CubiCasa5k | <https://github.com/CubiCasa/CubiCasa5k> | Large floorplan dataset with rich labels | Better future training/evaluation source than immediate runtime dependency |
| HEAT | <https://github.com/woodfrog/heat> | Topology and room-boundary reconstruction research | Neural/model dependency should wait until deterministic graph evidence is mature |
| RoomFormer | <https://github.com/ywyue/RoomFormer> | Room polygon reconstruction from floorplans | Research adapter candidate, not first-stage production path |
| PolyRoom | <https://github.com/3dv-casia/PolyRoom> | Polygonal room reconstruction | Research adapter candidate, not first-stage production path |
| Plan2Scene | <https://github.com/3dlg-hcvc/plan2scene> | Scene generation and indoor 3D context | More scene/texture oriented than compliance evidence oriented |
| IfcOpenShell | <https://github.com/IfcOpenShell/IfcOpenShell> | Future IFC creation and validation bridge | IFC export should follow a stable evidence model rather than lead it |
| trimesh | <https://github.com/mikedh/trimesh> | Simple mesh/GLB export in Python | Suitable for P68 GLB export because it stays lightweight and deterministic |

## Adopted P68 Direction

P68 implements an ArchReview-KG-native `layout_3d.v1` schema and builder:

- Prefer `sheet_graphs.json` to preserve sheet-level plan evidence.
- Fall back to `entity_graph.json` for older runs.
- Generate deterministic primitives: floor slab, room/corridor volumes, wall segments, door openings, stair placeholders, and dimension anchors.
- Write `layout_3d.json`, `layout_3d_summary.md`, and `layout_3d.glb` in full CLI and Studio runs.
- Render status, counts, assumptions, blocked reasons, and GLB links in Viewer/Studio.
- Copy layout artifacts into handoff packages as read-only evidence.

## Deferred Directions

- IFC export via IfcOpenShell after `layout_3d.v1` object semantics stabilize.
- CubiCasa/HEAT/RoomFormer/PolyRoom adapters after the benchmark suite has enough human-reviewed expected inventory to measure recognition gains.
- Door/window opening subtraction, multi-floor stacking, and vertical circulation geometry after the graph layer provides stronger evidence.

## Guardrails

- Do not describe GLB as BIM.
- Do not use default heights/thicknesses as compliance inputs.
- Do not replace 2D source evidence with 3D visualization.
- Do not claim arbitrary complex real drawing support from generated fixtures or one derived layout artifact.
