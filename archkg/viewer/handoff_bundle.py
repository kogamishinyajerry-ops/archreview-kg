from __future__ import annotations

import html
import json
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archkg.viewer.handoff_package import (
    ARCHIVE_MANIFEST_SCHEMA_VERSION,
    ARCHIVE_VERIFICATION_SCHEMA_VERSION,
    MANAGER_CHECKLIST_SCHEMA_VERSION,
    OPENING_PROVENANCE_BOUNDARY_WARNING,
    QUALITY_SCHEMA_VERSION,
    SIGNOFF_SCHEMA_VERSION,
)
from archkg.viewer.handoff_package import (
    SCHEMA_VERSION as PACKAGE_SCHEMA_VERSION,
)
from archkg.viewer.reviewer_task_checklist import (
    SCHEMA_VERSION as REVIEWER_TASK_CHECKLIST_SCHEMA_VERSION,
)

SCHEMA_VERSION = "handoff_bundle_index.v1"
MUTATION_POLICY = "bundle_index_only_no_package_mutation"
BOUNDARY_WARNING = (
    "Handoff bundle index summarizes package-local handoff state only; it is "
    "not a drawing-compliance certificate and does not mutate package artifacts "
    "or source run artifacts."
)


def build_handoff_bundle_index(packages_root: Path) -> dict[str, Any]:
    packages_root = packages_root.resolve()
    if not packages_root.exists() or not packages_root.is_dir():
        raise FileNotFoundError(f"handoff packages root not found: {packages_root}")
    if (packages_root / "handoff_manifest.json").exists():
        raise ValueError(
            "handoff bundle root must contain package directories; it must not be "
            "a single handoff package directory"
        )

    packages = [
        _package_summary(package_dir, packages_root)
        for package_dir in _discover_package_dirs(packages_root)
    ]
    summary = _bundle_summary(packages)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "packages_root": str(packages_root),
        "mutation_policy": MUTATION_POLICY,
        "status": _bundle_status(summary),
        "summary": summary,
        "packages": packages,
        "boundary_warning": BOUNDARY_WARNING,
        "next_action_queue": _bundle_next_action_queue(packages),
        "next_actions": _bundle_next_actions(packages),
    }


def write_handoff_bundle_index(
    packages_root: Path,
    *,
    out: Path | None = None,
    markdown: Path | None = None,
    html_path: Path | None = None,
) -> Path:
    packages_root = packages_root.resolve()
    payload = build_handoff_bundle_index(packages_root)
    json_path = out if out is not None else packages_root / "handoff_bundle_index.json"
    markdown_path = (
        markdown if markdown is not None else packages_root / "handoff_bundle_index.md"
    )
    html_out = (
        html_path
        if html_path is not None
        else packages_root / "handoff_bundle_index.html"
    )

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    html_out.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_handoff_bundle_index_markdown(payload),
        encoding="utf-8",
    )
    html_out.write_text(render_handoff_bundle_index_html(payload), encoding="utf-8")
    return json_path


