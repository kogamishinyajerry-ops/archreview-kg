# M5.A.1 — KGStore schema + health_check + `archkg kg init`

## What landed

- `archkg/kg/__init__.py` and `archkg/kg/store.py`: SQLite-backed graph
  store. Schema kg.v1 with 12 tables (project / drawing / sheet / run /
  rule / clause / entity / issue / reviewer / feedback_event / edge /
  schema_version). WAL mode, foreign keys enforced.
- `archkg kg init` and `archkg kg status` CLI commands.
- `.archkg/` added to .gitignore — per-developer local state.
- 14 tests for KGStore behaviour (schema, upserts, FK enforcement, WAL mode).

## Score delta

- `kg_persistence`: 0 → 10 (was unmeasurable, now measurable and passing).
- All other dimensions unchanged.
- `kg_coverage` still 0 because the scorer counts `issues.json` files in
  fixture run dirs, but most benchmark dirs only contain
  `drawing_understanding.json`. M5.A.2 will add ingest + (if needed) broaden
  the scorer's "ingestable run" definition.

## What does NOT yet exist

- No ingest path from run_dir JSON into the KG. The KG is initialised but
  empty against any real project.
- No query layer (M5.C).
- No web UI (M5.D).

## Tests

- 470 existing pre-M5 tests still pass.
- 14 new KGStore tests.
- 14 quality-score tests (from M5.F.0).

## Confidence

high — the schema is conservative SQL with strict FK semantics, all changes
are additive, and no existing module imports were modified.
