# ArchReview-KG State

Updated: 2026-04-28

## Current Position

Branch: `main`

Latest completed commit before this replan: `d5395c7 docs(P32): research intelligent plan review landscape`

Status:

- P31 completed sheet-region manual cropping and deterministic complex fixture.
- P32 completed intelligent plan review software research.
- P33-01 is complete: full CLI and Studio review runs now write `rule_input_readiness.json` beside `issues.json`.
- P33-02 is implemented in the working tree: Viewer/Studio/report surfaces render the readiness summary and old runs degrade with an explicit missing-readiness warning.

## Current Phase

P33: Rule-input readiness dashboard.

P33 now has both the machine-readable artifact and reviewer-facing surfaces. After validation/commit, the next implementation phase is P34: sheet-region candidate suggestions.

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
- Issue lifecycle can blur candidate findings and confirmed defects if schema naming is loose.
- IFC dependencies may be heavy or optional; P36 must degrade cleanly.
- Notion content can lag unless every phase closeout records commit and validation.

## Next Action

Validate and commit P33-02, then enter P34-01: generate sheet-region candidates with evidence summaries, without default auto-cropping.
