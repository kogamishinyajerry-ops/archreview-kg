# Quality Review — 2026-05-16 — overall 0/100

- Weakest dimension: kg_persistence (0/10) — tied with 7 other unmeasurable dimensions; scorer reports first-encountered weakest.
- 99+ status: no
- Verification overrides: none (all measurable claims verified against on-disk artifacts; all 0-scored dimensions verified as legitimately unmeasurable)

## Per-dimension audit

**code_quality (9.0/10, measurable):** Verified honest. Re-ran `.venv/bin/python -m pytest -q --no-header --no-summary` and observed `456 passed, 1 skipped, 5 warnings in 33.97s` — exact match to scorer detail. The single point deducted is for the 5 warnings (mostly a `DeprecationWarning: builtin type swigvarlink has no __module__ attribute` from a C extension dependency; not project-owned). ruff and mypy both clean. This dimension is at the ceiling that the current rubric permits without addressing upstream warnings.

**kg_persistence (0.0/10, measurable=false):** Verified honest. Both candidate paths (`/Users/Zhuanz/archreview-kg/.archkg/kg.db` and `/Users/Zhuanz/.archkg/kg.db`) confirmed absent via `ls`. The scorer correctly refuses partial credit and surfaces `status: no_kg_db_found`.

**kg_coverage (0.0/10, measurable=false):** Verified honest. Confirmed `archkg/kg/` directory does not exist; the package layout has `archkg/rules/`, `archkg/knowledge/`, `archkg/schemas/` etc. but no `kg/` subpackage. Scorer correctly returns `kg_store_module_missing` on `ImportError`.

**cross_project_query (0.0/10, measurable=false):** Verified. `.planning/m5/canonical_queries.json` does not exist (directory listing shows only `baseline_quality_score.json` and now this review file). Honest 0.

**web_ui_e2e (0.0/10, measurable=false):** Verified. `archkg.kg.web` module cannot exist because `archkg.kg` itself does not exist. Honest 0.

**recognition_quality (0.0/10, measurable=false):** Verified. Same root cause — `archkg.kg.recognition_quality` requires the KG package which is absent. Honest 0.

**real_pdf_breadth (2.0/10, measurable):** Verified honest. Parsed `samples/understanding_benchmarks/suite_manifest.json`: 7 total cases, 3 with `fixture_kind` starting `real_public` AND `status==active` (medfield-a1-first-floor, medfield-a2-second-floor, medfield-full-plan-set-multi-plan-intake). Score = `min(10, 3/15 * 10) = 2.0` — math is correct against the M5 blueprint target of 15.

**calibration (0.0/10, measurable=false):** Verified. `archkg.kg.calibration` blocked by absent kg package. Honest 0.

**feedback_loop (0.0/10, measurable=false):** Verified. `archkg.kg.feedback` blocked by absent kg package. Honest 0.

**documentation_honesty (10.0/10, measurable):** Verified honest. Confirmed `READINESS.md` (463 lines) and `README.md` (649 lines) both exist. Confirmed rule_cards.yaml parses to exactly 32 cards (matches scorer detail). Grep for forbidden phrases (`production ready`, `battle tested`, `fully automated review`, `replaces human reviewer`, `100% precision`, `100% recall`, `15 real`, `20 real`) returned zero unhedged matches; READINESS.md TL;DR explicitly states "only 4 张能在任何 PDF 上直接自动判定违规 (≈ 12.5%)" — the opposite of overclaiming. The 10/10 is earned, not gifted.

## Recommended next phase

**Build M5.A — KG Persistence Layer.** This is the single load-bearing dependency: 5 of the 10 dimensions (kg_persistence, kg_coverage, cross_project_query, web_ui_e2e, recognition_quality, calibration, feedback_loop — actually 7) are blocked behind the absence of `archkg/kg/store.py`. Even a minimal SQLite-backed schema (`project`, `drawing`, `entity`, `issue`, `rule`, `clause`, `run` tables) with `KGStore.health_check()` exposing `required_tables_present` and `query_p95_ms` would lift kg_persistence from 0 → ~8-10 and unblock kg_coverage measurement against the existing `tests/fixtures/**/issues.json` and `samples/understanding_benchmarks/**/issues.json` runs. The smallest change that lifts the weakest dimension by ≥2 points: create `archkg/kg/__init__.py` + `archkg/kg/store.py` with the minimum schema, then run `archkg kg init` to materialize `.archkg/kg.db`. Per the meta-rule `overall = min(sum, weakest * 10)`, the project will remain capped at 0 until any non-code-quality measurable dimension exits 0.

## Blockers

- **No `archkg/kg/` package exists** — blocks 7 dimensions (persistence, coverage, query, web, recognition, calibration, feedback). Must build M5.A first.
- **No `.planning/m5/canonical_queries.json`** — blocks cross_project_query even after M5.A lands. Author the 10 hand-computed expected-answer queries alongside or immediately after M5.C.
- **Real-public-PDF inventory is 3/15** — blocks real_pdf_breadth from exceeding 2.0/10 until 12 additional public PDFs are sourced and benchmarked. Per M5 blueprint risk register, accept smaller increment with explicit subscore loss rather than faking counts.
- **5 pytest warnings cap code_quality at 9** — surfaceable but low priority; the `swigvarlink` DeprecationWarning originates from a C extension and may require a filterwarnings suppression with documented rationale before code_quality can reach 10/10.
- **Meta-rule weakest-dimension cap** — until every dimension is ≥9 the overall cannot exceed `weakest * 10`. Current overall 0 will remain at 0 until M5.A ships.
