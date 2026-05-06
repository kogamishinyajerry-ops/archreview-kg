# P85-01 Bundle Manager Triage Digest Summary

## Result

P85-01 adds a derived manager digest to bundle indexes.

- `handoff_bundle_index.v1` now includes `manager_triage_digest`.
- The digest summarizes existing queue counts for:
  - `next_action_queue`
  - `opening_provenance_triage_queue`
  - `package_index_optional_guidance_queue`
  - `optional_guidance_note_closeout_queue`
- Digest items include package, category, actor, title, reason, severity, source
  queue, and optional command/path fields.
- Bundle Markdown and HTML now render a `Manager Triage Digest` section.

## Boundaries

- No package artifact mutation.
- No source-run mutation.
- No package-status, readiness, next-actor, next-action, manager-checklist, or
  archive semantic changes.
- No `issues.json` or `review_state.json` changes.
- No compliance, issue-confirmation, BIM, or rule-engine claim.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py::test_handoff_bundle_index_writes_manager_triage_digest_without_changing_queues` failed before implementation because `manager_triage_digest` did not exist.
- GREEN check: the same targeted command passed after implementation.
- Local targeted regression:
  `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py tests/test_handoff_package.py`
  passed: 43 passed, 5 warnings.
- `git diff --check` passed.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- Targeted handoff/viewer regression passed:
  `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py tests/test_handoff_package.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning`
  passed: 44 passed, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 442 passed, 1 skipped, 5 warnings.
