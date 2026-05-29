# M5.C — Query layer + canonical queries + filter CLI

## What landed

- `archkg/kg/query.py`: 10 canonical queries each implemented with both a
  SQL path and an independent Python ground-truth path. A query is reported
  "correct" only when SQL and Python agree row-for-row. No partial credit.
- `archkg kg query --rule X --status Y --project Z`: free-form filter
  surface over the issue → rule → run → project join.
- `archkg kg canonical-queries-run`: dev tool to run all 10 canonical
  queries against the live KG.
- `.planning/m5/canonical_queries.json`: manifest used by the scorer; only
  carries IDs + descriptions so the SQL/Python pair cannot drift.
- `score_cross_project_query()` rewired to pass `db_path` explicitly and
  unwrap `{"queries": [...]}` manifest format.
- 11 new query-layer tests.

## Score delta

- `cross_project_query`: 0 → 10/10.
- All other dims unchanged.
- Overall still capped at 0/100 because 4 dims (web_ui_e2e,
  recognition_quality, calibration, feedback_loop) remain 0.

## Canonical queries Q1-Q10

| ID  | Description |
| --- | ------------- |
| Q1  | Issue count per rule |
| Q2  | Issue count per project |
| Q3  | Issue count by status |
| Q4  | Top 5 (rule, clause) pairs (Python-only placeholder until clause edge land) |
| Q5  | Confirmed issues across all projects |
| Q6  | Project with most issues |
| Q7  | Rule with most rejections |
| Q8  | Orphaned issues (no linked entity_id) |
| Q9  | Distinct clauses per rule by standard prefix |
| Q10 | Issue density per drawing |

## Tests

- 491 tests pass (was 480).
- 11 new query tests; all pass.

## Confidence

high — every canonical query is cross-checked against an independent
Python implementation; failures cannot be silent. The CLI filter is read-only
and uses parameterised SQL.
