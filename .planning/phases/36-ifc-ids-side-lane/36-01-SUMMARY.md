# P36-01 SUMMARY: IFC/IDS Side Lane Spike

## Outcome

Implemented an optional, independent IFC/IDS validation lane.

## Implementation Notes

- Added `archkg ifc validate --ifc model.ifc --ids requirements.ids -o out/ifc`.
- Added `archkg.ifc.ids_validator` as a thin adapter over
  IfcOpenShell/IfcTester.
- Missing optional dependency modules (`ifcopenshell` / `ifctester`) return
  a clear CLI message and exit code 1; PDF review commands remain available.
- When dependencies are available, validation writes:
  - `ids_report_raw.json`
  - `ifc_validation.json`
  - `ifc_issues.json`
- IFC failure rows are issue-like evidence, but deliberately do not write
  PDF `issues.json`.
- Tests use deterministic generated IFC/IDS fixture files plus fake
  IfcTester modules, so CI does not require heavy global openBIM installs.

## Validation

- `.venv/bin/python -m pytest -q tests/test_ifc_ids.py`
- `.venv/bin/python -m pytest -q tests/test_ifc_ids.py tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`

Result: 327 tests passed.

## Next

Enter P37-01: rule-card authoring / citation assistant. Keep all generated
rule cards in draft state until explicit human review.
