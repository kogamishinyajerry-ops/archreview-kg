# Changelog

All notable changes to ArchReview-KG. Version tags follow `v<major>.<minor>.<patch>`;
patch releases (`v1.0.x`) are individual ship phases reviewed by Codex GPT-5.4,
minor releases (`v1.1.0` / `v1.2.0`) are stable milestones rolling up multiple patches.

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
