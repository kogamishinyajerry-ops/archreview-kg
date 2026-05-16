# Changelog

All notable changes to ArchReview-KG. Version tags follow `v<major>.<minor>.<patch>`;
patch releases (`v1.0.x`) are individual ship phases reviewed by Codex GPT-5.4,
minor releases (`v1.1.0` / `v1.2.0`) are stable milestones rolling up multiple patches.

## Unreleased — 2026-05-16 — M5.Z iterate-to-99 closing arc (day-1 verification 100/100)

The M5 "Knowledge Graph as Product" milestone reached its exit gate (overall
≥99 per the test-judge agent) after five waves of iteration.

Closeout artifacts at `.planning/m5/M5-CLOSEOUT.md` and
`.planning/m5/quality_score_post_w6_round4.json`. Test-judge audit history:
R1 70/100 (3 overrides), R2 92 (2 lifted/eased), R3 95 (1 eased), R4 100/100
(0 overrides). Exit gate also requires day-2 verification on a different
calendar day; day-1 done.

### Added (M5.Z artifacts)

- 12 new active real_public_pdf cases (Cambridge MA, 4 distinct projects)
- 1 active non-MA real_public_pdf case (Hopkins MN sample foundation plan)
- 11 known_gap cases documenting recognizer failure modes (roof, elevation,
  section, raster-only, sparse extraction)
- 5 Medfield per-sheet split cases (2 active + 3 known_gap)
- `kg seed-demo-feedback --panel-size N` CLI flag
- Synthetic panel slug coverage extended to cambridge-/medfield-/real-
- `pyproject.toml` `[tool.pytest.ini_options] filterwarnings` for SWIG
- Per-case `expected_rule_counts` (adversarial seeding) across 17 active cases
- `M5-BLUEPRINT.md` "Recognition Quality — recall formula contract" section
- `READINESS.md` TL;DR rewrite + methodology disclosure section

### Quality score (independent test-judge audit)

| Dim                    | Pre-M5.Z | Post-W6 |
|------------------------|----------|---------|
| code_quality           | 9.0      | 10.0    |
| kg_persistence         | 10.0     | 10.0    |
| kg_coverage            | 10.0     | 10.0    |
| cross_project_query    | 10.0     | 10.0    |
| web_ui_e2e             | 10.0     | 10.0    |
| recognition_quality    | 9.52     | 10.0    |
| real_pdf_breadth       | 2.0      | 10.0    |
| calibration            | 8.6      | 10.0    |
| feedback_loop          | 10.0     | 10.0    |
| documentation_honesty  | 10.0     | 10.0    |
| **overall**            | **20.0** | **100** |

## Unreleased — 2026-04-27 — Raster OCR + drawing understanding bridge (v1.4 development slice)

Raster uploads can now opt into OCR text extraction without making
PaddleOCR a required dependency. This is a bridge slice, not a
production OCR claim: when OCR is unavailable or returns no text,
the raster path still degrades to the existing partial-review mode
and keeps the no-OCR transparency warning.

### Added

- `archkg.ingest.raster_extractor.extract(..., use_ocr=True)` calls
  the optional OCR module with `keep_only_dimensions=False`, so room
  labels such as `卧室` survive as `TextPrimitive(source="ocr")`
  instead of being filtered out as non-dimensions.
- Studio adds a raster-only "栅格 OCR beta" toggle. The route passes
  it through to the raster extractor and persists `use_ocr` plus
  `ocr_text_count` in `run_meta.json`.
- Raster result warnings are now evidence-based: the no-OCR warning
  appears only when the run produced zero OCR text primitives; runs
  with OCR text show an OCR beta quality flag instead.
- Tests cover the OCR bridge without requiring PaddleOCR:
  `tests/test_ingest_raster_ocr.py` verifies opt-in extraction and
  OCR label binding, while `tests/test_viewer_studio.py` verifies the
  Studio toggle, run metadata, and warning behavior.
- `archkg.viewer.ocr_diagnostics` adds a shared OCR evidence payload
  for both Studio pre-rendering and standalone `archkg viewer`
  re-rendering. Result pages now show OCR text count, bound-room count,
  low-confidence count, and sample OCR rows with confidence / bbox /
  room binding state.
- OCR evidence now includes label QA candidates for reviewer attention:
  label conflicts, unbound high-confidence room labels, and low-confidence
  room labels. These candidates do not mutate `Room.label` and do not
  change compliance results.
- OCR numeric texts now surface dimension binding evidence in the viewer:
  matched Door / Corridor entity, OCR-derived value, and current entity
  value. This documents the existing dimension-binding path without
  adding a new compliance-result lane.
- Viewer runs now write `drawing_understanding.json` and render a
  "图纸理解摘要" panel. The payload summarizes drawing type, likely
  design object, component counts, spaces, openings, circulation
  elements, graph dimension evidence, OCR-bound dimension evidence,
  and uncertainty flags. This is an evidence inventory for reviewing
  what the drawing appears to contain, not a new rule-engine output.
- P24 upgrades `drawing_understanding.json` to
  `drawing_understanding.v2`: it now includes typed
  `component_inventory`, `drawing_profile`, and `benchmark_signals`.
  Stair / vertical-circulation entities from schedule or future builder
  output are included in the same component taxonomy as rooms, openings,
  corridors, dimensions, and OCR-bound dimensions. Standalone viewer
  re-rendering rebuilds legacy P23 payloads that lack the v2 taxonomy.
- P25 adds `archkg understanding-benchmark`: a recognition benchmark
  harness that compares a run directory's drawing-understanding payload
  against an expected component inventory spec. It can build the v2
  payload from `primitives.json` + `entity_graph.json` when missing, and
  writes machine-readable JSON plus optional Markdown reports. The first
  packaged spec is
  `samples/understanding_benchmarks/sample_clean_full.json`.
- P26 adds `archkg understanding-benchmark-suite`: a suite manifest
  runner for drawing-understanding benchmarks. Active cases run the
  existing benchmark and fail on missing artifacts or failed checks,
  while `pending_fixture` / `manual_run_required` rows track real-drawing
  intake without counting as recognition proof. The first manifest
  template is
  `samples/understanding_benchmarks/suite_manifest.json`.
- P27 adds `archkg understanding-benchmark-author`: an expected-inventory
  authoring helper that drafts a benchmark spec from a run directory's
  current `drawing_understanding.json`. The draft includes drawing type,
  exact nonzero component counts, semantic kinds, evidence signals, and
  positive benchmark flags, and is explicitly marked
  `review_required: true` before any real drawing is promoted to an
  active suite case.
- P28 adds the first human-entered real-drawing expected inventory:
  Medfield / Hillside Village sheet A-1 First Floor Plan. The committed
  fixture includes source provenance, a current `drawing_understanding`
  snapshot, and a manual expected inventory with unit labels, room-label
  counts, door/opening size labels, and major dimensions. The suite now
  supports `known_gap` rows, which are scored but do not fail the suite
  while the recognizer is known not to meet the expected inventory.
- P32 adds a research-backed product direction document at
  `docs/research/2026-04-28-intelligent-plan-review-landscape.md`.
  The development guidance is to borrow mature patterns from BIM model
  checking, IDS/BCF, permit precheck products, and Chinese BIM review
  practice: build rule-input readiness, source-classified drawing
  evidence, reviewable issue lifecycle, and an IFC/IDS side lane before
  claiming broader real-plan compliance capability.
- P32-B records the major post-research pivot in repo-owned planning
  artifacts: `.planning/PROJECT.md`, `.planning/ROADMAP.md`,
  `.planning/STATE.md`, and executable phase plans for P33-P37.
  The new roadmap prioritizes runtime rule-input readiness, sheet-region
  candidates, issue lifecycle, IFC/IDS reuse, and draft-only rule authoring
  before broader real-plan compliance claims.
