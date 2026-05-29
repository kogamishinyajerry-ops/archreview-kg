# ArchReview-KG Project Reframe

Updated: 2026-04-28

## North Star

ArchReview-KG is now planned as an evidence-first intelligent plan review platform.

The product goal is not to make a vision model issue final legal judgments. The goal is to convert drawings, schedules, OCR text, BIM/IFC data, and rule cards into reviewable evidence packages: what the sheet contains, what each rule needs, what evidence exists, what evidence is missing, and which findings a human reviewer has confirmed.

## Strategic Pivot

Before P32, the main risk was expanding rule count or visual recognition faster than the evidence layer could support.

After the intelligent-plan-review landscape research, the new direction is:

1. Treat structured evidence as the product core.
2. Treat rule input readiness as the first gate before compliance claims.
3. Treat sheet regions, schedules, legends, title blocks, and details as separately classified evidence sources.
4. Treat issues as lifecycle objects, not one-time JSON rows.
5. Reuse IFC/IDS/BCF patterns instead of rebuilding the BIM checker ecosystem from scratch.
6. Use LLM/VLM outputs only as draft assistance, never as final violations or ground truth.

## Product Boundaries

ArchReview-KG can:

- Run an end-to-end local review workflow.
- Produce drawing-understanding evidence.
- Track expected inventory benchmarks.
- Report known gaps honestly.
- Generate rule-driven issues where required inputs exist.
- Support human review and feedback loops.

ArchReview-KG must not claim:

- Arbitrary complex construction drawings are fully understood.
- AI-generated observations are final compliance defects.
- Missing rule inputs imply pass.
- A precheck result equals government permit approval.
- Random or generated samples prove real-world readiness.

## Durable Architecture Principles

- Repo/GitHub is the code truth. Notion is a mirrored control plane.
- Every issue must trace to rule card, clause, entity/source evidence, and review state.
- Every rule must declare input requirements before it is treated as runnable.
- Every low-confidence recognition path must produce an explicit uncertainty signal.
- Every benchmark oracle must come from reviewed expected inventory, not from the current model output alone.
- Every new external-standard lane should prefer open standards and existing libraries first.

## Immediate Outcome Target

The next mature workbench should let a reviewer answer five questions for a complex drawing:

1. What sheet or region did the system inspect?
2. What components did it identify, and from which evidence source?
3. Which rules are ready to run on this evidence?
4. Which rules are blocked by missing or low-confidence input?
5. Which findings were confirmed, rejected, or need more information?
