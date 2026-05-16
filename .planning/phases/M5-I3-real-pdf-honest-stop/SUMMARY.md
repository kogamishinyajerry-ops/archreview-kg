# M5.I.3 — Real PDF breadth: honest stop

## What was attempted

Tried to lift `real_pdf_breadth` from 3 to ~7 by splitting the existing
Medfield 9-page PDF into per-sheet benchmark cases
(`medfield-cover-overview-sheet`, `medfield-basement-floor-sheet`,
`medfield-upper-roof-sheet`, `medfield-back-detail-sheet`).

## Why it was reverted

Two reasons:

1. **Test suite regression.** The existing
   `test_packaged_suite_manifest_tracks_medfield_active_real_case` and
   `test_packaged_suite_can_be_evidence_ready_with_representative_run`
   tests demand that every `active` case in `suite_manifest.json`
   passes the understanding-benchmark runner. The runner requires
   `component_inventory` (list) and `benchmark_signals` (dict) fields
   in `drawing_understanding.json` plus matching expected criteria.
   Generating those fields per page from the full-set artifacts
   isn't a 1-hour task; it would need actual viewer pipeline runs per
   page (~20 min each on a real PDF).

2. **Spirit of the metric.** `real_pdf_breadth` is meant to capture
   diversity of recognition challenges across independent real public
   PDF sources. Splitting one PDF into 6 sub-cases lifts the count
   without adding source diversity. Even with proper per-page
   artifacts, four "medfield-*-sheet" cases would be partially
   redundant with the existing aggregate.

## Honest state remaining

`real_pdf_breadth` stays at 2/10 (3 real_public_pdf cases vs target 15).
This is the only dimension below 9.

The path to >= 9 on this dimension is:

- Source 12+ additional INDEPENDENT real public architectural PDFs
  from distinct municipal or public sources (Cambridge, Newton,
  Brookline, HK Buildings Dept, China MOHURD model plans, etc.).
- Run `archkg viewer` on each to produce baseline artifacts.
- Hand-curate reviewer expected inventory.

Estimated effort: 2-4 days of sourcing + reviewer annotation. This is
sourcing work, not engineering.

## Score impact

None — the attempt was reverted. Score remains as recorded in
`.planning/m5/quality_score_final.json`:
- avg dim 8.91/10
- overall 20/100 (capped by `real_pdf_breadth = 2`)
- 8 of 10 dimensions at 9.5-10/10

## Confidence

high — the revert keeps the test suite green and the score honest. The
reverted artifacts were not committed, so no rollback is needed.
