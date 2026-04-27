# ArchReview-KG State

Updated: 2026-04-28

## Current Position

Branch: `main`

Latest completed commit before this replan: `d5395c7 docs(P32): research intelligent plan review landscape`

Status:

- P31 completed sheet-region manual cropping and deterministic complex fixture.
- P32 completed intelligent plan review software research.
- P33-01 is complete: full CLI and Studio review runs now write `rule_input_readiness.json` beside `issues.json`.
- P33-02 is complete: Viewer/Studio/report surfaces render the readiness summary and old runs degrade with an explicit missing-readiness warning.
- P34-01 is complete: full CLI and Studio review runs now write `sheet_region_candidates.json` and render candidate regions without default auto-cropping.
- P34-02 is complete: candidate boxes are rendered into `sheet_region_candidates_overlay.png` and shown in the result page.
- P35-01 is complete: full CLI and Studio review runs now write `review_state.json`, while `issues.json` stays the rule-engine candidate output.
- P36-01 is complete: `archkg ifc validate` provides an optional IFC/IDS side lane with separate artifacts and clean missing-dependency degradation.
- P37-01 is implemented in the working tree: `archkg rule-card draft` writes draft-only rule-card authoring artifacts and does not mutate active `rule_cards.yaml`.

## Current Phase

P37: Rule-card authoring and citation assistant.

P37-01 now adds a safe local draft lane. It writes `rule_card_draft.v1` JSON with source clause, extracted threshold, proposed inputs, ambiguity notes, missing evidence, and proposed tests. Status is fixed to `draft`; promotion to active rule cards remains out of scope.

## Key Decisions

- Repo truth remains authoritative over Notion.
- Notion should mirror state and phase intent, not replace repo planning.
- Rule count is no longer the primary progress metric.
- Real drawing maturity is measured by reviewed expected inventory, per-run readiness, and issue lifecycle quality.
- LLM/VLM outputs are assistant drafts only.
- IFC/IDS support is a side lane, not a replacement for PDF evidence extraction.

## Open Risks

- Static readiness tiers can still drift from actual run evidence if future builder inputs are added without extending readiness coverage and tests.
- Sheet-region candidates can cause silent false negatives if automatic cropping becomes default too early.
- Feedback/report editing can drift if legacy `open` status is not normalized; keep compatibility tests around `open -> candidate`.
- Real IfcTester JSON shapes can vary by installed version; keep adapter tests around raw-report normalization and issue mapping.
- Rule-card draft heuristics are intentionally conservative; ambiguous clauses need human review and may require split/branch rules.
- Notion content can lag unless every phase closeout records commit and validation.

## Next Action

Validate and commit P37-01, then decide whether to enter P38 multi-sheet classification or add a P37-02 reviewed-promotion gate design.
