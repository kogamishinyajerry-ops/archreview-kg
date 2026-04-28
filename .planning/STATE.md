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
- P40-03 is complete: the Medfield full 9-page plan/elevation set now has a committed reduced full-run artifact snapshot and a `known_gap` expected spec. Packaged suite is active=3, pending=1, known_gap=1, failed=0.
- P41-01 is complete: full CLI and Studio runs now write `review_workbench.json`, while reports and Viewer/Studio render a workbench overview that summarizes evidence readiness without changing rule output.
- P41-02 is complete: `review_workbench.json` now includes structured action links for source/overlay, component inventory, readiness blockers, sheet evidence, region candidates, candidate issues, review state, and report/clauses.
- P41-03 is complete: `archkg review-state` now performs bounded single-issue review-state updates for primary `issues.json` issues, refreshes `review_workbench.json`, and leaves `issues.json` / per-sheet preview issues / rule output unchanged.
- P41-04 is complete: Viewer/Studio can focus first-page primary issue bboxes on source, entity overlay, and annotated previews from the issue list without changing rule output or review state.
- P42-01 is complete: `archkg review-diff` writes read-only `review_diff.json` artifacts comparing two runs' primary `issues.json` candidates as unchanged, changed, new, or resolved without using generated issue/entity IDs.
- P42-02 is complete: Viewer/Studio now load `review_diff.json` and render diff status in the workbench and issue list while keeping the artifact read-only.
- P43-01 is complete: `archkg release-readiness` evaluates benchmark suite evidence and representative run artifacts into `not_ready`, `demo_ready_with_known_gaps`, or `evidence_ready` without using rule count as the maturity metric.
- P44-01 is complete: `drawing_understanding.json` can merge `sheet_graphs.json` aggregate counts as multi-sheet recognition evidence, promoting the Medfield full 9-page real public plan/elevation set from known_gap to active benchmark.
- P45-01 is complete: the remaining `sample_clean_full` manual toy suite row is now a committed active fixture, allowing packaged release-readiness to reach `evidence_ready` when representative run artifacts are complete.
- P46-01 is complete: full review runs now write reviewer onboarding and quickstart artifacts, and Viewer/report render a first-hour path for novice plan-review engineers.
- P47-01 is complete: full CLI and Studio review runs now write `sheet_issue_review_queue.json`, a bounded per-sheet preview review bridge that stays separate from primary `issues.json` and `review_state.json`.
- P48-01 is complete: `archkg handoff-package` now builds a read-only handoff package with manifest, summary, and copied review artifacts outside the source run.
- P49-01 is complete: `archkg handoff-check` now validates handoff package schema, copy-only policy, required artifacts, copied files, and boundary warnings into `handoff_package_quality.v1`.
- P50-01 is complete: `archkg handoff-signoff` now writes package-local reviewer signoff JSON/Markdown notes without mutating the source run.
- P51-01 is complete: handoff packages now include a package-root static `index.html`, and handoff quality/signoff commands refresh that browser entry.
- P52-01 is complete: `archkg handoff-manager-checklist` now writes package-local manager checklist JSON/Markdown and refreshes the static package index.
- P53-01 is complete: `archkg handoff-archive-manifest` now writes package-local archive manifest JSON/Markdown with SHA-256 file entries and a deterministic package digest.
- P54-01 is complete: `archkg handoff-archive-verify` now verifies received packages against archive manifests and reports `archive_verified` or `archive_drift`.
- P55-01 is complete: the active understanding benchmark suite now includes Medfield A-2 Second Floor Plan and a generated complex mixed-sheet set, bringing packaged suite coverage to active=7, real_active=3, generated_active=3.
- P56-01 is complete: Viewer/Studio issue focus now maps primary issue bboxes by `page_index`; first-page issues still highlight on the preview layer, while non-first-page issues show the correct page and route reviewers to the PDF instead of being projected onto page 0.
- P57-01 is complete: Viewer/Studio now write `preview_pages.json` plus multi-page source/annotated PNG page sets, render page-switch controls, and focus non-first-page issues directly on their corresponding source/annotated preview page.
- P58-01 is complete: `archkg handoff-package` now copies `preview_pages.json`, `source.pdf`, annotated/source preview PNGs, and every page image referenced by `preview_pages.json`; missing referenced preview assets become package blockers.
- P59-01 is complete: Viewer/Studio now render entity overlay preview pages for each graph-backed sheet, record them in `preview_pages.json`, and preserve those overlay page assets through handoff packaging.
- P60-01 is complete: `archkg handoff-bundle-index` now scans a directory of handoff packages and writes bundle-level JSON/Markdown/HTML summaries without mutating individual packages or source runs.
- P61-01 is complete: full CLI and Studio runs now write `reviewer_task_sequence.json` / `.md`, report and Viewer render the ordered review queue, and handoff packages include the sequence as entry evidence.
- P62-01 is complete: full CLI and Studio runs now derive `reviewer_task_checklist.json` / `.md` from the ordered queue, report and Viewer render the fillable checklist seed, and handoff packages include it as entry evidence.