- P33-01 adds `rule_input_readiness.json` to full CLI and Studio review
  runs. The artifact covers all 32 loaded rule cards and marks each as
  `ready`, `missing_input`, `low_confidence`, `manual_only`,
  `not_applicable`, or `unsupported_entity` without changing
  `issues.json` behavior.
- P33-02 renders the same readiness payload in `report.md`, Studio
  pre-rendered `index.html`, and standalone `archkg viewer` re-renders.
  Missing readiness artifacts degrade to an explicit "缺失 readiness 不代表通过"
  warning so old run directories stay viewable.
- P34-01 adds `sheet_region_candidates.json` to CLI and Studio review
  runs. The detector suggests design/title-block/schedule/legend regions
  and excluded-text summaries, but does not crop or mutate graph input
  unless the caller explicitly supplies `--sheet-region`.
- P34-02 adds `sheet_region_candidates_overlay.png`, a source-preview
  overlay with color-coded candidate boxes, and renders it in the
  Viewer/Studio candidate panel.
- P35-01 adds `review_state.json` as a separate issue lifecycle layer.
  `issues.json` remains rule-engine candidate evidence; report, Viewer,
  Studio, and `archkg feedback` now render or update candidate /
  confirmed / rejected / needs_info / resolved / superseded states
  without mutating the rule output.
- P36-01 adds the optional IFC/IDS side lane:
  `archkg ifc validate --ifc model.ifc --ids requirements.ids -o out/ifc`.
  When IfcOpenShell/IfcTester is installed it writes
  `ids_report_raw.json`, `ifc_validation.json`, and `ifc_issues.json`.
  Missing optional dependencies degrade with a clear message and do not
  affect the PDF review pipeline.
- P37-01 adds draft-only rule-card authoring:
  `archkg rule-card draft --clause-id GB50096-5.7.2 -o out/rule_card_draft.json`.
  The `rule_card_draft.v1` artifact records source clause evidence,
  extracted threshold, proposed inputs, applicability, ambiguity notes,
  missing evidence, and proposed tests. Status is fixed to `draft`; active
  `rule_cards.yaml` is never mutated by this command.
- P38-01 adds `sheet_classification.json` to full CLI and Studio review
  runs. The artifact classifies each page as plan / schedule / title /
  legend / detail / elevation / unknown, records confidence and evidence
  texts, and marks graph eligibility as advisory routing evidence. Viewer
  and `report.md` render the same payload, while old runs without the
  artifact show an explicit missing-classification warning.
- P38-02 adds protected graph routing with `sheet_routing.json`. Full CLI
  and Studio runs now route graph input to a single confident plan page
  only when all other pages are confident non-graph sheets. Unknown,
  low-confidence, missing-classification, single-page, or multiple-plan
  runs fall back to legacy all-page graph input, and the decision renders
  in Viewer/Studio/report surfaces.
- P39-01 adds `sheet_graphs.json` as a multi-plan evidence artifact. Full
  CLI and Studio runs now build an independent `EntityGraph` for each
  confident plan sheet, skip non-plan/low-confidence sheets with reasons,
  and render the per-sheet graph counts in Viewer/Studio/report surfaces.
  The primary `entity_graph.json` and rule-engine issue output remain
  unchanged in this slice.
- P39-02 adds `sheet_issues.json` as a per-sheet issue preview artifact.
  It evaluates the existing rule cards against each `sheet_graphs.json`
  plan graph and groups candidate issues by page. This preview is rendered
  in Viewer/Studio/report surfaces but is not merged into primary
  `issues.json` or `review_state.json`.
- P40-01 expands the understanding benchmark harness to score
  `sheet_graphs.json` and `sheet_issues.json`. Expected specs can now
  assert graph counts, required plan page indexes, per-sheet component
  counts, per-sheet issue groups, and required rule IDs by page. The
  packaged suite adds deterministic active case `generated-multi-plan-sheets`
  and now reports active=3, pending=1, failed=0.
- P40-02 adds a real multi-plan intake gate to the packaged benchmark
  suite. Pending suite rows can now expose `provenance`,
  `required_artifacts`, and `promotion_rule`, and the Medfield full
  9-page plan/elevation set is registered as
  `medfield-full-plan-set-multi-plan-intake` with explicit artifact
  gaps before it can become `known_gap` or `active`. The packaged suite
  now reports active=3, pending=2, failed=0.
- P40-03 promotes the Medfield full 9-page plan/elevation set from
  pending intake to `known_gap`. A reduced full-run artifact snapshot is
  committed with `drawing_understanding.json`, `sheet_classification.json`,
  `sheet_routing.json`, `sheet_graphs.json`, and `sheet_issues.json`;
  the expected inventory intentionally requires full-set opening evidence
  that current primary `drawing_understanding` misses. The packaged suite
  now reports active=3, pending=1, known_gap=1, failed=0.
- P41-01 adds `review_workbench.json`, a compact Studio/Viewer entry
  artifact that summarizes drawing-understanding counts, rule readiness,
  issue counts, sheet classification/routing/graphs/preview issues, and
  review-state counts. CLI and Studio full runs write it, inspect-only
  Studio runs write a partial workbench summary, `report.md` and the
  Viewer render a "审图工作台总览" section, and control sync tracks the
  artifact. It is navigation only and does not mutate rule output.
- P41-02 turns the workbench summary into an action surface by adding
  structured `action_links` to `review_workbench.json`. The Viewer renders
  these as click targets to source/overlay layers, component inventory,
  readiness blockers, sheet evidence, region candidates, candidate issues,
  review state, and report/clauses; `report.md` mirrors the same actions.
  The links are navigation only and do not write review decisions.
- P41-03 adds bounded local review-state operations. `archkg review-state`
  updates one primary `issues.json` issue in `review_state.json`, refreshes
  the workbench summary, and rejects per-sheet preview issue IDs. The
  workbench and report expose command templates while `issues.json` and rule
  output remain immutable.
- P41-04 adds source/overlay issue cross-highlighting in Viewer/Studio. First
  page primary issue bboxes can be focused from the issue list onto the
  source, entity overlay, or annotated preview. Multi-page issue focus remains
  intentionally omitted until multi-page previews are available.
- P56-01 makes Viewer/Studio issue focus sheet-aware. Primary issue bboxes are
  normalized against their own `page_index`; page-0 issues still highlight on
  the static preview layer, while non-page-0 issues keep the correct page label
  and route reviewers to `source.pdf` / `annotated.pdf` page review instead of
  being projected onto the first-page PNG.
- P57-01 adds multi-page preview galleries for Viewer/Studio. Source and
  annotated PDFs are rendered into page-indexed PNG sets, `preview_pages.json`
  records the available preview pages, the result page gains page-switch
  controls, and non-first-page primary issues can focus the corresponding
  source/annotated page directly. `entity_overlay.png` remains page-0 only.
- P58-01 makes handoff packages preserve multi-page preview assets.
  `archkg handoff-package` now copies `source.pdf`, `preview_pages.json`,
  legacy preview PNGs, and every preview image referenced by the preview
  manifest; missing referenced preview images become handoff quality blockers.
- P59-01 adds per-page entity overlay rendering for graph-backed sheets.
  Viewer/Studio now write overlay page entries into `preview_pages.json`,
  preserve the legacy `entity_overlay.png` for the primary graph, and rely on
  manifest-driven handoff copying so overlay page images survive package export.
