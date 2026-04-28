# P56-01 Summary: Sheet-Aware Issue Focus

## Delivered

- Added tests for page-aware issue focus payloads and unmapped-page diagnostics.
- Updated Viewer/Studio issue focus data so each primary issue bbox is normalized against its own `page_index`.
- Preserved page-0 preview-layer highlighting, while non-page-0 issues now show their correct page and route reviewers to `source.pdf` / `annotated.pdf` review instead of being projected onto the first-page PNG.
- Added omitted issue diagnostics for missing bbox, missing page dimensions, and invalid bbox.
- Updated README, readiness notes, changelog, roadmap, and state.

## Guardrails

- Page-aware issue focus is reviewer navigation only; it does not create, confirm, reject, resolve, or aggregate issues.
- Static source/overlay/annotated PNG previews still render page 0 only.
- Non-page-0 issue focus deliberately avoids drawing a highlight box on the page-0 preview.

## Validation

- `pytest tests/test_viewer_issue_focus.py tests/test_viewer_studio.py -q` -> 35 passed.
- `ruff check .` -> passed.
- `mypy archkg` -> passed.
- Representative `archkg review samples/generated_complex_sheet_set.pdf -o tmp/p56/focus_run --project-meta samples/project_meta_demo.yaml --min-room-area-m2 1.0` -> passed and rendered page-aware viewer HTML via `_render_index`.
- Viewer smoke found `data-focus-page-index`, PDF links, and the non-first-page focus guidance string in `tmp/p56/focus_run/index.html`.
- `archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json` -> PASS active=7 pending=0 failed=0 known_gap=0.
- `archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p56/focus_run` -> demo_ready_with_known_gaps, blockers=0, warnings=1 because the smoke run intentionally lacks `review_diff.json`.
- `archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p54/handoff_run` -> evidence_ready, blockers=0, warnings=0, active=7, real_active=3, known_gap=0.
- `pytest -q` -> 388 passed.
