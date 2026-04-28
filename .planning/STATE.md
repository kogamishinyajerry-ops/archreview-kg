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
- P39-02 is complete: full CLI and Studio review runs now write `sheet_issues.json`, a per-sheet candidate issue preview decoupled from primary `issues.json` and `review_state.json`.
- P40-01 is complete: understanding benchmark expected specs can now check `sheet_graphs.json` and `sheet_issues.json`, and the packaged suite includes deterministic active case `generated-multi-plan-sheets`.
- P40-02 is complete: pending benchmark suite rows now expose provenance, required artifacts, and promotion rules; the Medfield full 9-page plan/elevation set is registered as a real multi-plan intake gate, not as a passing benchmark.

## Current Phase

P40: Real drawing benchmark expansion.

P40-02 adds a real multi-plan intake gate. The packaged suite now has active=3, pending=2, known_gap=0, failed=0. The new pending real-public row records the artifact and expected-inventory gaps required before promotion to known_gap or active.

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
- Per-sheet issues are preview-only in P39-02; do not claim multi-plan compliance aggregation until issue IDs, review state linkage, and report grouping are explicitly promoted.
- P40-01 uses a deterministic generated multi-plan fixture; it does not replace real public/private multi-plan expected inventory intake.
- P40-02 registers a real full-set intake gate but does not include a full-run expected inventory yet; it is bookkeeping for annotation work, not recognition proof.
- Notion content can lag unless every phase closeout records commit and validation.

## Next Action

Run the real Medfield full plan set or a user-private multi-plan drawing through full review, then author human expected inventory and promote it first to `known_gap` unless all multi-plan artifact checks pass.
