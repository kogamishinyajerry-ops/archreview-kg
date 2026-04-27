# P37-01 SUMMARY: Rule-Card Draft Authoring Assistant

## Outcome

Implemented a safe, local draft lane for rule-card authoring.

## Implementation Notes

- Added `archkg.schemas.rule_draft` with `rule_card_draft.v1`.
- Draft status is fixed to `draft`; `active` is rejected by schema
  validation.
- Added `archkg.knowledge.rule_authoring` to create a conservative draft
  from an existing `StandardClause`.
- Added CLI:
  `archkg rule-card draft --clause-id GB50096-5.7.2 -o out/rule_card_draft.json`.
- Draft artifacts record:
  - source clause
  - extracted threshold
  - proposed entity inputs
  - applicability
  - ambiguity notes
  - missing evidence
  - proposed tests
- The command never writes active `rule_cards.yaml` and cannot create final
  compliance issues.

## Validation

- `.venv/bin/python -m pytest -q tests/test_rule_card_authoring.py`
- `.venv/bin/python -m pytest -q tests/test_rule_card_authoring.py tests/test_schema_rule_card.py tests/test_knowledge_loader.py tests/test_rules_engine.py`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/python -m pytest -q`

Result: 332 tests passed.

## Next

Decide whether to add a P37-02 reviewed-promotion gate design or enter P38
multi-sheet classification.