def render_handoff_bundle_index_markdown(payload: dict[str, Any]) -> str:
    summary = _dict(payload.get("summary"))
    opening_weak_count = _int(summary.get("opening_provenance_weak_package_count"))
    lines = [
        "# ArchReview-KG Handoff Bundle Index",
        "",
        f"Status: `{_str(payload.get('status'))}`",
        f"Packages root: `{_str(payload.get('packages_root'))}`",
        f"Mutation policy: `{_str(payload.get('mutation_policy'))}`",
        "",
        _str(payload.get("boundary_warning")),
        "",
        "## Summary",
        "",
        f"- Packages: `{_int(summary.get('package_count'))}`",
        f"- Ready: `{_int(summary.get('ready_count'))}`",
        f"- Needs info: `{_int(summary.get('needs_info_count'))}`",
        f"- Blocked: `{_int(summary.get('blocked_count'))}`",
        f"- Missing required artifacts: `{_int(summary.get('missing_required_total'))}`",
        f"- Checklist open items: `{_int(summary.get('checklist_open_item_total'))}`",
        f"- Packages with open checklist: `{_int(summary.get('checklist_open_package_count'))}`",
        f"- Packages missing checklist: `{_int(summary.get('checklist_missing_count'))}`",
        f"- Reviewer next: `{_int(summary.get('next_actor_reviewer_count'))}`",
        f"- Manager next: `{_int(summary.get('next_actor_manager_count'))}`",
        f"- Archive next: `{_int(summary.get('next_actor_archive_count'))}`",
        f"- Opening provenance: semantic=`{_int(summary.get('opening_provenance_semantic_count'))}`, "
        f"measurement=`{_int(summary.get('opening_provenance_measurement_count'))}`, "
        f"host_wall=`{_int(summary.get('opening_provenance_host_count'))}`, "
        f"all_three=`{_int(summary.get('opening_provenance_all_three_count'))}`",
        f"- Weak opening provenance packages: `{opening_weak_count}`",
        "",
        "## Packages",
        "",
        "| Package | Status | Next Actor | Next Action | Quality | Signoff | Manager | Archive | Checklist | Missing | Open Items | Opening Provenance | Weak Coverage |",
        "|---|---|---|---|---|---|---|---|---|---:|---|---|---|",
    ]
    for row in _list_of_dicts(payload.get("packages")):
        open_items = "<br>".join(_str_list(row.get("open_items"))) or "-"
        opening_coverage = _opening_provenance_summary_text(row)
        opening_weak = _opening_coverage_weak(row)
        checklist_cell = (
            f"{_str(row.get('checklist_review_status'))} "
            f"({_int(row.get('checklist_open_item_count'))}/"
            f"{_int(row.get('checklist_item_count'))} open)"
        )
        lines.append(
            "| "
            f"`{_str(row.get('package_name'))}` | "
            f"{_str(row.get('package_status'))} | "
            f"{_str(row.get('next_actor'))} | "
            f"{_str(row.get('next_action_title'))} | "
            f"{_str(row.get('quality_status'))} | "
            f"{_str(row.get('signoff_status'))} | "
            f"{_str(row.get('manager_status'))} | "
            f"{_str(row.get('archive_verification_status'))} | "
            f"{checklist_cell} | "
            f"{_int(row.get('missing_required_count'))} | "
            f"{open_items} | "
            f"{opening_coverage} | "
            f"{_str(opening_weak)} |"
        )
    next_actions = _str_list(payload.get("next_actions"))
    if next_actions:
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {item}" for item in next_actions)
    lines.append("")
    return "\n".join(lines)


