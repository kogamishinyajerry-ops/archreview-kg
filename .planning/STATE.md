# ArchReview-KG State

Updated: 2026-04-28

## Current Position

Branch: `main`

Latest completed commit before this replan: `d5395c7 docs(P32): research intelligent plan review landscape`

Status:

- P31 completed sheet-region manual cropping and deterministic complex fixture.
- P32 completed intelligent plan review software research.
- Current turn starts the post-P32 strategic pivot into an evidence-first plan review platform.

## Current Phase

P33: Rule-input readiness dashboard.

P33 is the next implementation phase because it turns the P32 research conclusion into the first concrete workbench capability: every rule must tell the user whether it is runnable on the current evidence.

## Key Decisions

- Repo truth remains authoritative over Notion.
- Notion should mirror state and phase intent, not replace repo planning.
- Rule count is no longer the primary progress metric.
- Real drawing maturity is measured by reviewed expected inventory, per-run readiness, and issue lifecycle quality.
- LLM/VLM outputs are assistant drafts only.
- IFC/IDS support is a side lane, not a replacement for PDF evidence extraction.

## Open Risks

- Static readiness tiers may drift from actual run evidence unless P33 persists per-run readiness.
- Sheet-region candidates can cause silent false negatives if automatic cropping becomes default too early.
- Issue lifecycle can blur candidate findings and confirmed defects if schema naming is loose.
- IFC dependencies may be heavy or optional; P36 must degrade cleanly.
- Notion content can lag unless every phase closeout records commit and validation.

## Next Action

Execute P33-01.

Start by adding a run-level readiness artifact that maps current graph/project/schedule/OCR evidence to each rule card's required inputs without changing rule-engine issue behavior.
