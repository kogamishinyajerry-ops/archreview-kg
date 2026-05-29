# P41-04 SUMMARY: Issue Preview Cross-Highlighting

## Outcome

Added issue-to-preview cross-highlighting in Viewer/Studio.

## Implementation Notes

- New `archkg.viewer.issue_focus` builds normalized first-page focus rectangles from primary issue bboxes.
- Viewer/Studio render "定位图面" controls on focusable issue rows.
- The layer preview now has a non-mutating focus rectangle overlay shared by source, entity overlay, and annotated preview.
- Non-page-0 and invalid-bbox issues are omitted from focus to avoid false localization.
- No rule output, `issues.json`, `review_state.json`, or per-sheet preview issue semantics changed.

## Validation

- `.venv/bin/python -m pytest -q tests/test_viewer_issue_focus.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors`
- `.venv/bin/python -m pytest -q tests/test_viewer_issue_focus.py tests/test_viewer_studio.py tests/test_review_pipeline.py tests/test_control_sync.py`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p41/issue_focus_smoke`
- `.venv/bin/python -c 'from pathlib import Path; from archkg.viewer.server import _render_index; _render_index(Path("tmp/p41/issue_focus_smoke"), Path("samples/sample_clean.pdf"))'`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p41/suite_result_p41_04.json --markdown tmp/p41/suite_result_p41_04.md`
- `.venv/bin/python -m pytest -q`

Result: targeted tests 4 passed; touched-file tests 43 passed; ruff passed; mypy passed; static viewer smoke rendered issue focus controls in `index.html`; benchmark suite PASS active=3 pending=1 failed=0 known_gap=1; full pytest 350 passed.

## Next

Move to P42 rerun diff/resolution tracking, or first add multi-page preview navigation if visual focus needs to cover multi-page sheets.