def render_handoff_bundle_index_html(payload: dict[str, Any]) -> str:
    summary = _dict(payload.get("summary"))
    packages = _list_of_dicts(payload.get("packages"))
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1" />',
        "<title>ArchReview-KG Handoff Bundle</title>",
        "<style>",
        "body{margin:0;background:#f7f8fb;color:#18202f;font:14px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}",
        ".page{max-width:1180px;margin:0 auto;padding:24px}",
        "header{border-bottom:1px solid #d8deea;padding-bottom:18px;margin-bottom:18px}",
        "h1{font-size:26px;margin:0 0 8px}",
        "h2{font-size:16px;margin:0 0 12px}",
        ".muted{color:#5d6b82}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}",
        ".panel{border:1px solid #d8deea;background:#fff;border-radius:8px;padding:14px;margin:12px 0}",
        ".kpi{border:1px solid #d8deea;background:#fff;border-radius:8px;padding:12px}",
        ".kpi b{display:block;font-size:20px;margin-top:4px}",
        ".ok{color:#087443}.warn{color:#995a00}.bad{color:#a82424}",
        "table{width:100%;border-collapse:collapse;background:#fff}",
        "th,td{border-bottom:1px solid #e5e9f2;text-align:left;padding:8px;vertical-align:top}",
        "th{font-size:12px;color:#5d6b82;background:#f1f4f9}",
        "a{color:#174ea6;text-decoration:none}a:hover{text-decoration:underline}",
        ".pill{display:inline-block;border:1px solid #c8d1e2;border-radius:999px;padding:3px 8px;background:#f6f8fc;font-size:12px}",
        "ul{margin:8px 0 0;padding-left:18px}",
        "@media(max-width:820px){.page{padding:14px}table{font-size:12px}}",
        "</style>",
        "</head>",
        "<body>",
        '<main class="page">',
        "<header>",
        "<h1>ArchReview-KG Handoff Bundle</h1>",
        '<div class="muted">Compact read-only index across handoff packages.</div>',
        "</header>",
        '<section class="grid">',
        _kpi("Status", _str(payload.get("status")), _status_class(_str(payload.get("status")))),
        _kpi("Packages", str(_int(summary.get("package_count")))),
        _kpi("Ready", str(_int(summary.get("ready_count"))), "ok"),
        _kpi("Needs Info", str(_int(summary.get("needs_info_count"))), "warn"),
        _kpi("Blocked", str(_int(summary.get("blocked_count"))), "bad"),
        _kpi("Missing Required", str(_int(summary.get("missing_required_total"))), "bad"),
        _kpi("Reviewer Next", str(_int(summary.get("next_actor_reviewer_count"))), "warn"),
        _kpi("Manager Next", str(_int(summary.get("next_actor_manager_count"))), "warn"),
        _kpi("Archive Next", str(_int(summary.get("next_actor_archive_count"))), "warn"),
        _kpi(
            "Checklist Open",
            str(_int(summary.get("checklist_open_item_total"))),
            "warn" if _int(summary.get("checklist_open_item_total")) else "ok",
        ),
        _kpi(
            "Opening Weak Coverage",
            str(_int(summary.get("opening_provenance_weak_package_count"))),
            "warn" if _int(summary.get("opening_provenance_weak_package_count")) else "ok",
        ),
        "</section>",
        '<section class="panel">',
        "<h2>Bundle Boundary</h2>",
        f"<p><b>Mutation policy:</b> {_html(_str(payload.get('mutation_policy')))}</p>",
        f"<p>{_html(_str(payload.get('boundary_warning')))}</p>",
        "</section>",
        '<section class="panel">',
        "<h2>Opening Provenance Coverage</h2>",
        "<p>"
        f"Semantic={_int(summary.get('opening_provenance_semantic_count'))}, "
        f"Measurement={_int(summary.get('opening_provenance_measurement_count'))}, "
        f"Host wall={_int(summary.get('opening_provenance_host_count'))}, "
        f"All-three={_int(summary.get('opening_provenance_all_three_count'))}"
        "</p>",
        "<p>"
        f"Weak opening provenance packages: {_int(summary.get('opening_provenance_weak_package_count'))}. "
        f"{_html(OPENING_PROVENANCE_BOUNDARY_WARNING)}"
        "</p>",
        "</section>",
        '<section class="panel">',
        "<h2>Packages</h2>",
        "<table>",
        "<thead><tr><th>Package</th><th>Status</th><th>Next Actor</th><th>Next Action</th><th>Quality</th><th>Signoff</th><th>Manager</th><th>Archive Check</th><th>Checklist</th><th>Open Items</th><th>Opening Provenance</th><th>Weak Coverage</th></tr></thead>",
        "<tbody>",
    ]
    for row in packages:
        package_name = _str(row.get("package_name"))
        index_path = _str(row.get("index_path"))
        opening_coverage = _opening_provenance_summary_text(row)
        opening_weak = _opening_coverage_weak(row)
        label = (
            f'<a href="{_html_attr(index_path)}">{_html(package_name)}</a>'
            if index_path
            else _html(package_name)
        )
        open_items = _str_list(row.get("open_items"))
        lines.append(
            "<tr>"
            f"<td>{label}</td>"
            f"<td><span class=\"pill\">{_html(_str(row.get('package_status')))}</span></td>"
            f"<td>{_html(_str(row.get('next_actor')))}</td>"
            f"<td>{_html(_str(row.get('next_action_title')))}</td>"
            f"<td>{_html(_str(row.get('quality_status')))}</td>"
            f"<td>{_html(_str(row.get('signoff_status')))}</td>"
            f"<td>{_html(_str(row.get('manager_status')))}</td>"
            f"<td>{_html(_str(row.get('archive_verification_status')))}</td>"
            f"<td>{_html(_str(row.get('checklist_review_status')))} "
            f"({_int(row.get('checklist_open_item_count'))}/"
            f"{_int(row.get('checklist_item_count'))} open)</td>"
            f"<td>{_html('; '.join(open_items) if open_items else '-')}</td>"
            f"<td>{_html(opening_coverage)}</td>"
            f"<td>{_html(opening_weak)}</td>"
            "</tr>"
        )
    lines.extend(["</tbody>", "</table>", "</section>"])
    next_actions = _str_list(payload.get("next_actions"))
    if next_actions:
        lines.extend(['<section class="panel">', "<h2>Next Actions</h2>", "<ul>"])
        lines.extend(f"<li>{_html(item)}</li>" for item in next_actions)
        lines.extend(["</ul>", "</section>"])
    lines.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(lines)


def _discover_package_dirs(packages_root: Path) -> list[Path]:
    return [
        child
        for child in sorted(packages_root.iterdir())
        if child.is_dir() and (child / "handoff_manifest.json").is_file()
    ]