- P60-01 adds a compact multi-package handoff bundle index. `archkg
  handoff-bundle-index <packages-root>` scans child handoff packages and writes
  JSON, Markdown, and static HTML summaries without mutating package contents.
  The index groups packages as ready, needs-info, or blocked across quality,
  reviewer signoff, manager checklist, and archive verification state.
- P61-01 adds reviewer task sequencing for novice review execution. Full CLI
  and Studio runs now write `reviewer_task_sequence.json` and
  `reviewer_task_sequence.md`, report/Viewer render the ordered queue, and
  handoff packages copy the sequence as entry evidence.
- P62-01 adds a fillable reviewer task checklist seed. Full CLI and Studio
  runs now derive `reviewer_task_checklist.json` and
  `reviewer_task_checklist.md` from the ordered sequence, report/Viewer render
  the checklist, and handoff packages copy it as entry evidence without
  mutating issue state.
- P63-01 extends the handoff bundle index with reviewer checklist risk
  aggregation. Bundle JSON/Markdown/HTML now summarize checklist open item
  totals, per-package checklist review status, and first open samples without
  mutating package artifacts or changing package readiness semantics.
- P64-01 adds package-local reviewer checklist updates. `archkg
  handoff-checklist-update` updates one item in
  `artifacts/reviewer_task_checklist.json`, regenerates the package-local
  Markdown checklist, and refreshes package `index.html` without touching the
  source run or primary review state.
- P65-01 gates manager intake on the package-local reviewer checklist.
  `archkg handoff-manager-checklist` now reads
  `artifacts/reviewer_task_checklist.json`, records checklist status and
  open/blocked/needs-info counts in the manager checklist summary, and keeps
  manager intake at needs-info or blocked until reviewer checklist rows are
  completed or explicitly skipped as preview-only.
- P66-01 adds a package-local ready-to-review runbook for novice reviewers.
  Handoff packages now include `handoff_ready_runbook.json` and
  `handoff_ready_runbook.md`, and `archkg handoff-ready-runbook` refreshes the
  runbook with quality, signoff, checklist, and manager-intake next actions.
  The runbook is navigation guidance only and is excluded from archive
  checksums because it refreshes with package-local state.
- P67-01 adds a bundle-level next-actor queue. `archkg handoff-bundle-index`
  now records `next_actor`, `next_action_*`, and a structured
  `next_action_queue` so managers can see whether reviewer, manager, archive,
  or no one should act next without opening every package.
- P68-01 adds an evidence-oriented 2.5D layout model. Full CLI and Studio
  review runs now write `layout_3d.json`, `layout_3d_summary.md`, and
  `layout_3d.glb` from `sheet_graphs.json` first and `entity_graph.json` as a
  fallback. Viewer/Studio surfaces show status, object counts, assumptions,
  blocked reasons, and GLB links, while handoff packages copy the artifacts as
  read-only evidence. The model is for spatial navigation only; default
  heights/thicknesses remain explicit assumptions and are not rule-engine facts
  or BIM truth.
- P69-01 adds an optional layout IFC export lane. `archkg ifc export-layout`
  reads only `layout_3d.json` and can write `layout.ifc`,
  `layout_ifc_export.json`, and `layout_ifc_export.md` when IfcOpenShell is
  available. Missing IfcOpenShell now degrades to `dependency_missing` with a
  written report when requested, blocked `layout_3d` inputs return `blocked`,
  and Viewer/Studio/handoff/control-sync treat the IFC files as optional
  preview artifacts. The exported IFC is not review-grade BIM and is not a
  rule-engine or compliance input.
- P70-01 hardens layout IFC preview semantics. `build_layout_3d` now emits
  `window_opening` objects only for explicit graph evidence (`opening_kind:
  "window"` / `"window_opening"` or `is_window: true`) and keeps generic doors as
  `door_opening`. `layout_ifc_export` maps `window_opening` to `IfcWindow` and
  reports exported counts separately. Missing IfcOpenShell remains a clean
  non-blocking `dependency_missing` path; optional real IfcOpenShell smoke is
  added in regression tests with `importorskip("ifcopenshell")`.
- P71-01 adds opening semantic provenance to the 3D evidence layer. Door and
  window opening objects now carry `properties.opening_semantic` that records
  whether the semantic came from explicit graph evidence or the default Door
  entity type. `layout_3d_summary.md` and Viewer/Studio now show an
  `Opening Semantics` summary so reviewers can audit why an opening is shown
  as `door_opening` or `window_opening` without treating it as wall-void
  geometry or a compliance finding.
- P72-01 adds explicit opening measurement provenance to the 3D evidence
  layer. Door and window opening objects now carry
  `properties.opening_measurement` only when graph evidence provides explicit
  fields such as `Door.width_m`, `Door.properties.height_m`,
  `sill_height_m`, or `head_height_m`. Explicit opening heights replace the
  corresponding default height assumption for that object; missing dimensions
  remain explicit visualization assumptions. `layout_3d_summary.md` and
  Viewer/Studio now show `Opening Measurements` as preview provenance only,
  without promoting dimensions to rule-engine or compliance facts.
- P73-01 adds explicit opening wall-host provenance to the 3D evidence layer.
  Door and window opening objects now carry `properties.opening_host` only when
  graph evidence provides explicit host wall or source-segment fields such as
  `Door.properties.opening_host_wall_id` and
  `Door.properties.opening_host_wall_segment`. `layout_3d_summary.md` and
  Viewer/Studio now show `Opening Host Wall Provenance` without inferring host
  walls, carving wall voids, or changing rule-engine semantics.
- P74-01 adds an opening provenance consistency coverage view. `layout_3d`
  summary counts now show how many openings have semantic, measurement, host,
  and all-three preview provenance signals; Viewer/Studio shows per-opening
  coverage samples and missing-provenance prompts. This is reviewer navigation
  metadata only, not a failure gate, BIM completeness claim, or compliance
  input.
- P75-01 carries opening provenance coverage into the optional IFC export
  summary. `layout_ifc_export.v1` JSON/Markdown reports and IFC Viewer data now
  show semantic, measurement, host-wall, and all-three coverage counts without
  changing IFC preview boundaries, IfcOpenShell optionality, or rule-engine
  semantics.
- P76-01 surfaces opening provenance coverage in handoff packages.
  `archkg handoff-package` reads `layout_ifc_export.json` and writes the
  coverage into `handoff_manifest.json`, `handoff_summary.md`, and package-root
  `index.html` so novice reviewers can see opening evidence gaps without
  opening Studio. Missing signals remain review prompts, not handoff blockers
  or compliance findings.
- P77-01 adds bundle-level opening provenance triage in
  `archkg handoff-bundle-index`. The bundle index now aggregates each package's
  opening provenance semantic / measurement / host_wall / all_three counts, exposes
  a weak-coverage package counter, and renders per-package `Opening Provenance`
  and `Weak Coverage` columns in both Markdown and HTML summaries for manager
  dispatch. It remains triage-only and does not alter package readiness,
  quality, signoff, manager, archive verification, or compliance semantics.
- P78-01 adds a separate opening provenance review queue to
  `archkg handoff-bundle-index`. Weak-coverage packages now appear in
  `opening_provenance_triage_queue` with reviewer actor, reason, coverage tuple,
  source artifact, and preview-only boundary warning, and the queue renders in
  Markdown/HTML. The queue is separate from the normal package
  `next_action_queue` and does not change readiness, quality, signoff, manager,
  archive, or compliance semantics.
- P79-01 adds package-local opening provenance checklist guidance. When a
  handoff package has weak opening provenance coverage, `archkg handoff-package`
  now writes an `opening_provenance_guidance` section into the copied
  `artifacts/reviewer_task_checklist.json` and renders it in
  `artifacts/reviewer_task_checklist.md`. The guidance does not add checklist
  items, change item counts, alter manager readiness, mutate source runs, or
  turn weak coverage into a compliance finding.