## Current Phase

P62: Reviewer task checklist seed.

P62 is complete. Novice reviewers now get both an ordered task queue and a fillable checklist seed for reviewer_status, notes, checked evidence, and unresolved risks.

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
- P44-01 promotes one real full-set recognition benchmark, but aggregation is count-level evidence; per-sheet candidate issues still do not enter primary `issues.json` or `review_state.json`.
- P41-01 workbench summary is derived from current artifacts; if future artifacts are added, the summary must be extended or it can drift.
- P41-03 direct review-state operations can still leave pre-rendered HTML stale until the viewer is re-rendered; the command refreshes `review_workbench.json`, but static `index.html` regeneration remains a separate user/viewer step.
- P59 renders entity overlay pages only for graph-backed sheets; pages without a routed graph still rely on source/annotated/PDF review and must not be described as fully recognized.
- P42-01 duplicate matching is deterministic but still heuristic for multiple same-rule same-page candidates; it uses spatial/evidence ordering because generated entity IDs are not stable across runs.
- `review_diff.json` is not a compliance proof and does not resolve human review states automatically.
- P42-02 renders missing diff as "not run yet"; reviewers must still inspect diff rows before marking review_state items resolved or superseded.
- P43-P45 only gate evidence currently represented in the benchmark suite and run directory. They do not certify arbitrary complex real drawings; `evidence_ready` means constrained pilot readiness for benchmarked drawing classes only.
- P46 onboarding artifacts are guidance-only; they do not confirm issues, mutate rule output, or certify compliance.
- P47 preview queue artifacts are guidance-only and preview-only; their `preview_id` values are not valid `archkg review-state` targets.
- P48 handoff packages copy existing artifacts only; a complete package is still not a compliance certificate and missing artifacts must be treated as handoff risk.
- P49 handoff package quality validates package completeness and boundaries only; it is not a release-readiness or drawing-compliance gate.
- P50 reviewer signoff notes are package-local handoff notes only; `ready` does not mean the drawing is compliant.
- P51 static handoff `index.html` is a navigation surface only; it does not create new evidence or replace source-run artifacts.
- P52 manager checklist status is package-intake status only; `manager_ready` does not mean the drawing is compliant.
- P53 archive manifest status is transfer-integrity evidence only; `archive_manifest_ready` does not mean the drawing is compliant.
- P54 archive verification status is checksum alignment only; `archive_verified` does not mean any issue is confirmed or the drawing is compliant.
- P55 adds recognition benchmarks only; Medfield A-2 and generated mixed-sheet passing cases do not prove arbitrary real drawing compliance or multi-sheet issue aggregation.
- P56 page-aware focus is a reviewer navigation aid only; it does not create new issues, change review state, or certify compliance.
- P57/P59 preview pages are visual navigation artifacts only; they do not create new detection evidence, mutate issue state, or certify entity recognition accuracy.
- P58 strengthens handoff completeness for preview assets only; complete copied visuals still do not certify issue correctness or drawing compliance.
- P59 multi-page entity overlays improve reviewer orientation only; they do not promote per-sheet preview issues into primary `issues.json`.
- P60 bundle indexes summarize package-local handoff state only; `bundle_ready` is not a compliance certificate, and bundle generation must not mutate single-package artifacts.
- P61 reviewer task sequencing is order guidance only; it does not confirm issues, mutate `review_state.json`, or promote preview issues into primary lifecycle.
- P62 reviewer task checklist is a fillable seed only; checked rows are not issue confirmations unless the reviewer separately updates primary `review_state.json`.
- Notion content can lag unless every phase closeout records commit and validation.

## Next Action

Move beyond P62 by adding package-level reviewer checklist import/export or a richer static manager view that highlights open checklist risk across bundles.
