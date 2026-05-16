# M5.D — Flask web UI with 5 reviewer flows

## What landed

- `archkg/kg/web.py`: minimal Flask app (no React, no build step). Five
  flows on five endpoints:
  - `GET /` – static HTML index with vanilla JS table renderer.
  - `GET /api/projects` – list projects with drawing + issue counts.
  - `GET /api/projects/<slug>/drawings` – drawing browser per project.
  - `GET /api/heatmap` – rule trigger counts by status.
  - `GET /api/issues/<id>` – full issue lineage (rule, project, evidence,
    feedback events).
  - `POST /api/issues/<id>/feedback` – reviewer annotation, validates
    event type and reviewer.
- `run_e2e_smoke()` — exercises all 5 (+ index) via Flask test client
  and returns timings consumed by the `web_ui_e2e` scoring dimension.
- `archkg kg serve --db ...` and `archkg kg smoke --db ...` CLI.
- 12 new web tests covering each endpoint, error paths, and the smoke
  flow.

## Score delta (full --full snapshot)

| dim                  | pre   | post   |
| -------------------- | ----- | ------ |
| web_ui_e2e           | 0/10  | 10/10  |
| overall              | 0/100 | 20/100 |
| avg dim              | 8.2   | 9.1    |

Overall jumps from 0 to 20 because every dim is now > 0, but the
meta-rule cap (overall <= weakest_dim * 10) still pins overall at 20
because `real_pdf_breadth` stays at 2.

## What blocks 99+

Only `real_pdf_breadth`. The rubric requires 15 active real public PDFs;
the active suite has 3 (Medfield A-1, A-2, full-plan-set). This is a
sourcing+annotation grind that needs network access and per-case
expected inventory. Lowering the threshold would be cheating per the
"absolutely honest" mandate.

## Tests

- 522 tests pass (was 510).
- 12 new web tests.

## Confidence

high — every endpoint has positive and negative test coverage; the
smoke runner deliberately fails the 3 data-dependent flows on an empty
KG so the dimension can't be silently passed when data is missing.