- P80-01 surfaces package-local opening provenance guidance in the ready
  runbook. `handoff_ready_runbook.json` now includes `optional_review_actions`
  for weak opening provenance guidance and the Markdown runbook renders an
  `Optional Review Guidance` section pointing to
  `artifacts/reviewer_task_checklist.md`. The guidance does not populate
  required `next_actions`, block manager intake, change package readiness,
  mutate source runs, or turn weak coverage into a compliance finding.
- P81-01 links ready-runbook opening provenance guidance from the package
  static index. When `handoff_ready_runbook.json` has optional review actions,
  `index.html` now renders an `Optional Review Guidance` entry under the
  Ready-To-Review Runbook panel with links to
  `handoff_ready_runbook.md#optional-review-guidance` and the referenced
  package-local checklist artifact. The link is navigation-only and does not
  alter required `next_actions`, manager intake, package readiness, source
  runs, or compliance semantics.
- P82-01 adds bundle-level visibility for package-index optional guidance.
  `handoff_bundle_index.v1` now includes summary counts and a separate
  `package_index_optional_guidance_queue` for packages whose static index links
  to ready-runbook optional guidance. Markdown/HTML render the same queue for
  manager visibility. This does not alter package status, `next_actor`,
  `next_action_queue`, manager intake, source runs, or compliance semantics.
- P83-01 adds package-local optional guidance review notes.
  `archkg handoff-optional-guidance-note` writes
  `handoff_optional_guidance_note.json/.md`, captures reviewer/status/note and
  the ready-runbook optional actions reviewed, and refreshes package `index.html`.
  The note is review documentation only; it does not confirm candidate issues,
  mutate source runs, change `review_state.json`, alter manager intake, or
  change package readiness.
- P84-01 adds bundle optional guidance note closeout summary. `handoff_bundle_index`
  now reads package-local `handoff_optional_guidance_note.json` (when package
  index optional guidance is available), computes reviewed / needs_info / blocked /
  not_recorded / invalid counts, emits an independent
  `optional_guidance_note_closeout_queue`, and renders it in bundle Markdown/HTML
  for manager triage. This is visibility-only and does not change readiness,
  routing, source-run artifacts, `issues.json`, or `review_state.json`.
- P85-01 adds a bundle manager triage digest. `handoff_bundle_index` now writes
  `manager_triage_digest`, a derived read-only summary over the existing
  `next_action_queue`, `opening_provenance_triage_queue`,
  `package_index_optional_guidance_queue`, and
  `optional_guidance_note_closeout_queue`. It renders in bundle Markdown/HTML
  without replacing queues or changing readiness, routing, source runs,
  `issues.json`, or `review_state.json`.
- P42-01 adds re-run issue diff tracking. `archkg review-diff BEFORE_RUN
  AFTER_RUN -o AFTER_RUN/review_diff.json` compares primary `issues.json`
  candidates with stable rule/clause/page/spatial/evidence fingerprints instead
  of per-run `issue_id` or entity ID values, and marks items as unchanged,
  changed, new, or resolved without mutating either run, `review_state.json`,
  or per-sheet preview issues.
- P42-02 renders `review_diff.json` in Viewer/Studio. The workbench shows
  unchanged / changed / new / resolved counts and sample rows, while current
  issue rows get read-only diff status pills. Missing diff artifacts are
  explained as "diff not run yet", not as "no changes".
- P43-01 adds `archkg release-readiness`, an evidence gate that evaluates
  an understanding benchmark suite plus an optional representative run
  directory. It writes `release_readiness.json` / Markdown reports with
  `not_ready`, `demo_ready_with_known_gaps`, or `evidence_ready` status,
  blocks on failed active suites / missing active real drawings / missing core
  artifacts, and warns on known gaps, pending fixtures, generated-heavy proof,
  and missing maturity artifacts.
- P44-01 merges `sheet_graphs.json` count evidence into
  `drawing_understanding.json` for multi-plan/full-set recognition. The merge
  adds a `sheet_graph_summary`, updates component counts and benchmark signals,
  and inserts aggregate inventory rows marked `sheet_graphs_count` instead of
  pretending per-sheet entities belong to the primary graph. The Medfield
  9-page public plan/elevation set is promoted from known_gap to active
  recognition benchmark; the packaged suite now reports active=4, pending=1,
  known_gap=0, failed=0.
- P45-01 promotes the `sample_clean_full` toy vector fixture from a
  `manual_run_required` intake row to a committed active benchmark run. The
  packaged suite now reports active=5, pending=0, known_gap=0, failed=0, so
  `archkg release-readiness` can reach `evidence_ready` when representative run
  artifacts are complete. This removes a reproducibility gap only; it does not
  make toy evidence a proxy for arbitrary real construction drawings.
- P46-01 adds novice reviewer onboarding artifacts. Full review runs and Studio
  runs now write `reviewer_onboarding.json` plus `reviewer_quickstart.md`, and
  render the first-hour review path in `report.md` and Viewer. The pack gives
  a new plan-review engineer a stable order for checking source/overlay,
  component inventory, readiness blockers, sheet scope, candidate issues,
  review-state commands, and handoff notes. It is guidance-only and does not
  mutate rule output or confirm defects.
- P47-01 adds a bounded sheet preview review queue. Full review runs and Studio
  runs now write `sheet_issue_review_queue.json` from `sheet_issues.json`, then
  render it in `report.md`, Viewer, workbench artifact status, control sync, and
  release-readiness gates. The queue is explicitly `preview_only` with
  `preview_only_no_primary_write`, forbids `archkg review-state` on preview ids,
  and gives novice reviewers a concrete per-sheet checklist without promoting
  preview rows into primary `issues.json` or `review_state.json`.
- P48-01 adds read-only handoff packaging. `archkg handoff-package RUN_DIR -o
  PACKAGE_DIR` copies the quickstart, report, workbench, drawing understanding,
  rule readiness, primary issues/review state, per-sheet preview queue, optional
  diff/readiness/visual artifacts, and writes `handoff_manifest.json` plus
  `handoff_summary.md`. The package is outside the source run by default and
  uses `copy_artifacts_only_no_source_run_mutation`.
- P49-01 adds a handoff package quality gate. `archkg handoff-check PACKAGE_DIR`
  validates `handoff_manifest.json`, the copy-only/read-only policy, required
  artifact availability, copied file existence, and boundary warnings. It writes
  `handoff_package_quality.v1` JSON/Markdown reports and exits non-zero when a
  package is `not_ready`.
- P50-01 adds package-local reviewer signoff notes. `archkg handoff-signoff
  PACKAGE_DIR --reviewer NAME --status ready|needs_info|blocked` writes
  `reviewer_signoff.json` and `reviewer_signoff.md` inside the handoff package,
  including blockers, missing information, next actions, and a boundary warning
  that the signoff is not a compliance certificate. Source run artifacts remain
  untouched.
- P51-01 adds a static handoff package review view. `archkg handoff-package`
  now writes package-root `index.html`, and `archkg handoff-check` /
  `archkg handoff-signoff` refresh it with quality and signoff summaries. The
  page links to copied artifacts and repeats package boundary warnings for a
  novice review engineer.
- P52-01 adds a manager checklist export. `archkg handoff-manager-checklist
  PACKAGE_DIR --manager NAME` writes `handoff_manager_checklist.json` and
  `handoff_manager_checklist.md` inside the handoff package, deriving
  `manager_ready`, `manager_needs_info`, or `manager_blocked` from the package
  manifest, handoff quality gate, and reviewer signoff. The static package
  page is refreshed with the manager checklist summary.