def _package_summary(package_dir: Path, packages_root: Path) -> dict[str, Any]:
    manifest = _load_json(package_dir / "handoff_manifest.json")
    quality = _load_json(package_dir / "handoff_quality.json")
    signoff = _load_json(package_dir / "reviewer_signoff.json")
    manager = _load_json(package_dir / "handoff_manager_checklist.json")
    archive_manifest = _load_json(package_dir / "handoff_archive_manifest.json")
    archive_verification = _load_json(package_dir / "handoff_archive_verification.json")
    opening_provenance = _opening_provenance_summary(manifest)
    checklist_payload = _load_json(
        package_dir / "artifacts" / "reviewer_task_checklist.json"
    )
    checklist = _checklist_summary(checklist_payload)
    artifact_rows = _list_of_dicts(manifest.get("artifact_statuses"))
    available_count = sum(1 for row in artifact_rows if row.get("status") == "available")
    missing_required = _str_list(manifest.get("missing_required_artifacts"))
    package_status = _package_status(
        manifest=manifest,
        quality=quality,
        signoff=signoff,
        manager=manager,
        archive_verification=archive_verification,
    )
    open_items = _package_open_items(
        manifest=manifest,
        quality=quality,
        signoff=signoff,
        manager=manager,
        archive_manifest=archive_manifest,
        archive_verification=archive_verification,
    )
    next_action = _package_next_action(
        package_dir=package_dir,
        manifest=manifest,
        quality=quality,
        signoff=signoff,
        manager=manager,
        archive_manifest=archive_manifest,
        archive_verification=archive_verification,
        checklist=checklist,
        checklist_payload=checklist_payload,
    )
    relative_dir = package_dir.relative_to(packages_root).as_posix()
    index_rel = f"{relative_dir}/index.html" if (package_dir / "index.html").is_file() else ""
    return {
        "package_name": package_dir.name,
        "package_dir": str(package_dir),
        "relative_package_dir": relative_dir,
        "index_path": index_rel,
        "source_run_dir": _str(manifest.get("source_run_dir")),
        "created_at": _str(manifest.get("created_at")),
        "manifest_schema": _str(manifest.get("schema_version")) or "missing",
        "package_status": package_status,
        "next_actor": _str(next_action.get("actor")),
        "next_action_id": _str(next_action.get("id")),
        "next_action_title": _str(next_action.get("title")),
        "next_action_reason": _str(next_action.get("reason")),
        "next_action_command": _str(next_action.get("command")),
        "quality_status": _payload_status(
            quality,
            expected_schema=QUALITY_SCHEMA_VERSION,
            missing="not_run",
        ),
        "quality_blocker_count": len(_str_list(quality.get("blockers"))),
        "quality_warning_count": len(_str_list(quality.get("warnings"))),
        "signoff_status": _payload_status(
            signoff,
            expected_schema=SIGNOFF_SCHEMA_VERSION,
            missing="not_recorded",
        ),
        "reviewer": _str(signoff.get("reviewer")),
        "manager_status": _payload_status(
            manager,
            expected_schema=MANAGER_CHECKLIST_SCHEMA_VERSION,
            missing="not_recorded",
        ),
        "manager": _str(manager.get("manager")),
        "archive_status": _payload_status(
            archive_manifest,
            expected_schema=ARCHIVE_MANIFEST_SCHEMA_VERSION,
            missing="not_recorded",
        ),
        "archive_verification_status": _payload_status(
            archive_verification,
            expected_schema=ARCHIVE_VERIFICATION_SCHEMA_VERSION,
            missing="not_recorded",
        ),
        "package_digest": _str(archive_manifest.get("package_digest")),
        "checklist_available": checklist["available"],
        "checklist_status": checklist["status"],
        "checklist_review_status": checklist["review_status"],
        "checklist_item_count": checklist["item_count"],
        "checklist_done_item_count": checklist["done_item_count"],
        "checklist_open_item_count": checklist["open_item_count"],
        "checklist_blocked_item_count": checklist["blocked_item_count"],
        "checklist_needs_info_item_count": checklist["needs_info_item_count"],
        "checklist_readiness_item_count": checklist["readiness_item_count"],
        "checklist_primary_issue_item_count": checklist["primary_issue_item_count"],
        "checklist_preview_item_count": checklist["preview_item_count"],
        "checklist_handoff_item_count": checklist["handoff_item_count"],
        "checklist_open_samples": checklist["open_samples"],
        "artifact_available_count": available_count,
        "artifact_total_count": len(artifact_rows),
        "missing_required_count": len(missing_required),
        "missing_required_artifacts": missing_required,
        "opening_provenance_available": opening_provenance["available"],
        "opening_provenance_source_artifact": opening_provenance["source_artifact"],
        "opening_provenance_semantic_count": opening_provenance["semantic_count"],
        "opening_provenance_measurement_count": opening_provenance["measurement_count"],
        "opening_provenance_host_count": opening_provenance["host_count"],
        "opening_provenance_all_three_count": opening_provenance["all_three_count"],
        "opening_provenance_boundary_warning": opening_provenance["boundary_warning"],
        "opening_provenance_weak": (
            opening_provenance["available"] is False
            or opening_provenance["semantic_count"] == 0
            or opening_provenance["measurement_count"] == 0
            or opening_provenance["host_count"] == 0
        ),
        "open_items": open_items,
    }


