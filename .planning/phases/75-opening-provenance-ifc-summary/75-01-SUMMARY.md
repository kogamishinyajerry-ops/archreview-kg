# P75-01 Opening Provenance IFC Summary

## Result

P75-01 carried opening provenance coverage into the optional IFC export lane.
`layout_ifc_export.v1` now reports semantic, measurement, host-wall, and
all-three opening coverage, and IFC Viewer data can display the same KPI set as
preview metadata.

Baseline closeout commit: `0510c16 feat(P75-01): add opening provenance to ifc export summary`.

## Boundaries

- IFC export metadata remains preview-only.
- No inferred semantic, measurement, or host-wall provenance.
- No wall void subtraction.
- No rule-engine, `issues.json`, or `review_state.json` changes.
- IfcOpenShell remains optional.

## Verification

P75 was already complete at the start of P76. P76 validation reran the affected
IFC export tests together with handoff and Viewer tests to protect this lane.
