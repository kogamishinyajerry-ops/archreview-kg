# P53-01 Summary: Archive Manifest Checksums

## Delivered

- Added `handoff_archive_manifest.v1` with per-file SHA-256, byte size, role, excluded generated paths, and deterministic `package_digest`.
- Added `archkg handoff-archive-manifest` for package-local archive manifest generation.
- Updated handoff static `index.html` to surface archive status, digest, file count, and JSON/Markdown links.
- Updated README, reviewer playbook, readiness notes, changelog, roadmap, and state.

## Guardrails

- The archive manifest writes only inside the handoff package.
- It excludes itself and package-root `index.html` to avoid checksum loops.
- `archive_manifest_ready` is transfer-integrity evidence only, not drawing-compliance evidence.

## Validation

- `pytest tests/test_handoff_package.py tests/test_review_pipeline.py tests/test_release_readiness.py tests/test_control_sync.py -q` -> 34 passed.
- `ruff check .` -> passed.
- `mypy archkg` -> passed.
- Representative chain passed: review, review-diff, release-readiness, handoff package, handoff-check, handoff-signoff, handoff-manager-checklist, handoff-archive-manifest, static index grep, understanding benchmark suite.
- `pytest -q` -> 384 passed.