def _opening_provenance_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    raw = manifest.get("opening_provenance")
    if not isinstance(raw, dict):
        return {
            "available": False,
            "source_artifact": "",
            "semantic_count": 0,
            "measurement_count": 0,
            "host_count": 0,
            "all_three_count": 0,
            "boundary_warning": OPENING_PROVENANCE_BOUNDARY_WARNING,
        }
    return {
        "available": raw.get("available") is True,
        "source_artifact": _str(raw.get("source_artifact")),
        "semantic_count": _int(raw.get("semantic_count")),
        "measurement_count": _int(raw.get("measurement_count")),
        "host_count": _int(raw.get("host_count")),
        "all_three_count": _int(raw.get("all_three_count")),
        "boundary_warning": _str(raw.get("boundary_warning")),
    }


def _opening_provenance_summary_text(row: dict[str, Any]) -> str:
    if not _bool(row.get("opening_provenance_available")):
        return "unavailable"
    return (
        "semantic="
        f"{_int(row.get('opening_provenance_semantic_count'))}, "
        "measurement="
        f"{_int(row.get('opening_provenance_measurement_count'))}, "
        "host_wall="
        f"{_int(row.get('opening_provenance_host_count'))}, "
        "all_three="
        f"{_int(row.get('opening_provenance_all_three_count'))}"
    )


def _opening_coverage_weak(row: dict[str, Any]) -> str:
    return "yes" if _bool(row.get("opening_provenance_weak")) else "-"


def _package_status(
    *,
    manifest: dict[str, Any],
    quality: dict[str, Any],
    signoff: dict[str, Any],
    manager: dict[str, Any],
    archive_verification: dict[str, Any],
) -> str:
    manifest_schema = _str(manifest.get("schema_version"))
    if manifest_schema != PACKAGE_SCHEMA_VERSION:
        return "package_blocked"
    if _str_list(manifest.get("missing_required_artifacts")):
        return "package_blocked"
    blocking_statuses = {
        _payload_status(quality, expected_schema=QUALITY_SCHEMA_VERSION, missing="not_run"),
        _payload_status(signoff, expected_schema=SIGNOFF_SCHEMA_VERSION, missing="not_recorded"),
        _payload_status(
            manager,
            expected_schema=MANAGER_CHECKLIST_SCHEMA_VERSION,
            missing="not_recorded",
        ),
        _payload_status(
            archive_verification,
            expected_schema=ARCHIVE_VERIFICATION_SCHEMA_VERSION,
            missing="not_recorded",
        ),
    }
    if blocking_statuses.intersection(
        {"not_ready", "blocked", "manager_blocked", "archive_drift", "invalid"}
    ):
        return "package_blocked"
    if blocking_statuses.intersection(
        {
            "handoff_ready_with_warnings",
            "needs_info",
            "manager_needs_info",
            "not_run",
            "not_recorded",
        }
    ):
        return "package_needs_info"
    return "package_ready"


