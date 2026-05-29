# P57-01 Summary: Multi-Page Preview Gallery

## Delivered

- Added `archkg.viewer.preview_pages` to render source/annotated PDFs into page-indexed PNG sets while keeping legacy first-page filenames.
- Added `preview_pages.json` and loader normalization for old runs.
- Wired Studio and standalone Viewer to write/load preview page manifests.
- Updated issue focus to use preview availability, so non-first-page issues can be marked as directly preview-supported when source/annotated page PNGs exist.
- Updated the result page with page-switch controls, page-aware image selection, and direct non-first-page issue highlighting.
- Updated README, readiness notes, changelog, roadmap, and state.

## Guardrails

- `entity_overlay.png` remains page-0 only in P57.
- Preview pages are navigation artifacts only; they do not create new graph evidence, issue evidence, review-state decisions, or compliance proof.
- Legacy `source_preview.png` and `annotated_preview.png` remain the page-1 filenames for old links and handoff compatibility.

## Validation

- `pytest tests/test_viewer_preview_pages.py tests/test_viewer_issue_focus.py tests/test_viewer_studio.py -q` -> 38 passed.
- `ruff check .` -> passed.
- `mypy archkg` -> passed.
- Multi-page Studio smoke with `samples/generated_complex_sheet_set.pdf` -> generated `preview_pages.json`, page-count 4, four source preview pages, four annotated preview pages, and page-switch controls in `index.html`.
- `archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json` -> PASS active=7 pending=0 failed=0 known_gap=0.
- `archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p54/handoff_run` -> evidence_ready, blockers=0, warnings=0, active=7, real_active=3, known_gap=0.
- `pytest -q` -> 391 passed.