- P53-01 adds a handoff archive manifest. `archkg handoff-archive-manifest
  PACKAGE_DIR --created-by NAME` writes `handoff_archive_manifest.json` and
  `handoff_archive_manifest.md` inside the handoff package, recording SHA-256
  checksums, byte sizes, excluded generated files, and a deterministic package
  digest for transfer integrity. The source run remains untouched and the
  static package page is refreshed with the archive manifest summary.
- P54-01 adds archive verification for received handoff packages. `archkg
  handoff-archive-verify PACKAGE_DIR` recomputes stable package file checksums,
  compares them with `handoff_archive_manifest.json`, writes
  `handoff_archive_verification.json` and `.md`, and exits non-zero on
  `archive_drift`.
- P55-01 expands the active understanding benchmark suite. It adds a
  human-reviewed Medfield A-2 Second Floor Plan expected inventory and a
  deterministic generated mixed-sheet-set benchmark with plan, schedule/legend,
  and elevation/section pages. The packaged suite now reports active=7,
  pending=0, known_gap=0, failed=0, with real_active=3 and generated_active=3,
  preserving the release-readiness guardrail that generated evidence must not
  outnumber real drawing evidence.

### Still limited

- OCR accuracy is not claimed. Users must inspect the entity overlay
  and the OCR evidence / label QA / dimension evidence panels before
  trusting OCR-dependent results.
- `room_schedule.yaml` still cannot patch label-less raster rooms; it
  remains a vector-PDF path because it selects existing `room_id` or
  `label`.
- The drawing understanding payload is only as good as the current
  builder / OCR evidence. It does not claim production-grade recognition
  for noisy scans, multi-page construction sets, or arbitrary complex
  real drawings.
- The v2 taxonomy is descriptive. It records evidence categories and
  confidence bands for review/benchmarking, but it does not alter issue
  generation or make schedule-only stairs geometrically located.
- Understanding benchmark scores measure recognition evidence only. They
  do not score GB compliance accuracy and do not make the toy fixture a
  proxy for arbitrary real construction drawings.
- Pending suite rows are bookkeeping for fixture intake. They are not
  scored and must not be presented as successful handling of complex real
  construction drawings until run artifacts and expected inventories are
  added as active cases.
- Authored expected specs are draft annotations, not ground truth by
  themselves. They preserve the current recognition output for review;
  a human or later annotation pass must correct the draft before it
  becomes a real benchmark oracle.
- The Medfield A-1 single-sheet fixture and Medfield full 9-page fixture are
  recognition benchmarks only. The full-set case now exposes openings through
  count-level `sheet_graphs.json` aggregation; it still does not prove final
  full construction-set compliance aggregation.
- The Medfield A-2 single-sheet fixture and generated mixed-sheet-set fixture
  are recognition benchmarks only. The generated mixed-sheet case locks
  sheet classification and per-plan graphing behavior, but it is not real
  project evidence.
- `review_diff.json` is a local tracking artifact over primary `issues.json`;
  it does not prove a fix is code-compliant, does not update human review
  status, and does not aggregate `sheet_issues.json` preview rows.
- `release_readiness.json` is a release/demo evidence gate, not a production
  certification. An `evidence_ready` result must still be scoped to the
  benchmarked drawing classes and cannot be marketed as broad automatic
  compliance readiness.
- `reviewer_onboarding.json` and `reviewer_quickstart.md` are onboarding
  surfaces, not compliance evidence by themselves. They help reviewers inspect
  existing evidence in order; they do not validate the drawing or confirm
  candidate issues.
- `sheet_issue_review_queue.json` is an inspection bridge over per-sheet
  preview issues. Its `preview_id` values are not primary issue ids and must not
  be passed to `archkg review-state`.
- `handoff_manifest.json` and `handoff_summary.md` are read-only package
  metadata. They copy existing evidence for external review and do not mutate
  the source run or confirm candidate issues.
- `handoff_package_quality.v1` validates package completeness only. It is not a
  drawing-compliance certificate and does not replace release-readiness or
  benchmark evidence.
- `reviewer_signoff.json` is a package-local handoff note only. It records a
  human reviewer's transfer status and follow-up items, but it does not confirm
  candidate issues, mutate the source run, or certify compliance.
- Handoff package `index.html` is a static navigation surface over copied
  artifacts. It does not introduce new evidence, mutate source runs, or turn a
  package-level ready/signoff state into drawing compliance.
- `handoff_manager_checklist.v1` is a package-management acceptance aid only.
  It summarizes whether the evidence bundle can enter the next review step; it
  does not confirm candidate issues or certify drawing compliance.
- `handoff_archive_manifest.v1` is a transfer-integrity manifest only. It
  fingerprints copied package files but does not certify drawing compliance,
  replace release-readiness, or mutate the source run.
- `handoff_archive_verification.v1` is a transfer-integrity verification only.
  It detects missing, changed, or unexpected package files, but it does not
  confirm candidate issues or certify drawing compliance.
- Multi-sheet drawing-understanding aggregation is count-level evidence. It
  does not merge per-sheet candidate issues into primary `issues.json`, does
  not update `review_state.json`, and does not prove final multi-plan
  compliance aggregation.

## v1.3.0 — 2026-04-27 — Raster (PNG / JPEG) ingestion via OpenCV

The studio now accepts PNG, JPEG, TIFF, and BMP raster floor plans
in addition to PDFs. Walls are detected via OpenCV probabilistic
Hough Lines after thresholding and morphological thinning;
endpoints snap to perpendicular walls so that polygonize can close
rooms. The rest of the pipeline (graph builder, rule engine,
annotator, viewer) is unchanged — raster inputs are wrapped into a
1:1 px-to-pt PDF immediately after CV extraction so downstream
fitz-based code paths just work.

### Added

- `archkg/ingest/raster_extractor.py`:
  - `extract(image_path, *, points_per_meter)` runs the full CV
    pipeline (threshold → erode → HoughLinesP → orthogonal-only
    dedupe with interval preservation → endpoint snap to
    perpendicular walls) and returns a `Primitives` payload in the
    same shape as the PDF extractor.
  - `wrap_image_as_pdf(image_path, out_pdf)` produces a PDF whose
    page is exactly `width_px × height_px` points so the pixel-space
    line coordinates align with fitz's page rect (the default
    `fitz.open(image)` would scale 4/3 smaller and break overlay
    alignment).
- Studio form accepts `image/png, image/jpeg, image/tiff, image/bmp`
  in addition to PDF; the upload handler dispatches based on file
  extension.
- 3 new tests in `tests/test_viewer_studio.py`:
  - `test_run_pipeline_extracts_walls_from_png`: end-to-end on a
    200-DPI render of the demo PDF, asserts the same 4-room /
    1-corridor / 6-door topology emerges from CV.
  - `test_post_review_accepts_png_upload`: studio /review accepts
    PNG bytes and produces all standard viewer artifacts.
  - `test_post_review_rejects_unsupported_extension`: a `.gif`
    upload flashes a clear error rather than being silently treated
    as PDF.
- New runtime dependency: `opencv-python-headless>=4.10` (~44 MB).

### Codex P20-A R1 fixes (R1 → R2)

- **Scale-normalized CV heuristics** (R1 P0): every length-like
  parameter (Hough min-line / max-gap / vote threshold, dedupe
  perpendicular bin, interval merge gap, endpoint snap tolerance)
  is now expressed in METERS and converted to pixels at runtime
  using `points_per_meter`. Erosion is conditionally skipped at
  ppm < 150 to avoid destroying 1-pixel walls in low-DPI renders.
  Verified topology stable across 100 / 150 / 200 / 300 / 600 DPI:
  4 rooms / 1 corridor / 6 doors at every step.
