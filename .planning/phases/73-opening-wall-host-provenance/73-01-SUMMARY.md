# P73-01 Opening Wall-Host Provenance Summary

## Result

P73-01 added explicit opening host-wall provenance to the 3D evidence layer.
`door_opening` and `window_opening` objects now include `properties.opening_host`
only when the source graph provides explicit host wall or source-segment fields.

## Boundaries

- No host-wall inference.
- No nearest-wall snapping.
- No wall void boolean subtraction.
- No rule-engine, `issues.json`, or `review_state.json` semantic changes.
- No mandatory IfcOpenShell dependency.

## Verification

- Latest handoff before P74 recorded full validation at commit `e9b6eb3`: 426 passed, 1 skipped, 5 warnings.
