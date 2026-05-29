# P78-01 Bundle Opening Provenance Review Queue Summary

## Result

P78-01 adds a dedicated `opening_provenance_triage_queue` to
`archkg handoff-bundle-index`. Packages with weak opening provenance coverage
now produce a reviewer triage item with:

- package name and relative package directory
- reviewer actor and `review_opening_provenance_coverage` action id
- coverage tuple
- source artifact
- human-readable missing-signal reason
- preview-only boundary warning

Bundle Markdown and HTML now render the queue separately from the normal package
`next_action_queue`.

## Boundaries

- No package status, quality, signoff, manager, archive, or normal
  `next_action_queue` semantic changes.
- No source-run or handoff-package mutation.
- No rule-engine, `issues.json`, or `review_state.json` changes.
- No inferred opening provenance.
- No compliance or review-grade BIM claim.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py::test_handoff_bundle_index_emits_opening_provenance_triage_queue tests/test_handoff_bundle.py::test_handoff_bundle_index_markdown_html_show_opening_provenance_triage_queue` failed before implementation with missing `opening_provenance_triage_queue`.
- GREEN check: the same targeted command passed after implementation: 2 passed, 5 warnings.
- Local bundle regression: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py` passed: 5 passed, 5 warnings.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py tests/test_handoff_package.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 42 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 435 passed, 1 skipped, 5 warnings.