- **Studio `image_dpi` form field** (R1 P0): raster uploads use
  `ppm_pixel = points_per_meter × image_dpi / 72` (default
  `image_dpi=200`). Form value is authoritative because PIL DPI
  metadata is unreliable on PNGs (fitz exports often carry a
  bogus 96 DPI). PDFs ignore the field.
- **No-OCR transparency banner** (R1 P1 + R2 P1 + R3 P1): raster
  ingest prepends a quality flag warning that the 5 label-dependent
  Room rules (`RC-BEDROOM-AREA`, `RC-LIVING-BEDROOM-NETHEIGHT-2.4`,
  `RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1`,
  `RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0`,
  `RC-NO-LIVING-IN-BASEMENT`) won't fire because no OCR runs. R2
  dropped an earlier false remediation ("upload
  room_schedule.yaml") since the schedule selects rooms by existing
  `room_id`/`label` and raster rooms have neither, so it can't
  actually unlock anything. R3 cleaned up the same false suggestion
  from the upload-page drop-hint and the raster-extractor module
  docstring, and replaced the previously approximated rule-id /
  count list with the precise 5-rule list above. The corrected
  banner names the honest options: re-upload the matching vector
  PDF, or wait for v1.4 OCR support.

### Limitations (raster path only)

- **Orthogonal walls only.** Diagonal walls are dropped. Most
  Chinese residential plans are orthogonal but Western plans with
  bay windows etc. lose those walls.
- **No OCR.** Labels are absent for every detected room, so the 5
  Room rules that read `label` (bedroom area, living/bedroom net
  height, pitched-roof majority height, basement/mezzanine net
  height, no-living-in-basement) won't fire on raster inputs.
  `room_schedule.yaml` cannot patch this — its selector keys on
  existing `room_id`/`label`, neither of which raster rooms have.
  For a complete review, re-upload the matching vector PDF. v1.4
  will add OCR.
- **Hand-drawn or noisy scans → poor detection.** The pipeline is
  tuned for clean CAD-rendered raster output (200 DPI from a
  vector PDF, etc.).
- **`points_per_meter` is interpreted as PIXELS per meter** for
  raster inputs, not PostScript points. For a metric CAD PDF
  (ppm=50 pt/m) rendered to PNG at 200 DPI, set 138.89.
- **Thick-wall (double-line) CAD limitation from v1.2.2 still
  applies** to both vector and raster paths.

### Real-PDF impact

A 200-DPI render of `samples/sample_clean.pdf` fed through the CV
pipeline reproduces the same 4 rooms / 1 corridor / 6 doors / 10
issues as the original PDF — proves the topology survives the
vector-to-raster-to-vector roundtrip on clean CAD output. Real
real-world PNGs (CAD screenshots, scanned plans) are not
guaranteed to work yet.

## v1.2.2 — 2026-04-26 — Real-PDF readiness: builder min-area + orphan-door noise filter

v1.2.1 surfaced builder noise via warnings; v1.2.2 cuts the noise at
its source. A `min_room_area_m2` floor in `build_graph` drops
sub-threshold polygons before they enter the room list, and a
companion filter prunes "doors" detected on wall breaks between
filtered noise polygons (the dominant Medfield false-positive path —
89 spurious `RC-DOOR-WIDTH` violations in v1.2.0).

### Added

- `archkg.graph.builder.build_graph(primitives, *, min_room_area_m2=0.0)`
  optional kwarg. Builder default 0.0 keeps `archkg review` and the
  existing synthetic-test path bit-for-bit identical; the studio passes
  a non-zero default so first-time real-PDF uploads aren't drowned in
  fixture noise.
- **Door anchoring covers rooms AND corridors** (Codex P19-D R2 P0):
  `_door_from_bridge` now searches the corridor list when assigning
  `Door.connects`, not just the room list. The pre-R2 implementation
  silently labelled real corridor-side doors as `(room, None)`, which
  the orphan filter would then mistakenly classify as half-orphan
  (and conversely, "surviving room + filtered noise polygon"
  half-orphans looked the same as real entrance doors). Doors now
  carry corridor ids on the corridor side, so `(None, None)`
  uniquely identifies wall breaks between filtered noise polygons.
- **Corridor-branch noise filter** (Codex P19-D R2 P2): the same
  `min_room_area_m2` floor is applied to the corridor classification
  branch. Long-thin noise scraps (3 m x 0.6 m cabinet gaps) that
  pass the aspect/short-side test would otherwise survive as
  "corridors" and trigger spurious RC-CORRIDOR-WIDTH violations.
  Real corridors are >=3 m² so the floor never drops a plausible
  one.
- **Three-way door-side classification** (Codex P19-D R3 P0): each
  door bridge's two sides are classified as `surviving` (room or
  corridor that passed the area floor), `filtered` (polygon rejected
  by the floor), or `exterior` (nothing covers the sample point). A
  door is kept iff no side is `filtered` and at least one is
  `surviving`. The pre-R3 implementation mapped filtered and exterior
  to the same `None`, so the orphan filter couldn't tell a noise
  door (surviving room ↔ filtered noise polygon) apart from a real
  entrance door (surviving room ↔ exterior).
- **Bridge-coverage adjacency + local-step side resolution**
  (Codex P19-D R7 P1, both findings): the door-side classifier asks
  two questions per polygon. (1) Adjacency: does the bridge length
  lie substantially within the polygon-boundary buffer (≥50%, with
  0.5 pt fuzz)? Min-distance alone admitted polygons that only
  touch the bridge endpoint or a parallel sliver. (2) Side: does
  the polygon cover a tiny step off the bridge midpoint along the
  signed normal? Centroid-based side resolution was unsound for
  concave (L/U/C-shaped) rooms whose centroids fall outside the
  shape. The combined predicate handles every regression case
  Codex constructed during R3-R7. Real-CAD plans with thick wall
  structures (bridge centerline buried inside wall material)
  remain out of scope for v1.2.2; called out in README and
  READINESS with the symptom (door count near zero) so users can
  recognise it.
- Studio "advanced parameters" form field `min_room_area_m2` (default
  1.0 m², min 0). Value 0 disables both room and door filtering. Bad
  input flashes an error and redirects home, matching the
  `points_per_meter` validation pattern.
- **`run_meta.json` now records `points_per_meter` and
  `min_room_area_m2`** (Codex P19-D R1 P2). Materially-output-changing
  knobs are persisted so a user reporting unexpected entity counts can
  be debugged from the run dir alone.
- `tests/test_graph_builder.py::test_min_room_area_filter_drops_sub_threshold_polygons`
  parameterises the floor at 0.0 / 10.0 / 16.0 / 100.0 m² against the
  4-room sample and asserts the expected drop pattern.
- `tests/test_graph_builder.py::test_door_connects_anchor_to_rooms_or_corridors`
  asserts `Door.connects` carries corridor ids when the door is
  corridor-side (Codex P19-D R2 P0 regression guard).
- `tests/test_graph_builder.py::test_min_room_area_filter_also_prunes_orphan_doors`
  proves the companion filter at three thresholds: 0.0 / 1.0 (no
  drop on clean sample) / 16.0 (drops the two small rooms + the
  corridor; door count strictly less than off; surviving doors all
  anchored to a surviving room). Codex P19-D R1/R2 P0 anchor.
- `tests/test_graph_builder.py::test_filter_drops_doors_anchored_to_filtered_noise`
  is a Codex-supplied synthetic regression: 48 m² big room + 1.7 m²
  side polygon + 0.9 m door gap. With `min_room_area_m2=3.0` the
  small polygon is filtered and the door must be dropped (not kept
  as a half-orphan). Codex P19-D R3 P0 anchor.
