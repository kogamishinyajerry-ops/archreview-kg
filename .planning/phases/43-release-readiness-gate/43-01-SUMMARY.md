# P43-01 SUMMARY: Release Readiness Evidence Gate

## Outcome

Added an evidence-based release/demo readiness gate.

## Implementation Notes

- New `archkg.release_readiness` builds `release_readiness.v1` payloads from benchmark suite results and optional representative run directories.
- New CLI command `archkg release-readiness` accepts either `--manifest` or `--suite-result`, writes JSON / Markdown reports, and exits non-zero only for `not_ready` by default.
- Gate statuses are `not_ready`, `demo_ready_with_known_gaps`, and `evidence_ready`.
- Blockers cover failed active suite, no active cases, no active real drawing benchmark, and missing core artifacts.
- Warnings cover known gaps, pending rows, generated-heavy proof limits, no run directory, and missing optional maturity artifacts.
- Control sync now includes `release_readiness.json` as a known artifact.

## Validation

- `.venv/bin/python -m pytest -q tests/test_release_readiness.py tests/test_control_sync.py`
- `.venv/bin/python -m ruff check archkg/release_readiness.py archkg/cli/main.py archkg/control_sync.py tests/test_release_readiness.py tests/test_control_sync.py`
- `.venv/bin/python -m mypy archkg`
- Representative run smoke:
  - `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p43/readiness_before --project-meta samples/project_meta_demo.yaml --room-schedule samples/room_schedule_demo.yaml --stair-schedule samples/stair_schedule_demo.yaml`
  - `.venv/bin/archkg review samples/sample_clean.pdf -o tmp/p43/readiness_after --project-meta samples/project_meta_demo.yaml --room-schedule samples/room_schedule_demo.yaml --stair-schedule samples/stair_schedule_demo.yaml`
  - `.venv/bin/archkg review-diff tmp/p43/readiness_before tmp/p43/readiness_after -o tmp/p43/readiness_after/review_diff.json`
  - `.venv/bin/archkg release-readiness --manifest samples/understanding_benchmarks/suite_manifest.json --run-dir tmp/p43/readiness_after --out tmp/p43/release_readiness.json --markdown tmp/p43/release_readiness.md`

Smoke result: `release-readiness status=demo_ready_with_known_gaps blockers=0 warnings=3 active=3 real_active=1 known_gap=1`.

Result: targeted tests 11 passed; ruff passed; mypy passed; benchmark suite PASS active=3 pending=1 failed=0 known_gap=1; release-readiness smoke returned `demo_ready_with_known_gaps`; full pytest 367 passed.

## Next

Promote additional real drawing expected inventories from known_gap/pending into active cases, then rerun the release gate before external demo or release claims.
