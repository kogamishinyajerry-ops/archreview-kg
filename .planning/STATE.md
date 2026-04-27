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
- P37-01 is complete: `archkg rule-card draft` writes draft-only rule-card authoring artifacts and does not mutate active `rule_cards.yaml`.
- P38-01 is complete: full CLI and Studio review runs now write `sheet_classification.json`, and Viewer/report render it with explicit missing-artifact degradation.
- P38-02 is complete: full CLI and Studio review runs now write `sheet_routing.json`, and protected graph routing selects a single confident plan page only when fallback guards pass.
- P39-01 is complete: full CLI and Studio review runs now write `sheet_graphs.json`, with one independent graph per high-confidence plan sheet.

## Current Phase

P39: Multi-plan graph outputs.

P39-01 adds a separate multi-plan graph evidence artifact. It builds independent per-sheet graphs for every high-confidence plan page, skips non-plan or low-confidence sheets with reasons, and leaves primary `entity_graph.json` plus rule-engine issue output unchanged.

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
- Sheet routing is still page-level and conservative; multiple plan pages need future multi-graph support before automatic per-sheet graph outputs are trusted.
- Per-sheet graphs are evidence only in P39-01; do not claim multi-plan compliance aggregation until rule evaluation, issue IDs, and report grouping are explicitly designed.
- Notion content can lag unless every phase closeout records commit and validation.

## Next Action

Enter P39-02 per-sheet issue evaluation or P40 benchmark expansion.
