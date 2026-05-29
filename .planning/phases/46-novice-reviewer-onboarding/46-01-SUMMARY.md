# P46-01 SUMMARY: Novice Reviewer Onboarding Pack

## Outcome

Added a generated reviewer onboarding pack so a new plan-review engineer can open a run and follow a first-hour evidence review path.

## Implementation Notes

- New `reviewer_onboarding.json` captures first-hour steps, artifact map, common commands, do-not-claim boundaries, and handoff checklist.
- New `reviewer_quickstart.md` renders the same guidance as a human-readable checklist.
- CLI full review, Studio full review, and Studio inspect-only runs write the onboarding artifacts.
- `report.md` includes a “新手审图上手包” section with the first-hour flow.
- Viewer/Studio renders a “新手上手” panel and links to both onboarding artifacts.
- Release-readiness and control-sync now track the onboarding artifacts as maturity evidence.

## Validation

- `.venv/bin/python -m pytest -q tests/test_review_pipeline.py::test_review_end_to_end_flags_corridor_and_doors tests/test_review_pipeline.py::test_report_md_contains_clause_text tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning`
- `.venv/bin/python -m pytest -q tests/test_review_pipeline.py tests/test_viewer_studio.py tests/test_control_sync.py tests/test_release_readiness.py`
- `.venv/bin/python -m ruff check archkg tests`
- `.venv/bin/python -m mypy archkg`
- `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p46/reviewer_onboarding_run --project-meta samples/project_meta_demo.yaml --room-schedule samples/room_schedule_demo.yaml --stair-schedule samples/stair_schedule_demo.yaml`
- `.venv/bin/archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p46/reviewer_onboarding_run --out tmp/p46/release_readiness_p46_01.json --markdown tmp/p46/release_readiness_p46_01.md`
- `.venv/bin/archkg understanding-benchmark-suite --manifest samples/understanding_benchmarks/suite_manifest.json --out tmp/p46/suite_result_p46_01.json --markdown tmp/p46/suite_result_p46_01.md`
- `.venv/bin/python -m pytest -q`

Result: targeted RED/GREEN tests passed; affected test group 50 passed; ruff passed; mypy passed; demo run wrote onboarding artifacts; Viewer smoke found the onboarding panel; benchmark suite PASS active=5 pending=0 failed=0 known_gap=0; release-readiness returned `evidence_ready` with blockers=0 warnings=0 active=5 real_active=2 known_gap=0; full pytest 369 passed.

## Next

Continue toward handoff-ready maturity by adding either another reviewed real complex benchmark or a bounded per-sheet preview review bridge that keeps preview issues separate from primary lifecycle until explicitly promoted.
