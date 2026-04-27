# P35-01 SUMMARY: Issue Lifecycle and Review State

## Outcome

Implemented a separate review-state layer for rule-engine candidate issues.

## Implementation Notes

- Added `archkg.schemas.review_state` and `archkg.review_state`.
- CLI and Studio full review runs now write `review_state.json` beside
  `issues.json`.
- `issues.json` remains rule-engine candidate evidence and does not carry
  reviewer/status fields.
- `report.md`, Studio pre-rendered `index.html`, and standalone
  `archkg viewer` render review lifecycle status.
- `archkg feedback` now updates both `feedback.yaml` and
  `review_state.json`.
- Legacy report rows with `status=open` are normalized to `candidate`.
- Supported lifecycle states:
  `candidate`, `confirmed`, `rejected`, `needs_info`, `resolved`,
  `superseded`.

## Validation

- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: 324 tests passed.

## Next

Decide whether P35 needs a second cross-run supersession workflow plan.
If not, enter P36-01: IFC/IDS side lane with optional dependencies and
clean degradation.
