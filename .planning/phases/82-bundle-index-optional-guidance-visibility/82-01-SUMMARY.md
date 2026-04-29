# P82-01 Bundle Optional Guidance Visibility Summary

## Result

P82-01 adds bundle-level visibility for package-index optional opening
provenance guidance. `handoff_bundle_index.json` now includes:

- `summary.package_index_optional_guidance_package_count`
- `summary.package_index_optional_guidance_action_total`
- per-package guidance availability/path/reason fields
- a separate `package_index_optional_guidance_queue`

Bundle Markdown and HTML render a `Package Index Optional Guidance` section with
package name, action count, index link, runbook optional-section link, and
reason. The normal `next_action_queue` remains unchanged.

## Boundaries

- No package status, next actor, or normal next-action changes.
- No manager readiness changes.
- No package or source-run mutation.
- No rule-engine, `issues.json`, or `review_state.json` changes.
- No inferred opening provenance.
- No compliance, BIM completeness, or review-grade IFC claim.

## Verification

- RED check: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py::test_handoff_bundle_index_surfaces_package_index_optional_guidance` failed before implementation with missing `package_index_optional_guidance_package_count`.
- GREEN check: the same targeted command passed after implementation: 1 passed, 5 warnings.
- Local targeted regression: `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py tests/test_handoff_package.py::test_handoff_bundle_index_summarizes_multiple_packages_without_mutation tests/test_handoff_package.py::test_handoff_bundle_index_routes_next_actor_to_manager_and_archive tests/test_handoff_package.py::test_handoff_bundle_index_cli_writes_json_markdown_and_html` passed: 9 passed, 5 warnings.
- `git diff --check` passed.
- `./.venv/bin/python -m ruff check .` passed.
- `./.venv/bin/python -m mypy archkg` passed.
- `./.venv/bin/python -m pytest -q tests/test_handoff_bundle.py tests/test_handoff_package.py tests/test_reviewer_task_checklist.py tests/test_ifc_layout_export.py tests/test_viewer_studio.py::test_standalone_viewer_renders_sheet_classification_and_missing_warning` passed: 48 passed, 1 skipped, 5 warnings.
- `./.venv/bin/python -m pytest -q` passed: 439 passed, 1 skipped, 5 warnings.
