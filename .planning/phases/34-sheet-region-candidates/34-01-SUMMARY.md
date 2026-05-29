# P34-01 SUMMARY: Sheet-Region Candidate Suggestions

## Outcome

Implemented advisory sheet-region candidate generation for full CLI and Studio
review runs.

## Implementation Notes

- Added `archkg.ingest.sheet_region_candidates` to produce
  `sheet_region_candidates.json`.
- Candidates include `design_region`, `title_block`, `schedule`, and `legend`
  regions when evidence exists.
- Candidate evidence includes keyword rows and right-side table/grid signals.
- Each page includes candidate excluded-text summaries outside the suggested
  design region.
- CLI and Studio write the candidate artifact before any manual crop is
  applied.
- Viewer/Studio and standalone `archkg viewer` render a "候选区域" panel.
- Manual `--sheet-region` remains the only path that mutates
  `primitives.json` / graph input.

## Validation

- `python -m ruff check .`
- `python -m mypy archkg`
- `python -m pytest -q`

Result: 319 tests passed.

## Next

Consider a candidate overlay visualization, then move into P35 issue
lifecycle/review-state storage.