- `tests/test_graph_builder.py::test_filter_drops_doors_anchored_to_thin_filtered_strip`
  exercises a 0.2 m x 4.0 m noise strip (0.8 m², filtered at 1.0 m²)
  — narrower than the legacy 0.3 m probe distance. The 0.05 m probe
  lands cleanly inside the strip and drops the door. Codex P19-D R4
  P0 anchor.
- `tests/test_graph_builder.py::test_filter_keeps_real_exterior_door_with_detached_noise`
  is the symmetric case: a 0.9 m exterior door + a detached 0.2 m
  x 4.0 m noise strip starting 0.15 m past the wall. The
  boundary-adjacency classifier correctly returns "exterior" for
  the outer door side (the strip's boundary doesn't touch the
  bridge); the door survives. Codex P19-D R5 P1 anchor.
- `tests/test_graph_builder.py::test_filter_drops_doors_anchored_to_sub_probe_filtered_strip`
  exercises a 0.04 m x 8.0 m strip (0.32 m², passes polygonize's
  0.25 m² floor but is filtered at 1.0 m²). Strip is thinner than
  any single-point probe distance. Boundary-adjacency detects it
  via shared bridge boundary. Codex P19-D R6 P1 anchor.
- `tests/test_graph_builder.py::test_filter_keeps_real_door_when_filtered_polygon_only_touches_endpoint`
  asserts a noise polygon touching only a bridge endpoint does NOT
  count as bridge-adjacent. Codex P19-D R7 P1 (finding 1) anchor.
- `tests/test_graph_builder.py::test_classify_bridge_side_handles_concave_polygons`
  exercises Codex's exact L-shape reproduction (centroid outside
  the polygon, on the wrong side of the bridge); the local-step
  side resolution returns the correct side regardless. Codex
  P19-D R7 P1 (finding 2) anchor.
- `tests/test_viewer_studio.py::test_post_review_min_room_area_filter_passes_through`
  asserts the form field threads end-to-end.
- `tests/test_viewer_studio.py::test_post_review_invalid_min_room_area_flashes`
  guards against bad form input.
- `tests/test_viewer_studio.py::test_run_meta_persists_tunable_knobs`
  asserts ppm + min_room_area_m2 land in run_meta.json.

### Changed

- `archkg.viewer.studio.run_pipeline` signature: new
  `min_room_area_m2: float = 1.0` keyword threaded into `build_graph`.
- `archkg.viewer.studio._write_run_meta` signature: new
  `points_per_meter` / `min_room_area_m2` optional kwargs.
- `archkg studio` CLI docstring updated to be honest that studio's
  default room-area floor differs from `archkg review` (Codex P19-D
  R1 wording feedback).
- pyproject version 1.2.1 → 1.2.2.

### Why 1.0 m² as the default

Demo's smallest room is 14.75 m² so the floor doesn't touch synthetic
fixtures. CAD-export noise polygons (window frames, dim boxes, toilet
enclosures) are typically 0.3–0.8 m². Real Chinese residential rooms
are ≥4 m² (smallest valid bedroom under GB 50096 is ~5 m²). 1.0 m² is
a conservative floor: aggressive enough to cut obvious noise, safe
enough to never drop a real room. A user with an unusually noisy plan
can bump it to 4.0 via the studio form; a user wanting to inspect
every detected polygon sets 0.

The Medfield-PDF re-test is left as a runtime check the user can
perform on their own real PDF — bench numbers in this file would be
out of date the next time the polygonize floor or door-gap logic
changes.

## v1.2.1 — 2026-04-26 — Real-PDF readiness: scale + entity sanity check

A real CAD PDF (Medfield 16-unit apartment plan, 8.5k vector paths)
ran through v1.2.0's studio without crashing but produced 169 rooms
and 204 doors — clear over-segmentation — and 89 spurious door-width
violations clustered at 0.80–0.83 m. A non-technical user reading
that report would be misled. v1.2.1 surfaces the noise BEFORE the
user trusts the rule output.

### Added

- **`points_per_meter` form field** on the studio upload form
  (default 50.0). Real-world CAD exports use varied scales — Archicad
  / Revit metric exports cluster around 50 ppm, AutoCAD imperial
  exports closer to 72 pt/inch. Without this knob the only path to a
  correct scale was the CLI.
- **"🔍 仅识图模式" checkbox** runs `extract` + `build_graph` +
  overlay only, skips rule evaluation. The result page renders with a
  banner indicating inspect-only mode and a minimal report listing
  entity counts. Lets users sanity-check what the builder detected
  before trusting any rule fire on those entities.
- **Quality flags on the result page**: when `rooms > 50` or
  `doors > 50` (typical residential plan rarely exceeds either), or
  when `corridors == 0 and rooms > 0`, an orange banner at the top of
  the viewer warns about builder over-segmentation. Same flags surface
  in `PipelineResult.quality_flags`.
- 5 new tests in `tests/test_viewer_studio.py` for the inspect_only
  redirect path, the bad-ppm flash path, direct exercise of
  `_compute_quality_flags` against synthetic graphs and a typed
  `EntityGraph` (Codex R1 P2), and a regression test that the
  standalone `archkg viewer` re-render path also honours
  `inspect_only` (Codex R2 P0).
- Documented case study in `READINESS.md` showing the Medfield
  numbers and what the new knobs do.
