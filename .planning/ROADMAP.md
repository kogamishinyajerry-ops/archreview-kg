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

### P42: Re-Run Diff and Resolution Tracking

- Compare two runs and mark issues as unchanged, changed, resolved, or new.

### P43: Release Readiness Gate

- Publish a readiness rubric based on real benchmark evidence, not rule count.

## Explicit Not-Build List

- No full Solibri/BIMcollab clone.
- No direct AI final violations.
- No arbitrary-jurisdiction permit approval claims.
- No benchmark promotion without reviewed expected inventory.
- No IFC stack rewrite while IfcOpenShell/IfcTester can provide the first lane.
