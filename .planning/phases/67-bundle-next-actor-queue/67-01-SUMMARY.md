# P67-01 SUMMARY: Bundle Next-Actor Queue

## Completed

- `archkg handoff-bundle-index` now derives per-package `next_actor`, `next_action_id`, `next_action_title`, `next_action_reason`, and `next_action_command`.
- Bundle JSON now includes structured `next_action_queue` while preserving the legacy text `next_actions` list.
- Bundle summary now counts reviewer, manager, archive, and done next actors.
- Bundle Markdown and HTML render next actor/action columns.
- Tests cover reviewer routing for incomplete packages, manager routing after reviewer closeout, archive routing after manager intake, and done routing for fully verified packages.

## Boundary

The next-actor queue is read-only dispatch guidance. It does not mutate package artifacts, source run artifacts, primary `review_state.json`, primary `issues.json`, candidate issue truth, package readiness semantics, or drawing-compliance status.

## Validation

- `.venv/bin/python -m pytest tests/test_handoff_package.py -q`: 30 passed, 5 warnings.
- `.venv/bin/python -m ruff check .`: passed.
- `.venv/bin/python -m mypy archkg`: passed.
- Command smoke: bundle index over reviewer/manager/archive packages produced next_actor counts 1/1/1 and structured `next_action_queue` with three rows.
- `understanding-benchmark-suite`: PASS, active=7, pending=0, failed=0, known_gap=0.
- `release-readiness` on `tmp/p54/handoff_run`: `evidence_ready`, blockers=0, warnings=0.
- Full `.venv/bin/python -m pytest -q`: 410 passed, 5 warnings.
