"""Feedback loop: read reviewer-edited report.md, persist verdicts, optionally
promote confirmed cases into rule_cards.yaml as regression test cases.

A "run directory" is whatever folder `archkg review` wrote into — it must
contain `issues.json`, `entity_graph.json`, and `report.md`.

Output: `<run_dir>/feedback.yaml` containing one entry per issue with the
reviewer's `status` (open/confirmed/rejected) and `note`.

`apply_to_rules=True` additionally appends one RuleCardTestCase per
*confirmed* (and not-already-known) issue into the project's rule_cards.yaml.
This mutates the packaged YAML and should be done deliberately.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from archkg.knowledge.loader import load_rules, load_standards


class FeedbackError(RuntimeError):
    pass


# Header row contains all of these; data rows start with a backtick-wrapped issue_id.
EXPECTED_COLUMNS = [
    "issue_id",
    "rule_card_id",
    "条文",
    "实体",
    "测量值",
    "阈值",
    "单位",
    "信息",
    "reviewer",
    "status",
    "note",
]
VALID_STATUSES = {"open", "confirmed", "rejected"}


def _strip(cell: str) -> str:
    return cell.strip().strip("`").strip()


def _parse_table(md_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header_idx: list[str] | None = None
    for line in md_text.splitlines():
        if not line.startswith("|"):
            header_idx = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header_idx is None:
            if all(col in cells for col in ("issue_id", "rule_card_id", "status")):
                header_idx = cells
            continue
        # skip the separator line "---|---|..."
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        if len(cells) != len(header_idx):
            continue
        rows.append({header_idx[i]: _strip(cells[i]) for i in range(len(cells))})
    return rows


def _load_issues(run_dir: Path) -> dict[str, dict[str, Any]]:
    issues_json = run_dir / "issues.json"
    if not issues_json.exists():
        raise FeedbackError(f"missing {issues_json}")
    raw = json.loads(issues_json.read_text(encoding="utf-8"))
    return {item["issue_id"]: item for item in raw}


def _load_graph(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Return a flat {entity_id: entity_dict} for all rooms/doors/corridors."""
    g_path = run_dir / "entity_graph.json"
    if not g_path.exists():
        raise FeedbackError(f"missing {g_path}")
    g = json.loads(g_path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for kind in ("rooms", "doors", "corridors"):
        for ent in g.get(kind, []):
            out[ent["id"]] = ent
    return out


def _load_project_meta(run_dir: Path) -> dict[str, Any] | None:
    """Read the project_meta dump that `archkg review --project-meta` saved.

    Returns None when the run was made without a project meta — in that case
    project-scope confirmed cases cannot be promoted (they lack context) and
    we silently skip them.
    """
    meta_path = run_dir / "project_meta.yaml"
    if not meta_path.exists():
        return None
    raw = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def record(
    run_dir: Path,
    *,
    rules_path: Path | None = None,
    apply_to_rules: bool = False,
) -> Path:
    """Read report.md feedback rows, write feedback.yaml; optionally promote
    confirmed rows into rule_cards.yaml as new test_cases."""
    if not run_dir.is_dir():
        raise FeedbackError(f"not a directory: {run_dir}")
    report = run_dir / "report.md"
    if not report.exists():
        raise FeedbackError(f"missing {report}")

    rows = _parse_table(report.read_text(encoding="utf-8"))
    if not rows:
        raise FeedbackError("no feedback rows found in report.md")

    issues = _load_issues(run_dir)
    graph = _load_graph(run_dir)
    meta = _load_project_meta(run_dir)

    items: list[dict[str, Any]] = []
    confirmed_for_rules: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        issue_id = row.get("issue_id", "")
        status = row.get("status", "open").lower() or "open"
        if status not in VALID_STATUSES:
            raise FeedbackError(f"row {issue_id}: invalid status '{status}'")
        issue = issues.get(issue_id)
        if issue is None:
            raise FeedbackError(f"row references unknown issue_id '{issue_id}'")
        items.append(
            {
                "issue_id": issue_id,
                "rule_card_id": issue["rule_card_id"],
                "standard_clause_id": issue["standard_clause_id"],
                "entity_ids": issue["entity_ids"],
                "measured_value": issue["evidence"].get("measured_value"),
                "threshold_value": issue["evidence"].get("threshold_value"),
                "reviewer": row.get("reviewer", "") or None,
                "status": status,
                "note": row.get("note", "") or None,
            }
        )
        if status == "confirmed":
            tc = _build_test_case(issue, graph, meta)
            if tc is not None:
                confirmed_for_rules.setdefault(issue["rule_card_id"], []).append(tc)

    payload = {
        "run_id": run_dir.name,
        "recorded_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "items": items,
    }
    out_path = run_dir / "feedback.yaml"
    out_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    if apply_to_rules and confirmed_for_rules:
        _append_test_cases(rules_path, confirmed_for_rules)

    return out_path


def _build_test_case(
    issue: dict[str, Any],
    graph: dict[str, dict[str, Any]],
    meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build a regression test case from a confirmed issue.

    For entity-level rules the env comes from `entity_graph.json`. For
    project-level rules (entity_ids like 'project:<id>') the env is
    reconstructed from the persisted ProjectMeta dump; without that
    dump the case is dropped silently rather than poisoning the rule
    card with an all-None entity.
    """
    eid = (issue.get("entity_ids") or [None])[0]
    if eid is None:
        return None
    standards = load_standards()
    rules = load_rules(standards=standards)
    rule = next((r for r in rules if r.id == issue["rule_card_id"]), None)
    if rule is None:
        return None

    if isinstance(eid, str) and eid.startswith("project:"):
        if meta is None:
            return None  # missing context → don't promote bogus all-None inputs
        inputs = {k: meta.get(k) for k in rule.inputs}
    else:
        entity = graph.get(eid, {})
        inputs = {k: entity.get(k) for k in rule.inputs}

    return {
        "name": f"confirmed-{issue['issue_id']}",
        "entity": inputs,
        "expect_pass": False,  # confirmed = the rule SHOULD have flagged this
        "note": "auto-promoted from feedback",
    }


def _append_test_cases(
    rules_path: Path | None, confirmed: dict[str, list[dict[str, Any]]]
) -> None:
    target = rules_path or _packaged_rules_path()
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise FeedbackError(f"{target} not a YAML list")
    by_id = {entry["id"]: entry for entry in raw}
    for rule_id, tcs in confirmed.items():
        entry = by_id.get(rule_id)
        if entry is None:
            continue
        existing = entry.setdefault("test_cases", [])
        existing_names = {tc.get("name") for tc in existing}
        for tc in tcs:
            if tc["name"] in existing_names:
                continue
            existing.append(tc)
    target.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _packaged_rules_path() -> Path:
    from importlib.resources import files

    return Path(str(files("archkg.knowledge.data").joinpath("rule_cards.yaml")))
