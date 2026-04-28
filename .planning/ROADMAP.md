# ArchReview-KG Roadmap After P32

Updated: 2026-04-28

## Milestone M2: Evidence-First Plan Review Platform

Goal: make the workbench trustworthy on complex drawings before widening compliance claims.

### P33: Rule-Input Readiness Dashboard

Purpose: turn static rule coverage into per-run rule readiness.

Deliverables:

- `rule_input_readiness.json` artifact for every review run.
- Viewer/Studio readiness panel.
- Report section that distinguishes ready, missing input, low confidence, manual-only, and not applicable.
- Tests proving missing input cannot be represented as pass.

Exit gate:

- All 32 shipped rule cards appear in the readiness artifact.
- Existing rule-engine issue output remains behaviorally unchanged.
- CLI, Studio, and standalone viewer can read the same artifact.

### P34: Sheet-Region Candidate Suggestions

Purpose: stop asking users to hand-enter crop regions before the system can propose candidate design/title/schedule/legend areas.

Deliverables:

- `sheet_region_candidates.json` with design-region, title-block, schedule, legend, and excluded-text summaries.
- Candidate display in Studio.
- No automatic cropping by default.

Exit gate:

- Existing manual `--sheet-region` remains authoritative.
- Candidate suggestions can be reviewed without mutating graph input.
- Generated-complex-titleblock benchmark records candidate evidence.

### P35: Issue Lifecycle and Review State

Purpose: move from one-shot findings to reviewable issue history.

Deliverables:

- Backward-compatible issue lifecycle schema.
- Review states: `candidate`, `confirmed`, `rejected`, `needs_info`, `resolved`, `superseded`.
- Local review-state import/export.
- Report and viewer surface for review state.

Exit gate:

- Old `issues.json` continues to validate.
- Rule engine still produces candidates only.
- Human review state is stored separately or explicitly layered.

### P36: IFC/IDS Side Lane

Purpose: reuse openBIM checking rather than hand-rolling all model-validation logic.

Deliverables:

- Independent `archkg ifc validate --ifc model.ifc --ids spec.ids` spike.
- IfcOpenShell/IfcTester-backed validation where dependency is available.
- IDS failure mapping to ArchReview-KG issue-like evidence rows.
- Minimal IFC/IDS fixture and tests.

Exit gate:

- PDF review pipeline remains decoupled.
- Missing optional IFC dependency degrades with a clear message.
- No claim that IFC validation replaces drawing recognition.

### P37: Rule-Card Authoring and Code-Citation Assistant

Purpose: use AI/retrieval only for draft authoring and citation support.

Deliverables:

- Draft rule-card authoring artifact format.
- `draft / reviewed / active` lifecycle for generated rule-card candidates.
- Citation/evidence report that names source clause, parsed threshold, ambiguity, and required entity inputs.

Exit gate:

- Drafts never enter active `rule_cards.yaml` without explicit review.
- Assistant output cannot create final compliance issues.

## Milestone M3: Complex Drawing Understanding

Goal: handle larger real sheet sets with better source classification and benchmark coverage.

### P38: Multi-Sheet Classification

- Classify architectural plan, detail, elevation, schedule, title, legend, and unknown sheets.
- Route only eligible regions into graph building.

### P39: Multi-Plan Graph Outputs

- Build a separate graph for each high-confidence plan sheet.
- Keep primary `entity_graph.json` and rule-engine output stable until aggregation semantics are explicit.
- Surface per-sheet graph counts, skipped-page reasons, and per-sheet issue preview in Viewer/Studio/report.

### P40: Real Drawing Benchmark Expansion

- Expand active/known_gap suite to at least five reviewed complex cases.
- Separate real public PDFs, deterministic generated PDFs, and user-private fixtures.
- Include multi-sheet artifact checks for `sheet_graphs.json` and `sheet_issues.json`.
- Track real multi-plan intake gates with provenance, required artifacts, and promotion rules before any case is counted as active.

## Milestone M4: Review Workbench

Goal: make the tool useful for repeated human review, not just CLI artifacts.

### P41: Studio Readiness Workbench

- Unify source preview, region candidates, component inventory, rule readiness, issues, and review state.
- Start with `review_workbench.json` as a non-mutating run summary before adding reviewer actions.
- Add action links that navigate from the workbench to evidence panels before implementing any state-changing review controls.
- Add bounded local review-state operations that update only `review_state.json` for primary `issues.json` issue IDs and never mutate rule output or per-sheet preview issues.
- Add first-page issue-to-preview cross-highlighting so reviewers can jump from primary issues to source/overlay/annotated visual evidence.

### P42: Re-Run Diff and Resolution Tracking

- Compare two runs and mark issues as unchanged, changed, resolved, or new.
- P42-01 complete: `archkg review-diff` writes read-only `review_diff.json` over primary `issues.json` candidates without relying on generated issue/entity IDs.
- P42-02 complete: Viewer/Studio/workbench render diff summaries and per-current-issue status pills without auto-mutating `review_state.json`.

