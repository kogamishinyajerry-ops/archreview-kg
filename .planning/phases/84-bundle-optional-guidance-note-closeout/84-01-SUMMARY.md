# P84-01 Bundle Optional Guidance Note Closeout Summary

## Result

P84-01 adds bundle-level closeout visibility for optional guidance review notes.

- `archkg handoff-bundle-index` now reads package-local
  `handoff_optional_guidance_note.json` when package-index optional guidance is
  available.
- Bundle summary now includes optional guidance closeout counts:
  `reviewed`, `needs_info`, `blocked`, `not_recorded`, and `invalid`.
- Per-package status fields and optional guidance note metadata are included in each
  package row.
- `handoff_bundle_index` now renders an independent
  `optional_guidance_note_closeout_queue` in JSON, Markdown, and HTML.

## Boundaries

- No package-level status mutation.
- No package-status / readiness / next-actor / next-action changes.
- No manager checklist, archive checks, source-run, `issues.json`, or
  `review_state.json` mutations.
- No automatic creation of optional guidance notes.
- No requirement to treat missing/needs_info/blocked notes as compliance blockers.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py::test_handoff_bundle_index_summarizes_optional_guidance_note_closeout` failed before implementation because bundle closeout summary fields and queue were absent.
- GREEN check: the same targeted command passed after implementation.
- Local targeted regression:
  `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py tests/test_handoff_package.py`
  passed with added assertions for optional guidance note closeout counts and queue rendering.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q` passed.
