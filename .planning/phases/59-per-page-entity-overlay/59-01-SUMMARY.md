# P59-01 Summary: Per-Page Entity Overlay Rendering

## Delivered

- Added `render_entity_overlay_preview_pages()` to render one overlay PNG per graph-backed page while preserving `entity_overlay.png` for the primary graph.
- Extended `preview_pages.json` generation so the overlay layer can list multiple pages and report multi-page overlay availability.
- Updated Studio to render overlay previews from the primary graph plus routed sheet graphs.
- Updated standalone viewer serving to regenerate overlay previews from `entity_graph.json` and `sheet_graphs.json`.
- Added regression coverage for helper output, real multi-page Studio output, viewer HTML references, and handoff copying of non-first-page overlay assets.
- Updated README, readiness notes, changelog, roadmap, and state.

## Guardrails

- Entity overlay previews are visual reviewer aids only; they do not add detections, change rule output, or certify drawing compliance.
- Overlay pages exist only for graph-backed sheets. Pages without a routed graph still require source/annotated/PDF review.
- Per-sheet preview issues remain separate from primary `issues.json` and `review_state.json`.

## Validation

- `pytest tests/test_viewer_preview_pages.py tests/test_viewer_studio.py::test_run_pipeline_writes_multi_page_entity_overlay_manifest tests/test_viewer_studio.py::test_standalone_viewer_renders_second_page_issue_focus tests/test_handoff_package.py::test_handoff_package_copies_multi_page_preview_assets -q` -> 5 passed.
- Real multi-page Studio smoke from `samples/generated_complex_sheet_set.pdf` wrote source/annotated previews for 4 pages and overlay previews for graph-backed pages 1 and 3.
- `pytest tests/test_viewer_preview_pages.py tests/test_viewer_studio.py tests/test_handoff_package.py -q` -> 54 passed.
- `ruff check .` -> passed.
- `mypy archkg` -> passed.
- Multi-page handoff smoke copied `entity_overlay_page_3.png` into the package and `handoff-check` returned `handoff_ready`.
- `archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json` -> PASS active=7 pending=0 failed=0 known_gap=0.
- `archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p54/handoff_run` -> evidence_ready, blockers=0, warnings=0, active=7, real_active=3, known_gap=0.
- `pytest -q` -> 395 passed.