### P43: Release Readiness Gate

- Publish a readiness rubric based on real benchmark evidence, not rule count.
- P43-01 complete: `archkg release-readiness` evaluates suite status, active real benchmark coverage, representative run artifacts, known gaps, pending rows, and generated-heavy proof limits into `not_ready`, `demo_ready_with_known_gaps`, or `evidence_ready`.

### P44: Real Drawing Benchmark Promotion

- Reduce release-readiness warnings by promoting real drawing cases only when reviewed expected inventory passes.
- P44-01 complete: multi-sheet `drawing_understanding.json` merges count-level `sheet_graphs.json` evidence, promoting Medfield full-set from known_gap to active while keeping per-sheet preview issues out of primary lifecycle.

### P45: Release Readiness Tightening

- Remove remaining packaged suite pending/manual rows without weakening evidence gates.
- P45-01 complete: `sample_clean_full` is now a committed deterministic active toy fixture; packaged suite reports active=5, pending=0, known_gap=0, and release-readiness can produce `evidence_ready` for benchmarked drawing classes when representative run artifacts are complete.

### P46: Novice Reviewer Onboarding

- Make a generated review run understandable to a first-time plan-review engineer.
- P46-01 complete: full review runs and Studio runs write `reviewer_onboarding.json` and `reviewer_quickstart.md`; report and Viewer render the first-hour flow, boundary reminders, common commands, and handoff checklist.

### P47: Sheet Preview Review Bridge

- Make per-sheet candidate preview actionable without promoting it into the primary issue lifecycle.
- P47-01 complete: full review runs and Studio runs write `sheet_issue_review_queue.json`; report, Viewer, workbench, control sync, and release readiness all surface the queue as a preview-only bounded bridge.
- Guardrail: preview queue ids are not primary issue ids and must not be used with `archkg review-state`.

### P48: Real-Project Handoff Export Package

- Package an existing review run into a standalone read-only handoff directory for downstream review.
- P48-01 complete: `archkg handoff-package` writes `handoff_manifest.json`, `handoff_summary.md`, and copied artifacts under `artifacts/` without mutating the source run.
- Guardrail: handoff packages are evidence bundles, not compliance certificates.

### P49: Handoff Package Quality Gate

- Validate a generated handoff package before it is used for external review.
- P49-01 complete: `archkg handoff-check` writes `handoff_package_quality.v1` JSON/Markdown reports and fails `not_ready` packages.
- Guardrail: package quality checks completeness and boundary warnings only; it does not certify drawing compliance.

### P50: Package Reviewer Signoff Notes

- Let a receiving reviewer record package-level ready / needs_info / blocked status without touching source run artifacts.
- P50-01 complete: `archkg handoff-signoff` writes `reviewer_signoff.json` and `reviewer_signoff.md` inside the handoff package.
- Guardrail: reviewer signoff is a handoff note, not a compliance certificate, and it does not confirm candidate issues.

### P51: Static Handoff Package Review View

- Make a generated handoff package directly consumable in a browser without running Studio or a server.
- P51-01 complete: `archkg handoff-package` writes package-root `index.html`; `archkg handoff-check` and `archkg handoff-signoff` refresh quality/signoff summaries in that page.
- Guardrail: the static view is navigation only; it does not create evidence, mutate source runs, or certify compliance.

### P52: Manager Checklist Export

- Give a review manager a package-level intake checklist derived from manifest, handoff quality, and reviewer signoff.
- P52-01 complete: `archkg handoff-manager-checklist` writes `handoff_manager_checklist.v1` JSON/Markdown and refreshes the static package index.
- Guardrail: manager status is package-intake status only; it does not confirm candidate issues or certify drawing compliance.

### P53: Archive Manifest Checksums

- Give transferred handoff packages a stable file integrity manifest for downstream intake.
- P53-01 complete: `archkg handoff-archive-manifest` writes `handoff_archive_manifest.v1` JSON/Markdown, SHA-256 file entries, and a deterministic package digest while excluding generated self/index files.
- Guardrail: archive manifest status is transfer-integrity evidence only; it does not certify drawing compliance or replace source-run artifacts.

### P54: Archive Verification Import Check

- Let receiving reviewers verify a handoff package against its archive manifest before trusting the package contents.
- P54-01 complete: `archkg handoff-archive-verify` writes `handoff_archive_verification.v1` JSON/Markdown, reports missing/changed/unexpected package files, refreshes the static package index, and exits non-zero on `archive_drift`.
- Guardrail: archive verification is checksum alignment only; it does not confirm candidate issues or certify drawing compliance.

## Explicit Not-Build List

- No full Solibri/BIMcollab clone.
- No direct AI final violations.
- No arbitrary-jurisdiction permit approval claims.
- No benchmark promotion without reviewed expected inventory.
- No IFC stack rewrite while IfcOpenShell/IfcTester can provide the first lane.