def _package_open_items(
    *,
    manifest: dict[str, Any],
    quality: dict[str, Any],
    signoff: dict[str, Any],
    manager: dict[str, Any],
    archive_manifest: dict[str, Any],
    archive_verification: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        items.append("handoff_manifest.json missing or invalid")
    items.extend(
        f"missing required artifact: {name}"
        for name in _str_list(manifest.get("missing_required_artifacts"))
    )
    quality_status = _payload_status(
        quality,
        expected_schema=QUALITY_SCHEMA_VERSION,
        missing="not_run",
    )
    if quality_status == "not_run":
        items.append("run handoff-check")
    elif quality_status != "handoff_ready":
        items.extend(_str_list(quality.get("blockers")) or [f"quality {quality_status}"])
    signoff_status = _payload_status(
        signoff,
        expected_schema=SIGNOFF_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if signoff_status == "not_recorded":
        items.append("record reviewer signoff")
    elif signoff_status != "ready":
        items.extend(_str_list(signoff.get("blockers")) or [f"reviewer signoff {signoff_status}"])
    manager_status = _payload_status(
        manager,
        expected_schema=MANAGER_CHECKLIST_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if manager_status == "not_recorded":
        items.append("record manager checklist")
    elif manager_status != "manager_ready":
        items.extend(_str_list(manager.get("open_items")) or [f"manager checklist {manager_status}"])
    archive_status = _payload_status(
        archive_manifest,
        expected_schema=ARCHIVE_MANIFEST_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if archive_status == "not_recorded":
        items.append("write archive manifest before transfer")
    archive_verification_status = _payload_status(
        archive_verification,
        expected_schema=ARCHIVE_VERIFICATION_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if archive_verification_status == "not_recorded":
        items.append("verify archive after transfer")
    elif archive_verification_status != "archive_verified":
        items.extend(
            _str_list(archive_verification.get("blockers"))
            or [f"archive verification {archive_verification_status}"]
        )
    return _dedupe(items)


def _package_next_action(
    *,
    package_dir: Path,
    manifest: dict[str, Any],
    quality: dict[str, Any],
    signoff: dict[str, Any],
    manager: dict[str, Any],
    archive_manifest: dict[str, Any],
    archive_verification: dict[str, Any],
    checklist: dict[str, Any],
    checklist_payload: dict[str, Any],
) -> dict[str, str]:
    package_arg = _shell_path(package_dir)
    if manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        return _next_action(
            "reviewer",
            "restore_manifest",
            "Restore handoff manifest.",
            "handoff_manifest.json is missing or invalid.",
            "",
        )
    missing_required = _str_list(manifest.get("missing_required_artifacts"))
    if missing_required:
        return _next_action(
            "reviewer",
            "restore_required_artifacts",
            "Restore missing required artifacts.",
            f"Missing required artifact: {missing_required[0]}.",
            "",
        )

    quality_status = _payload_status(
        quality,
        expected_schema=QUALITY_SCHEMA_VERSION,
        missing="not_run",
    )
    if quality_status != "handoff_ready":
        return _next_action(
            "reviewer",
            "run_handoff_quality",
            "Run handoff package quality gate.",
            f"Current handoff quality status is {quality_status}.",
            (
                f"archkg handoff-check {package_arg} "
                f"--out {package_arg}/handoff_quality.json "
                f"--markdown {package_arg}/handoff_quality.md"
            ),
        )

    signoff_status = _payload_status(
        signoff,
        expected_schema=SIGNOFF_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if signoff_status != "ready":
        return _next_action(
            "reviewer",
            "record_reviewer_signoff",
            "Record reviewer signoff.",
            f"Current reviewer signoff status is {signoff_status}.",
            (
                f"archkg handoff-signoff {package_arg} --reviewer <reviewer> "
                '--status ready --note "<handoff note>"'
            ),
        )

    checklist_review_status = _str(checklist.get("review_status"))
    if checklist_review_status != "checklist_complete":
        return _next_checklist_action(package_dir, checklist, checklist_payload)

    manager_status = _payload_status(
        manager,
        expected_schema=MANAGER_CHECKLIST_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if manager_status != "manager_ready":
        return _next_action(
            "manager",
            "run_manager_checklist",
            "Run manager checklist for intake.",
            f"Current manager checklist status is {manager_status}.",
            (
                f"archkg handoff-manager-checklist {package_arg} "
                '--manager <manager> --note "<manager intake note>"'
            ),
        )

    archive_status = _payload_status(
        archive_manifest,
        expected_schema=ARCHIVE_MANIFEST_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if archive_status != "archive_manifest_ready":
        return _next_action(
            "archive",
            "write_archive_manifest",
            "Write archive manifest before transfer.",
            f"Current archive manifest status is {archive_status}.",
            (
                f"archkg handoff-archive-manifest {package_arg} "
                '--created-by <name> --note "<transfer note>"'
            ),
        )

    archive_verification_status = _payload_status(
        archive_verification,
        expected_schema=ARCHIVE_VERIFICATION_SCHEMA_VERSION,
        missing="not_recorded",
    )
    if archive_verification_status != "archive_verified":
        return _next_action(
            "archive",
            "verify_archive",
            "Verify archive after transfer.",
            f"Current archive verification status is {archive_verification_status}.",
            f"archkg handoff-archive-verify {package_arg}",
        )

    return _next_action(
        "done",
        "ready",
        "No action required.",
        "Package is ready.",
        "",
    )


def _next_checklist_action(
    package_dir: Path,
    checklist: dict[str, Any],
    checklist_payload: dict[str, Any],
) -> dict[str, str]:
    package_arg = _shell_path(package_dir)
    if not checklist.get("available"):
        return _next_action(
            "reviewer",
            "restore_reviewer_task_checklist",
            "Restore reviewer task checklist artifact.",
            f"Reviewer checklist status is {_str(checklist.get('review_status'))}.",
            "",
        )
    for item in _list_of_dicts(checklist_payload.get("items")):
        reviewer_status = _str(item.get("reviewer_status"))
        if reviewer_status in {"done", "skipped_preview"}:
            continue
        ordinal = _int(item.get("ordinal"))
        check_id = _str(item.get("check_id"))
        selector = (
            f"--ordinal {ordinal}"
            if ordinal
            else f"--check-id {shlex.quote(check_id)}"
        )
        evidence = _str_list(item.get("required_evidence"))
        evidence_flags = "".join(
            f" --evidence-checked {shlex.quote(value)}" for value in evidence
        )
        return _next_action(
            "reviewer",
            f"close_checklist_{ordinal or check_id}",
            _str(item.get("title")) or "Close reviewer checklist item.",
            f"Checklist item is currently {reviewer_status or 'todo'}.",
            (
                f"archkg handoff-checklist-update {package_arg} {selector} "
                f"--reviewer <reviewer> --status done "
                f'--note "<evidence reviewed>"{evidence_flags}'
            ),
        )
    return _next_action(
        "reviewer",
        "review_reviewer_task_checklist",
        "Review reviewer task checklist.",
        f"Reviewer checklist status is {_str(checklist.get('review_status'))}.",
        "",
    )


def _next_action(
    actor: str,
    action_id: str,
    title: str,
    reason: str,
    command: str,
) -> dict[str, str]:
    return {
        "actor": actor,
        "id": action_id,
        "title": title,
        "reason": reason,
        "command": command,
    }


def _payload_status(
    payload: dict[str, Any],
    *,
    expected_schema: str,
    missing: str,
) -> str:
    if not payload:
        return missing
    if _str(payload.get("schema_version")) != expected_schema:
        return "invalid"
    return _str(payload.get("status")) or missing


def _bundle_summary(packages: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [_str(row.get("package_status")) for row in packages]
    return {
        "package_count": len(packages),
        "ready_count": statuses.count("package_ready"),
        "needs_info_count": statuses.count("package_needs_info"),
        "blocked_count": statuses.count("package_blocked"),
        "missing_required_total": sum(
            _int(row.get("missing_required_count")) for row in packages
        ),
        "quality_not_run_count": sum(
            1 for row in packages if row.get("quality_status") == "not_run"
        ),
        "signoff_not_recorded_count": sum(
            1 for row in packages if row.get("signoff_status") == "not_recorded"
        ),
        "checklist_open_package_count": sum(
            1 for row in packages if _int(row.get("checklist_open_item_count")) > 0
        ),
        "checklist_open_item_total": sum(
            _int(row.get("checklist_open_item_count")) for row in packages
        ),
        "checklist_blocked_item_total": sum(
            _int(row.get("checklist_blocked_item_count")) for row in packages
        ),
        "checklist_needs_info_item_total": sum(
            _int(row.get("checklist_needs_info_item_count")) for row in packages
        ),
        "checklist_missing_count": sum(
            1 for row in packages if row.get("checklist_review_status") == "checklist_missing"
        ),
        "next_actor_reviewer_count": _next_actor_count(packages, "reviewer"),
        "next_actor_manager_count": _next_actor_count(packages, "manager"),
        "next_actor_archive_count": _next_actor_count(packages, "archive"),
        "next_actor_done_count": _next_actor_count(packages, "done"),
        "opening_provenance_weak_package_count": sum(
            1 for row in packages if _bool(row.get("opening_provenance_weak"))
        ),
        "opening_provenance_semantic_count": sum(
            _int(row.get("opening_provenance_semantic_count")) for row in packages
        ),
        "opening_provenance_measurement_count": sum(
            _int(row.get("opening_provenance_measurement_count")) for row in packages
        ),
        "opening_provenance_host_count": sum(
            _int(row.get("opening_provenance_host_count")) for row in packages
        ),
        "opening_provenance_all_three_count": sum(
            _int(row.get("opening_provenance_all_three_count")) for row in packages
        ),
    }


def _bundle_status(summary: dict[str, int]) -> str:
    if summary["package_count"] == 0:
        return "bundle_empty"
    if summary["blocked_count"]:
        return "bundle_blocked"
    if summary["needs_info_count"]:
        return "bundle_needs_info"
    return "bundle_ready"


def _bundle_next_actions(packages: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for package in packages:
        actor = _str(package.get("next_actor"))
        if actor == "done":
            continue
        actions.append(
            f"{_str(package.get('package_name'))}: "
            f"{actor} -> {_str(package.get('next_action_title'))}"
        )
    for package in packages:
        if _int(package.get("checklist_open_item_count")) <= 0:
            continue
        actions.append(
            f"{_str(package.get('package_name'))}: complete "
            f"{_int(package.get('checklist_open_item_count'))} reviewer checklist items"
        )
    return actions


def _bundle_next_action_queue(packages: list[dict[str, Any]]) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    for package in packages:
        actor = _str(package.get("next_actor"))
        if actor == "done":
            continue
        queue.append(
            {
                "package_name": _str(package.get("package_name")),
                "relative_package_dir": _str(package.get("relative_package_dir")),
                "actor": actor,
                "action_id": _str(package.get("next_action_id")),
                "title": _str(package.get("next_action_title")),
                "reason": _str(package.get("next_action_reason")),
                "command": _str(package.get("next_action_command")),
            }
        )
    return queue


def _next_actor_count(packages: list[dict[str, Any]], actor: str) -> int:
    return sum(1 for row in packages if row.get("next_actor") == actor)


def _checklist_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return _empty_checklist_summary("checklist_missing", available=False)
    if _str(payload.get("schema_version")) != REVIEWER_TASK_CHECKLIST_SCHEMA_VERSION:
        return _empty_checklist_summary("checklist_invalid", available=False)

    items = _list_of_dicts(payload.get("items"))
    open_items = [
        item
        for item in items
        if _str(item.get("reviewer_status")) not in {"done", "skipped_preview"}
    ]
    blocked_items = [
        item for item in items if _str(item.get("reviewer_status")) == "blocked"
    ]
    needs_info_items = [
        item for item in items if _str(item.get("reviewer_status")) == "needs_info"
    ]
    done_items = [
        item
        for item in items
        if _str(item.get("reviewer_status")) in {"done", "skipped_preview"}
    ]
    return {
        "available": True,
        "status": _str(payload.get("status")) or "unknown",
        "review_status": _checklist_review_status(
            item_count=len(items),
            open_count=len(open_items),
            blocked_count=len(blocked_items),
            needs_info_count=len(needs_info_items),
        ),
        "item_count": len(items),
        "done_item_count": len(done_items),
        "open_item_count": len(open_items),
        "blocked_item_count": len(blocked_items),
        "needs_info_item_count": len(needs_info_items),
        "readiness_item_count": _count_stage(items, "readiness"),
        "primary_issue_item_count": _count_stage(items, "primary_issue_review"),
        "preview_item_count": _count_stage(items, "per_sheet_preview"),
        "handoff_item_count": _count_stage(items, "handoff"),
        "open_samples": [
            _str(item.get("title")) or _str(item.get("check_id"))
            for item in open_items[:3]
        ],
    }


def _empty_checklist_summary(
    review_status: str,
    *,
    available: bool,
) -> dict[str, Any]:
    return {
        "available": available,
        "status": review_status,
        "review_status": review_status,
        "item_count": 0,
        "done_item_count": 0,
        "open_item_count": 0,
        "blocked_item_count": 0,
        "needs_info_item_count": 0,
        "readiness_item_count": 0,
        "primary_issue_item_count": 0,
        "preview_item_count": 0,
        "handoff_item_count": 0,
        "open_samples": [],
    }


def _checklist_review_status(
    *,
    item_count: int,
    open_count: int,
    blocked_count: int,
    needs_info_count: int,
) -> str:
    if item_count == 0:
        return "checklist_empty"
    if blocked_count:
        return "checklist_blocked"
    if needs_info_count:
        return "checklist_needs_info"
    if open_count:
        return "checklist_open"
    return "checklist_complete"


def _count_stage(items: list[dict[str, Any]], stage: str) -> int:
    return sum(1 for item in items if _str(item.get("stage")) == stage)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": "invalid"}
    return raw if isinstance(raw, dict) else {"schema_version": "invalid"}


def _status_class(status: str) -> str:
    if status in {"bundle_ready", "package_ready"}:
        return "ok"
    if status in {"bundle_blocked", "package_blocked", "bundle_empty"}:
        return "bad"
    if status in {"bundle_needs_info", "package_needs_info"}:
        return "warn"
    return ""


def _kpi(label: str, value: str, class_name: str = "") -> str:
    class_attr = f" {class_name}" if class_name else ""
    return (
        f'<div class="kpi{class_attr}">'
        f'<span class="muted">{_html(label)}</span>'
        f"<b>{_html(value)}</b>"
        "</div>"
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        out.append(item)
        seen.add(item)
    return out


def _list_of_dicts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _str_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _dict(raw: object) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _bool(raw: object) -> bool:
    return raw is True


def _html(raw: object) -> str:
    return html.escape(_str(raw), quote=False)


def _html_attr(raw: object) -> str:
    return html.escape(_str(raw), quote=True)


def _shell_path(path: Path) -> str:
    return shlex.quote(str(path))


__all__ = [
    "BOUNDARY_WARNING",
    "MUTATION_POLICY",
    "SCHEMA_VERSION",
    "build_handoff_bundle_index",
    "render_handoff_bundle_index_html",
    "render_handoff_bundle_index_markdown",
    "write_handoff_bundle_index",
]
