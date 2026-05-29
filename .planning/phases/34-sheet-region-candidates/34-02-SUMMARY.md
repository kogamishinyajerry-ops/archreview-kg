# P34-02 SUMMARY: Candidate Overlay Visualization

## Outcome

Implemented visual overlay rendering for sheet-region candidates.

## Implementation Notes

- Added `archkg.annotate.sheet_region_overlay`.
- CLI and Studio review runs now write
  `sheet_region_candidates_overlay.png`.
- The overlay draws deterministic color-coded boxes for candidate kinds:
  design region, title block, schedule, and legend.
- Viewer/Studio result pages render the overlay inside the "候选区域" panel
  when present.
- This remains advisory only; no candidate is applied unless the user
  explicitly supplies `--sheet-region`.

## Validation

- `python -m ruff check .`
- `python -m mypy archkg`
- `python -m pytest -q`

Result: 320 tests passed.

## Next

Enter P35-01: issue lifecycle / review-state storage.