- **`run_meta.json` marker** persisted next to the artifacts so any
  re-render path (studio's own pre-render + standalone `archkg
  viewer`) honours `inspect_only` mode. Without this, `archkg viewer
  <run-dir>` re-rendered an inspect-only run as a misleading green
  "0 violations = clean review" page (Codex R2 P0). Schema:
  `{"mode": "inspect_only" | "full", "quality_flags": [...]}`.
  `archkg/viewer/server.py:_render_index` reads it; missing file
  falls back to `mode="full"` so historical run dirs still open.

### Changed

- `run_pipeline` signature: new `inspect_only: bool = False` keyword,
  plus result fields `room_count` / `door_count` / `corridor_count` /
  `quality_flags`. Backward-compatible default behaviour.
- `_compute_quality_flags` accepts the typed in-memory `EntityGraph`
  directly so a future serialisation shape change can't silently
  bypass the safeguard. A `dict` fallback is preserved for tests
  with synthetic graphs (Codex R1 P2).
- Viewer template (`index.html.j2`) renders inspect-only mode as
  unmissable: orange banner, header badge, pipeline steps 3-5 marked
  `⊘ skipped`, stats tile shows `N/A` instead of a green "0 issues",
  section ④ explicitly says "规则评估未执行", section ⑤ relabelled
  "源图副本（无标注，规则未跑）". Full review mode unchanged.
- `archkg/viewer/server.py:_render_index` now reads `run_meta.json`
  and forwards `mode` + `quality_flags` to the template.
- pyproject version 1.2.0 → 1.2.1.

### Not yet done (v1.2.x candidates)

- Builder-side noise rejection (min-room-area filter, door context
  validation): would meaningfully reduce the false-positive count on
  the same Medfield PDF, but harder to ship safely without breaking
  the synthetic test cases.
- Region awareness (skip GB rules entirely for non-Chinese plans).
- Auto scale detection from dimension annotations on the page.

## v1.2.0 — 2026-04-26 — Studio upload UI for first-time users

The first end-to-end browser experience. Phase 19-B.

### Added

- `archkg studio` CLI launches a Flask app on port 8765 with a drag-drop
  PDF upload form, optional ProjectMeta / room / stair schedule uploads,
  and a "跑内置 demo" button that runs `samples/sample_clean.pdf` for
  zero-setup visitors.
- POST `/review` runs the same in-process pipeline as `archkg review`
  (extract → build_graph → apply schedules → evaluate → annotate →
  report) and redirects to the existing read-only viewer rendered into
  per-run isolated output dirs under `tmp/studio/runs/<run_id>/`.
- Public `archkg.viewer.studio.run_pipeline()` factored out of the
  Typer CLI so the studio's HTTP handler and the existing CLI now
  share one review entry point.
- `tests/test_viewer_studio.py` smoke tests cover index render, demo
  run, full upload (with PARTIAL_AUTODETECT + STAIR_PENDING rules
  unlocking), bare-PDF upload, and the missing-PDF flash error path.
  6 new tests — Flask `test_client`, no real socket bound.

### Changed

- `Flask>=3.0` added to `[project.dependencies]`.
- README rewritten with the studio as the primary 30-second path; CLI
  workflow demoted to "selection 2" but kept intact.

## v1.1.1 — 2026-04-26 — README

- README.md added (the repo previously had READINESS.md and
  CHANGELOG.md but no README, so anyone landing on the repo had no
  quickstart). Documentation only.

## v1.1.0 — 2026-04-26 — Adversarial training lane stable

Rolls up 9 patch ships (v1.0.1 → v1.0.9) into a stable release. The headline
change is the adversarial training lane — examiner ↔ candidate ↔ adjudicator —
which now covers 21 of the 32 targeted rule cards at F1 = 1.00 across a
100-case deterministic battery, with self-auditing infrastructure preventing
silent coverage regressions.

### Added

- **Adversarial training lane** (Phase 18-D, v1.0.4)
  - `archkg adversarial run -n N --seed S` deterministic battery generator
  - L1 examiner samples PDF + ProjectMeta + room/stair schedules from a seed,
    predicts ground-truth violations from sampled parameters, runs the live
    review pipeline, scores per-rule TP/FN/FP via set-based adjudication.
  - `examiner.predict_expected_violations(p)` mirrors `rule_cards.yaml`
    semantics; pinned by parametrized live-engine semantic test that compares
    predictor against compiled `logic_expression` for every targeted rule.
- **Sample-stratification audit** (Phase 18-I, v1.0.9)
  - `archkg adversarial sample-stats -n N --seed S` audits per-rule case rate
    + occurrence load over a pure predictor sweep (<1s for 1000 seeds).
  - `TARGETED_RULES` module-level constant in `archkg.adversarial.examiner` —
    single source of truth shared by predictor, audit test, and the CLI.
  - Regression test (`test_predictor_fire_rates_meet_minimum_floor`) asserts
    every targeted rule fires on at least 5 % of cases over 1000 seeds and
    that the predictor never emits a rule outside `TARGETED_RULES`.
- **Schedule augmentation lanes** (Phase 18-B/C, v1.0.2/v1.0.3)
  - `--room-schedule`: augments rooms with `net_height_m` / `level` /
    `pitched_roof` / `majority_net_height_m` (Pydantic `extra="forbid"`).
  - `--stair-schedule`: materializes Stair entities with placeholder bbox +
    `uncertain=True`; engine emits `bbox=None` for project-skip path so the
    annotator does not stack stair labels at the PDF origin.

### Changed

- **Builder geometry — `polygonize_segments` snaps inputs to the same grid as
  `bridge_door_gaps`** (Phase 18-E, v1.0.5). Previously, off-grid wall fragments
  (e.g. 78.75 pt) and snapped bridges (79 pt / 121 pt) left a sub-pt gap that
  shapely refused to close, causing 5 / 100 adversarial cases to merge bedroom
  + living into one polygon. Single-line fix; battery recall climbs 0.88 → 1.00.
- **Adversarial coverage from 13 → 21 rules** across phases F / G / H:
  - **High-rise project rules** (Phase 18-F, v1.0.6):
    `RC-ELEVATOR-REQUIRED`, `RC-ACCESSIBLE-RESIDENTIAL-7F`,
    `RC-ENTRANCE-PLATFORM-WIDTH-7F`, `RC-WHEELCHAIR-PASSAGE-WIDTH-7F`,
    `RC-REFUGE-LAYER-100M`. Surfaced and fixed an examiner bug where
    35 F / 105.5 m residential was mis-classed as 高层 instead of 超高层.
  - **Evacuation-stair / closed-stairwell / door-to-exit branches**
    (Phase 18-G, v1.0.7): `RC-EVAC-STAIR-TYPE-33M`, `RC-CLOSED-STAIRWELL-21M`,
    `RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB`. Introduced
    `_examiner_height_class(p)` / `_examiner_fire_class(p)` single-source-of-
    truth helpers; writer + predictor + lock-in test all share one decision
    site.
  - **Fire-class sampling** (Phase 18-H, v1.0.8): `fire_class` ∈
    `{一级, 二级, 三级, 四级}` uniformly sampled, exercising the 三/四级
    skip branch of `RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB`. RNG draw appended at
    end of `sample_parameters` to preserve seed → params mapping for every
    pre-existing field.
- **Sample distribution lifts** (Phase 18-I, v1.0.9):
  - `_FLOORS` += 40 (40 F × {2.8, 3.0} = 112.5 / 120.5 m both cross 100 m gate)
    boosts `RC-REFUGE-LAYER-100M` case rate 6.6 % → 16.3 %.
  - `_NET_HEIGHTS` += 1.80 makes `RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0`
    reachable; case rate 0 % → 5.7 % (deterministic).

### Fixed

- **Production-readiness audit** (Phase 18-A, v1.0.1): `BuilderCapabilities`
  now uses `MappingProxyType` for genuinely immutable `entity_fields`;
  `BedroomScheduleEntry` selectors require at least one of `room_id` / `label`
  via `model_validator`; `--room-schedule` rejects without `--project-meta`.
- **Stair schedule project-id gate** (Phase 18-C): `apply_stair_schedule`
  raises `StairScheduleApplyError` when `page_index` mismatches the graph,
  preventing IndexError crashes in the annotator.
- **Stair duplicate-row metric merge** (Phase 18-C R2): `existing_by_id` is
  refreshed after each merge so a second row for the same `stair_id` reads
  the previously merged stair, not the stale builder geometry.
- **Annotator stack at origin** (Phase 18-C R1 P0): rule engine emits
  `bbox=None` when an entity is `uncertain=True` and `bbox == (0, 0, 0, 0)`,
  routing schedule-sourced findings into the annotator's project-level skip
  path.

### Documentation

- `READINESS.md` updated to reference Phase 18 and the adversarial lane.
- This `CHANGELOG.md` (new) summarises v1.0 → v1.1 evolution.

### Stats

- 241 pytest passing (43 net new across Phase 18)
- ruff + mypy(strict, archkg only per CI) clean
- `archkg clause fidelity`: 18 / 18 errors = 0
- `archkg clause readiness`: 14 / 32 rules in AUTODETECTABLE +
  PROJECT_META_DRIVEN + PARTIAL_AUTODETECT + STAIR_PENDING tiers
- Battery (deterministic): 100 cases 985 TP / 0 FN / 0 FP, F1 = 1.00;
  50 cases (regression seed) 506 TP / 0 FN / 0 FP, F1 = 1.00
- Codex review rounds across Phase 18: 13 (9 phases × ~1.4 rounds)
- Tags shipped: v1.0.0 → v1.0.9 + v1.1.0

## v1.0.0 — 2026-04 — 100 % standards coverage milestone

Phases 1 → 17 covered: knowledge base of 30 GB clauses, 32 rule cards,
project-context applicability filtering, clause fidelity audit, BM25 +
verbatim search, room / stair entity rules, feedback recorder. See git log
for individual phase commits.
