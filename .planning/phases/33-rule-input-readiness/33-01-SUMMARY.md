# P33-01 SUMMARY: Rule-Input Readiness Artifact

## Outcome

Implemented a per-run `rule_input_readiness.json` artifact for full CLI and
Studio review runs.

The artifact covers all 32 packaged rule cards and classifies each rule as:

- `ready`
- `missing_input`
- `low_confidence`
- `manual_only`
- `not_applicable`
- `unsupported_entity`

## Implementation Notes

- Added `archkg.schemas.rule_readiness` for the stable JSON schema.
- Added `archkg.knowledge.run_readiness` to map graph / ProjectMeta /
  skipped applicability / schedule / OCR context to rule readiness.
- Wired full `archkg review` output to write `rule_input_readiness.json`.
- Wired Studio full review runs to preserve the same artifact.
- Left `issues.json` and rule-engine evaluation behavior unchanged.
- Added control-sync artifact discovery for `rule_input_readiness.json`.

## Validation

- `python -m ruff check .`
- `python -m mypy archkg`
- `python -m pytest -q`

Result: 315 tests passed.

## Next

P33-02 should render the artifact in Viewer/Studio so reviewers can inspect
readiness without opening JSON by hand.
