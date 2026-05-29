# P33-02 SUMMARY: Readiness Viewer and Report Surface

## Outcome

Implemented reviewer-facing readiness rendering for the P33-01 artifact.

## Implementation Notes

- Added `archkg.viewer.rule_readiness` to load and summarize
  `rule_input_readiness.json` for UI/report presentation.
- Studio pre-rendered `index.html` now shows a "规则输入就绪度" panel.
- Standalone `archkg viewer` re-renders the same panel from run artifacts.
- `report.md` now includes a compact readiness section with status counts,
  input/source grouping, and non-ready examples.
- Old run directories without `rule_input_readiness.json` still render with
  an explicit "缺失 readiness 不代表通过" warning.
- `issues.json` and issue schema remain unchanged.

## Validation

- `python -m ruff check .`
- `python -m mypy archkg`
- `python -m pytest -q`

Result: 316 tests passed.

## Next

P34-01 should generate sheet-region candidate suggestions with evidence
summaries, while keeping manual confirmation before crop application.
