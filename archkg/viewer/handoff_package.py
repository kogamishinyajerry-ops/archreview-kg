from __future__ import annotations

import hashlib
import html
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "handoff_package.v1"
QUALITY_SCHEMA_VERSION = "handoff_package_quality.v1"
SIGNOFF_SCHEMA_VERSION = "handoff_reviewer_signoff.v1"
MANAGER_CHECKLIST_SCHEMA_VERSION = "handoff_manager_checklist.v1"
ARCHIVE_MANIFEST_SCHEMA_VERSION = "handoff_archive_manifest.v1"
ARCHIVE_VERIFICATION_SCHEMA_VERSION = "handoff_archive_verification.v1"

MUTATION_POLICY = "copy_artifacts_only_no_source_run_mutation"
ARCHIVE_MANIFEST_MUTATION_POLICY = (
    "package_integrity_manifest_only_no_source_run_mutation"
)
ARCHIVE_VERIFICATION_MUTATION_POLICY = (
    "package_archive_verification_only_no_source_run_mutation"
)
ARCHIVE_MANIFEST_EXCLUDED_PATHS: tuple[str, ...] = (
    "handoff_archive_manifest.json",
    "handoff_archive_manifest.md",
    "index.html",
)
ARCHIVE_VERIFICATION_EXCLUDED_PATHS: tuple[str, ...] = (
    "handoff_archive_verification.json",
    "handoff_archive_verification.md",
)

BOUNDARY_WARNINGS: tuple[str, ...] = (
    "This package is read-only evidence for human handoff; it does not certify compliance.",
    "issues.json rows remain candidate issues until a reviewer updates review_state.json.",
    "sheet_issue_review_queue.json preview_id values are preview ids; "
    "preview ids are not primary issue ids and must not be passed to archkg review-state.",
    "Missing input or low confidence evidence must be listed as unresolved handoff risk.",
    "release_readiness evidence_ready is scoped to benchmarked drawing classes only.",
)


@dataclass(frozen=True)
class HandoffArtifactSpec:
    name: str
    required: bool
    tier: str
    purpose: str


ARTIFACTS: tuple[HandoffArtifactSpec, ...] = (
    HandoffArtifactSpec(
        "reviewer_quickstart.md",
        True,
        "entry",
        "First-hour checklist for a novice reviewer.",
    ),
    HandoffArtifactSpec(
        "report.md",
        True,
        "entry",
        "Human-readable issue and evidence report.",
    ),
    HandoffArtifactSpec(
        "review_workbench.json",
        True,
        "core",
        "Navigation summary across review evidence surfaces.",
    ),
    HandoffArtifactSpec(
        "drawing_understanding.json",
        True,
        "core",
        "Drawing type, component inventory, and recognition evidence.",
    ),
    HandoffArtifactSpec(
        "rule_input_readiness.json",
        True,
        "core",
        "Per-rule ready, missing-input, and low-confidence status.",
    ),
    HandoffArtifactSpec(
        "issues.json",
        True,
        "core",
        "Primary rule-engine candidate issues.",
    ),
    HandoffArtifactSpec(
        "review_state.json",
        True,
        "core",
        "Human review lifecycle state for primary issues.",
    ),
    HandoffArtifactSpec(
        "sheet_issue_review_queue.json",
        True,
        "preview",
        "Bounded per-sheet preview review queue.",
    ),
    HandoffArtifactSpec(
        "review_diff.json",
        False,
        "revision",
        "Read-only comparison against another run.",
    ),
    HandoffArtifactSpec(
        "release_readiness.json",
        False,
        "gate",
        "Machine-readable release or demo readiness gate output.",
    ),
    HandoffArtifactSpec(
        "release_readiness.md",
        False,
        "gate",
        "Human-readable release or demo readiness gate output.",
    ),
    HandoffArtifactSpec(
        "annotated.pdf",
        False,
        "visual",
        "PDF with issue annotations.",
    ),
    HandoffArtifactSpec(
        "source.pdf",
        False,
        "visual",
        "Source PDF copy used by the static viewer.",
    ),
    HandoffArtifactSpec(
        "preview_pages.json",
        False,
        "visual",
        "Available source, annotated, and overlay preview pages.",
    ),
    HandoffArtifactSpec(
        "source_preview.png",
        False,
        "visual",
        "Rendered source preview.",
    ),
    HandoffArtifactSpec(
        "annotated_preview.png",
        False,
        "visual",
        "Rendered annotated preview.",
    ),
    HandoffArtifactSpec(
        "entity_overlay.png",
        False,
        "visual",
        "Entity overlay preview.",
    ),
    HandoffArtifactSpec(
        "index.html",
        False,
        "viewer",
        "Pre-rendered static Viewer page when available.",
    ),
)


def write_handoff_package(run_dir: Path, package_dir: Path) -> Path:
    """Copy review evidence into a standalone read-only handoff package."""

    run_dir = run_dir.resolve()
    package_dir = package_dir.resolve()
    _validate_paths(run_dir, package_dir)

    artifacts_dir = package_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    statuses = [_copy_artifact(run_dir, artifacts_dir, spec) for spec in ARTIFACTS]
    statuses.extend(_copy_preview_page_artifacts(run_dir, artifacts_dir, statuses))
    missing_required = [
        row["artifact"]
        for row in statuses
        if row["required"] is True and row["status"] == "missing"
    ]
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "source_run_dir": str(run_dir),
        "package_dir": str(package_dir),
        "read_only": True,
        "mutation_policy": MUTATION_POLICY,
        "audience": "novice_review_engineer",
        "artifact_statuses": statuses,
        "included_artifacts": [
            row["artifact"] for row in statuses if row["status"] == "available"
        ],
        "missing_required_artifacts": missing_required,
        "boundary_warnings": list(BOUNDARY_WARNINGS),
        "commands": _commands(run_dir),
        "handoff_summary_path": "handoff_summary.md",
        "artifacts_dir": "artifacts",
    }
    manifest_path = package_dir / "handoff_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "handoff_summary.md").write_text(
        render_handoff_summary(manifest),
        encoding="utf-8",
    )
    _write_handoff_index_from_payloads(package_dir, manifest)
    return manifest_path


def render_handoff_summary(manifest: dict[str, Any]) -> str:
    missing = _str_list(manifest.get("missing_required_artifacts"))
    lines = [
        "# ArchReview-KG Handoff Package",
        "",
        f"Source run: `{_str(manifest.get('source_run_dir'))}`",
        f"Package: `{_str(manifest.get('package_dir'))}`",
        f"Mutation policy: `{_str(manifest.get('mutation_policy'))}`",
        "",
        "## Boundary Warnings",
        "",
    ]
    for warning in _str_list(manifest.get("boundary_warnings")):
        lines.append(f"- {warning}")
    lines.extend(["", "## Missing Required Artifacts", ""])
    if missing:
        lines.extend(f"- `{item}`" for item in missing)
    else:
        lines.append("None")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "| Artifact | Required | Status | Tier | Package Path | Purpose |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for row in _artifact_rows(manifest):
        lines.append(
            "| "
            f"`{_str(row.get('artifact'))}` | "
            f"{'yes' if row.get('required') else 'no'} | "
            f"{_str(row.get('status'))} | "
            f"{_str(row.get('tier'))} | "
            f"`{_str(row.get('package_path')) or '-'}` | "
            f"{_str(row.get('purpose'))} |"
        )
    lines.extend(["", "## Next Review Actions", ""])
    lines.append("- Open `artifacts/reviewer_quickstart.md` first.")
    lines.append("- Check `artifacts/rule_input_readiness.json` before trusting issue counts.")
    lines.append("- Use `archkg review-state` only with primary issue ids from `artifacts/issues.json`.")
    lines.append("- Treat `artifacts/sheet_issue_review_queue.json` as preview evidence only.")
    lines.append("")
    return "\n".join(lines)


def build_handoff_package_quality(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    manifest_path = package_dir / "handoff_manifest.json"
    manifest = _load_manifest(manifest_path)
    checks = {
        "manifest_schema": _check_manifest_schema(manifest),
        "read_only_policy": _check_read_only_policy(manifest),
        "required_artifacts_present": _check_required_artifacts_present(manifest),
        "copied_artifacts_exist": _check_copied_artifacts_exist(
            package_dir,
            manifest,
        ),
        "boundary_warnings_present": _check_boundary_warnings_present(manifest),
    }
    blockers = [
        detail
        for check in checks.values()
        if check["severity"] == "blocker" and check["passed"] is False
        for detail in _str_list(check.get("details"))
    ]
    warnings = [
        detail
        for check in checks.values()
        if check["severity"] == "warning" and check["passed"] is False
        for detail in _str_list(check.get("details"))
    ]
    status = "not_ready" if blockers else "handoff_ready_with_warnings" if warnings else "handoff_ready"
    return {
        "schema_version": QUALITY_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "package_dir": str(package_dir),
        "manifest_path": str(manifest_path),
        "status": status,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "note": (
            "Handoff quality validates package completeness and boundaries. "
            "It does not certify drawing compliance."
        ),
    }


def write_handoff_package_quality_json(result: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_handoff_package_quality_markdown(result: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_handoff_package_quality_markdown(result), encoding="utf-8")
    return path


def render_handoff_package_quality_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# ArchReview-KG Handoff Package Quality",
        "",
        f"Status: `{_str(result.get('status'))}`",
        "",
        _str(result.get("note")),
        "",
        "## Checks",
        "",
        "| Check | Severity | Status | Details |",
        "|---|---|---:|---|",
    ]
    checks = result.get("checks")
    if isinstance(checks, dict):
        for check_id, raw in checks.items():
            check = raw if isinstance(raw, dict) else {}
            details = "; ".join(_str_list(check.get("details"))) or "-"
            lines.append(
                "| "
                f"{check_id} | "
                f"{_str(check.get('severity'))} | "
                f"{'PASS' if check.get('passed') else 'FAIL'} | "
                f"{details} |"
            )
    blockers = _str_list(result.get("blockers"))
    warnings = _str_list(result.get("warnings"))
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)
    lines.append("")
    return "\n".join(lines)


def write_handoff_index(
    package_dir: Path,
    *,
    quality: dict[str, Any] | None = None,
    signoff: dict[str, Any] | None = None,
    manager_checklist: dict[str, Any] | None = None,
    archive_manifest: dict[str, Any] | None = None,
    archive_verification: dict[str, Any] | None = None,
) -> Path:
    package_dir = package_dir.resolve()
    manifest = _load_manifest(package_dir / "handoff_manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise FileNotFoundError(f"handoff package manifest not found: {package_dir}")
    return _write_handoff_index_from_payloads(
        package_dir,
        manifest,
        quality=quality,
        signoff=signoff,
        manager_checklist=manager_checklist,
        archive_manifest=archive_manifest,
        archive_verification=archive_verification,
    )


def render_handoff_index_html(
    manifest: dict[str, Any],
    *,
    quality: dict[str, Any] | None = None,
    signoff: dict[str, Any] | None = None,
    manager_checklist: dict[str, Any] | None = None,
    archive_manifest: dict[str, Any] | None = None,
    archive_verification: dict[str, Any] | None = None,
) -> str:
    quality = quality if isinstance(quality, dict) else {}
    signoff = signoff if isinstance(signoff, dict) else {}
    manager_checklist = manager_checklist if isinstance(manager_checklist, dict) else {}
    archive_manifest = archive_manifest if isinstance(archive_manifest, dict) else {}
    archive_verification = (
        archive_verification if isinstance(archive_verification, dict) else {}
    )
    artifact_rows = _artifact_rows(manifest)
    available_count = sum(1 for row in artifact_rows if row.get("status") == "available")
    required_missing = _str_list(manifest.get("missing_required_artifacts"))
    quality_status = _str(quality.get("status")) or "not_run"
    signoff_status = _str(signoff.get("status")) or "not_recorded"
    signoff_schema = _str(signoff.get("schema_version")) or "not_recorded"
    signoff_note = _str(signoff.get("note")) or "No reviewer signoff note recorded yet."
    manager_status = _str(manager_checklist.get("status")) or "not_recorded"
    archive_status = _str(archive_manifest.get("status")) or "not_recorded"
    archive_digest = _str(archive_manifest.get("package_digest")) or "not_recorded"
    archive_file_count = archive_manifest.get("file_count")
    archive_verification_status = (
        _str(archive_verification.get("status")) or "not_recorded"
    )

    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1" />',
        "<title>ArchReview-KG Handoff Review</title>",
        "<style>",
        "body{margin:0;background:#f7f8fb;color:#18202f;font:14px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}",
        ".page{max-width:1180px;margin:0 auto;padding:24px}",
        "header{border-bottom:1px solid #d8deea;padding-bottom:18px;margin-bottom:18px}",
        "h1{font-size:26px;margin:0 0 8px}",
        "h2{font-size:16px;margin:0 0 12px}",
        ".muted{color:#5d6b82}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}",
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
        "@media(max-width:820px){.page{padding:14px}}",
        "</style>",
        "</head>",
        "<body>",
        '<main class="page">',
        "<header>",
        "<h1>ArchReview-KG Handoff Review</h1>",
        '<div class="muted">Static read-only entry for a novice review engineer.</div>',
        "</header>",
        '<section class="grid">',
        _kpi("Manifest", _str(manifest.get("schema_version")), "ok"),
        _kpi("Artifacts", f"{available_count}/{len(artifact_rows)} available", "ok"),
        _kpi("Quality", quality_status, _status_class(quality_status)),
        _kpi("Signoff", signoff_status, _status_class(signoff_status)),
        _kpi("Manager", manager_status, _status_class(manager_status)),
        _kpi("Archive", archive_status, _status_class(archive_status)),
        _kpi(
            "Archive Check",
            archive_verification_status,
            _status_class(archive_verification_status),
        ),
        "</section>",
        '<section class="panel">',
        "<h2>Package Boundaries</h2>",
        f"<p><b>Mutation policy:</b> {_html(_str(manifest.get('mutation_policy')))}</p>",
        '<p><a href="handoff_summary.md">Open handoff_summary.md</a></p>',
        "<ul>",
    ]
    for warning in _str_list(manifest.get("boundary_warnings")):
        lines.append(f"<li>{_html(warning)}</li>")
    lines.extend(["</ul>", "</section>"])

    lines.extend(
        [
            '<section class="panel">',
            "<h2>Quality Gate</h2>",
            f"<p><b>Schema:</b> {_html(_str(quality.get('schema_version')) or 'not_recorded')}</p>",
            f"<p><b>Status:</b> <span class=\"pill\">{_html(quality_status)}</span></p>",
            f"<p>{_html(_str(quality.get('note')) or 'Run archkg handoff-check to record package quality.')}</p>",
            '<p><a href="handoff_quality.json">handoff_quality.json</a> · <a href="handoff_quality.md">handoff_quality.md</a></p>',
            "</section>",
            '<section class="panel">',
            "<h2>Reviewer Signoff</h2>",
            f"<p><b>Schema:</b> {_html(signoff_schema)}</p>",
            f"<p><b>Reviewer:</b> {_html(_str(signoff.get('reviewer')) or 'not_recorded')}</p>",
            f"<p><b>Status:</b> <span class=\"pill\">{_html(signoff_status)}</span></p>",
            f"<p>{_html(signoff_note)}</p>",
            f"<p>{_html(_str(signoff.get('boundary_warning')) or 'Reviewer signoff is not a compliance certificate.')}</p>",
        ]
    )
    blockers = _str_list(signoff.get("blockers"))
    if blockers:
        lines.extend(["<ul>", *[f"<li>{_html(item)}</li>" for item in blockers], "</ul>"])
    lines.extend(
        [
            '<p><a href="reviewer_signoff.json">reviewer_signoff.json</a> · <a href="reviewer_signoff.md">reviewer_signoff.md</a></p>',
            "</section>",
            '<section class="panel">',
            "<h2>Manager Checklist</h2>",
            f"<p><b>Schema:</b> {_html(_str(manager_checklist.get('schema_version')) or 'not_recorded')}</p>",
            f"<p><b>Manager:</b> {_html(_str(manager_checklist.get('manager')) or 'not_recorded')}</p>",
            f"<p><b>Status:</b> <span class=\"pill\">{_html(manager_status)}</span></p>",
            f"<p>{_html(_str(manager_checklist.get('boundary_warning')) or 'Manager checklist is not a compliance certificate.')}</p>",
        ]
    )
    open_items = _str_list(manager_checklist.get("open_items"))
    if open_items:
        lines.extend(["<ul>", *[f"<li>{_html(item)}</li>" for item in open_items], "</ul>"])
    lines.extend(
        [
            '<p><a href="handoff_manager_checklist.json">handoff_manager_checklist.json</a> · <a href="handoff_manager_checklist.md">handoff_manager_checklist.md</a></p>',
            "</section>",
            '<section class="panel">',
            "<h2>Archive Manifest</h2>",
            f"<p><b>Schema:</b> {_html(_str(archive_manifest.get('schema_version')) or 'not_recorded')}</p>",
            f"<p><b>Created by:</b> {_html(_str(archive_manifest.get('created_by')) or 'not_recorded')}</p>",
            f"<p><b>Status:</b> <span class=\"pill\">{_html(archive_status)}</span></p>",
            f"<p><b>Files:</b> {_html(str(archive_file_count) if isinstance(archive_file_count, int) else 'not_recorded')}</p>",
            f"<p><b>package_digest:</b> <code>{_html(archive_digest)}</code></p>",
            f"<p>{_html(_str(archive_manifest.get('boundary_warning')) or 'Archive manifest is not a compliance certificate.')}</p>",
            '<p><a href="handoff_archive_manifest.json">handoff_archive_manifest.json</a> · <a href="handoff_archive_manifest.md">handoff_archive_manifest.md</a></p>',
            f"<p><b>Verification schema:</b> {_html(_str(archive_verification.get('schema_version')) or 'not_recorded')}</p>",
            f"<p><b>Verification status:</b> <span class=\"pill\">{_html(archive_verification_status)}</span></p>",
            '<p><a href="handoff_archive_verification.json">handoff_archive_verification.json</a> · <a href="handoff_archive_verification.md">handoff_archive_verification.md</a></p>',
            "</section>",
            '<section class="panel">',
            "<h2>Artifacts</h2>",
            "<table>",
            "<thead><tr><th>Artifact</th><th>Required</th><th>Status</th><th>Tier</th><th>Purpose</th></tr></thead>",
            "<tbody>",
        ]
    )
    for row in artifact_rows:
        artifact = _str(row.get("artifact"))
        rel = _str(row.get("package_path"))
        label = f'<a href="{_html_attr(rel)}">{_html(artifact)}</a>' if rel else _html(artifact)
        lines.append(
            "<tr>"
            f"<td>{label}</td>"
            f"<td>{'yes' if row.get('required') else 'no'}</td>"
            f"<td>{_html(_str(row.get('status')))}</td>"
            f"<td>{_html(_str(row.get('tier')))}</td>"
            f"<td>{_html(_str(row.get('purpose')))}</td>"
            "</tr>"
        )
    lines.extend(["</tbody>", "</table>", "</section>"])
    if required_missing:
        lines.extend(['<section class="panel">', "<h2>Missing Required Artifacts</h2>", "<ul>"])
        lines.extend(f"<li>{_html(item)}</li>" for item in required_missing)
        lines.extend(["</ul>", "</section>"])
    lines.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(lines)


def write_handoff_reviewer_signoff(
    package_dir: Path,
    *,
    reviewer: str,
    status: str,
    note: str,
    blockers: list[str] | None = None,
    needs_info: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> Path:
    package_dir = package_dir.resolve()
    manifest = _load_manifest(package_dir / "handoff_manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise FileNotFoundError(f"handoff package manifest not found: {package_dir}")
    normalized_status = _normalize_signoff_status(status)
    payload = {
        "schema_version": SIGNOFF_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "package_dir": str(package_dir),
        "source_run_dir": _str(manifest.get("source_run_dir")),
        "mutation_policy": "package_note_only_no_source_run_mutation",
        "reviewer": reviewer,
        "status": normalized_status,
        "note": note,
        "blockers": blockers or [],
        "needs_info": needs_info or [],
        "next_actions": next_actions or [],
        "boundary_warning": (
            "Reviewer signoff is a handoff note, not a compliance certificate; "
            "it does not mutate source run artifacts or confirm candidate issues."
        ),
    }
    path = package_dir / "reviewer_signoff.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (package_dir / "reviewer_signoff.md").write_text(
        render_handoff_reviewer_signoff_markdown(payload),
        encoding="utf-8",
    )
    write_handoff_index(package_dir, signoff=payload)
    return path


def render_handoff_reviewer_signoff_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Handoff Reviewer Signoff",
        "",
        f"Reviewer: `{_str(payload.get('reviewer'))}`",
        f"Status: `{_str(payload.get('status'))}`",
        f"Mutation policy: `{_str(payload.get('mutation_policy'))}`",
        "",
        _str(payload.get("boundary_warning")),
        "",
        "## Note",
        "",
        _str(payload.get("note")) or "-",
        "",
        "## Blockers",
        "",
    ]
    blockers = _str_list(payload.get("blockers"))
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- None")
    lines.extend(["", "## Needs Info", ""])
    needs_info = _str_list(payload.get("needs_info"))
    lines.extend(f"- {item}" for item in needs_info) if needs_info else lines.append("- None")
    lines.extend(["", "## Next Actions", ""])
    next_actions = _str_list(payload.get("next_actions"))
    lines.extend(f"- {item}" for item in next_actions) if next_actions else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_handoff_manager_checklist(
    package_dir: Path,
    *,
    manager: str,
    note: str = "",
) -> Path:
    package_dir = package_dir.resolve()
    payload = build_handoff_manager_checklist(
        package_dir,
        manager=manager,
        note=note,
    )
    path = package_dir / "handoff_manager_checklist.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (package_dir / "handoff_manager_checklist.md").write_text(
        render_handoff_manager_checklist_markdown(payload),
        encoding="utf-8",
    )
    write_handoff_index(package_dir, manager_checklist=payload)
    return path


def build_handoff_manager_checklist(
    package_dir: Path,
    *,
    manager: str,
    note: str = "",
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    manifest = _load_manifest(package_dir / "handoff_manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise FileNotFoundError(f"handoff package manifest not found: {package_dir}")
    quality = _load_optional_json(package_dir / "handoff_quality.json") or {}
    signoff = _load_optional_json(package_dir / "reviewer_signoff.json") or {}
    items = _manager_checklist_items(manifest, quality, signoff)
    open_items = [
        _str(item.get("detail"))
        for item in items
        if item.get("status") != "pass" and _str(item.get("detail"))
    ]
    status = _manager_status(items)
    artifact_rows = _artifact_rows(manifest)
    return {
        "schema_version": MANAGER_CHECKLIST_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "package_dir": str(package_dir),
        "source_run_dir": _str(manifest.get("source_run_dir")),
        "mutation_policy": "package_checklist_only_no_source_run_mutation",
        "manager": manager,
        "status": status,
        "note": note,
        "summary": {
            "quality_status": _str(quality.get("status")) or "missing",
            "signoff_status": _str(signoff.get("status")) or "missing",
            "missing_required_count": len(_str_list(manifest.get("missing_required_artifacts"))),
            "artifact_available_count": sum(
                1 for row in artifact_rows if row.get("status") == "available"
            ),
            "artifact_total_count": len(artifact_rows),
        },
        "checklist_items": items,
        "open_items": open_items,
        "boundary_warning": (
            "Manager checklist is a package acceptance aid, not a compliance certificate; "
            "it does not mutate source run artifacts or confirm candidate issues."
        ),
    }


def render_handoff_manager_checklist_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Handoff Manager Checklist",
        "",
        f"Manager: `{_str(payload.get('manager'))}`",
        f"Status: `{_str(payload.get('status'))}`",
        f"Mutation policy: `{_str(payload.get('mutation_policy'))}`",
        "",
        _str(payload.get("boundary_warning")),
        "",
        "## Summary",
        "",
    ]
    raw_summary = payload.get("summary")
    summary: dict[str, Any] = raw_summary if isinstance(raw_summary, dict) else {}
    lines.extend(
        [
            f"- Quality: `{_str(summary.get('quality_status'))}`",
            f"- Reviewer signoff: `{_str(summary.get('signoff_status'))}`",
            f"- Available artifacts: `{summary.get('artifact_available_count')}/{summary.get('artifact_total_count')}`",
            f"- Missing required artifacts: `{summary.get('missing_required_count')}`",
            "",
            "## Checklist",
            "",
            "| Item | Status | Detail |",
            "|---|---|---|",
        ]
    )
    for item in _list_of_dicts(payload.get("checklist_items")):
        lines.append(
            "| "
            f"`{_str(item.get('id'))}` | "
            f"{_str(item.get('status'))} | "
            f"{_str(item.get('detail'))} |"
        )
    open_items = _str_list(payload.get("open_items"))
    if open_items:
        lines.extend(["", "## Open Items", ""])
        lines.extend(f"- {item}" for item in open_items)
    lines.append("")
    return "\n".join(lines)


def write_handoff_archive_manifest(
    package_dir: Path,
    *,
    created_by: str = "",
    note: str = "",
) -> Path:
    """Write a package-local integrity manifest with stable file checksums."""

    package_dir = package_dir.resolve()
    payload = build_handoff_archive_manifest(
        package_dir,
        created_by=created_by,
        note=note,
    )
    path = package_dir / "handoff_archive_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (package_dir / "handoff_archive_manifest.md").write_text(
        render_handoff_archive_manifest_markdown(payload),
        encoding="utf-8",
    )
    write_handoff_index(package_dir, archive_manifest=payload)
    return path


def build_handoff_archive_manifest(
    package_dir: Path,
    *,
    created_by: str = "",
    note: str = "",
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    manifest = _load_manifest(package_dir / "handoff_manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise FileNotFoundError(f"handoff package manifest not found: {package_dir}")
    files = _archive_file_entries(package_dir)
    return {
        "schema_version": ARCHIVE_MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "package_dir": str(package_dir),
        "source_run_dir": _str(manifest.get("source_run_dir")),
        "mutation_policy": ARCHIVE_MANIFEST_MUTATION_POLICY,
        "created_by": created_by,
        "status": "archive_manifest_ready" if files else "archive_manifest_empty",
        "note": note,
        "excluded_paths": list(ARCHIVE_MANIFEST_EXCLUDED_PATHS),
        "file_count": len(files),
        "total_size_bytes": sum(_int(item.get("size_bytes")) for item in files),
        "files": files,
        "package_digest": _archive_package_digest(files),
        "boundary_warning": (
            "Archive manifest records transfer integrity checksums only; it is not a "
            "compliance certificate and does not mutate source run artifacts."
        ),
    }


def render_handoff_archive_manifest_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Handoff Archive Manifest",
        "",
        f"Status: `{_str(payload.get('status'))}`",
        f"Created by: `{_str(payload.get('created_by')) or 'not_recorded'}`",
        f"Mutation policy: `{_str(payload.get('mutation_policy'))}`",
        f"package_digest: `{_str(payload.get('package_digest'))}`",
        f"File count: `{payload.get('file_count')}`",
        f"Total size bytes: `{payload.get('total_size_bytes')}`",
        "",
        _str(payload.get("boundary_warning")),
        "",
        "## Excluded Paths",
        "",
    ]
    excluded_paths = _str_list(payload.get("excluded_paths"))
    lines.extend(f"- `{item}`" for item in excluded_paths) if excluded_paths else lines.append("- None")
    note = _str(payload.get("note"))
    if note:
        lines.extend(["", "## Note", "", note])
    lines.extend(
        [
            "",
            "## Files",
            "",
            "| Path | Role | Size Bytes | SHA-256 |",
            "|---|---|---:|---|",
        ]
    )
    for row in _list_of_dicts(payload.get("files")):
        lines.append(
            "| "
            f"`{_str(row.get('path'))}` | "
            f"{_str(row.get('role'))} | "
            f"{_int(row.get('size_bytes'))} | "
            f"`{_str(row.get('sha256'))}` |"
        )
    lines.append("")
    return "\n".join(lines)


def write_handoff_archive_verification(package_dir: Path) -> Path:
    """Verify package files against a previously written archive manifest."""

    package_dir = package_dir.resolve()
    payload = build_handoff_archive_verification(package_dir)
    path = package_dir / "handoff_archive_verification.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (package_dir / "handoff_archive_verification.md").write_text(
        render_handoff_archive_verification_markdown(payload),
        encoding="utf-8",
    )
    write_handoff_index(package_dir, archive_verification=payload)
    return path


def build_handoff_archive_verification(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    manifest = _load_manifest(package_dir / "handoff_manifest.json")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise FileNotFoundError(f"handoff package manifest not found: {package_dir}")
    archive_manifest_path = package_dir / "handoff_archive_manifest.json"
    archive_manifest = _load_optional_json(archive_manifest_path)
    if not archive_manifest:
        raise FileNotFoundError(
            f"handoff archive manifest not found: {archive_manifest_path}"
        )
    if archive_manifest.get("schema_version") != ARCHIVE_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "handoff archive manifest schema must be "
            f"{ARCHIVE_MANIFEST_SCHEMA_VERSION}"
        )

    excluded_paths = _archive_verification_excluded_paths(archive_manifest)
    actual_files = _archive_file_entries(package_dir, excluded_paths=excluded_paths)
    expected_files = _list_of_dicts(archive_manifest.get("files"))
    actual_by_path = {_str(row.get("path")): row for row in actual_files}
    expected_by_path = {_str(row.get("path")): row for row in expected_files}
    missing_files = [
        path for path in sorted(expected_by_path) if path not in actual_by_path
    ]
    unexpected_files = [
        path for path in sorted(actual_by_path) if path not in expected_by_path
    ]
    changed_files = _archive_changed_files(expected_by_path, actual_by_path)
    actual_digest = _archive_package_digest(actual_files)
    expected_digest = _str(archive_manifest.get("package_digest"))
    digest_match = expected_digest == actual_digest
    checks = {
        "manifest_schema": _check("blocker", True, []),
        "files_present": _check(
            "blocker",
            not missing_files,
            [f"missing package file: {item}" for item in missing_files],
        ),
        "file_checksums_match": _check(
            "blocker",
            not changed_files,
            [f"changed package file: {_str(item.get('path'))}" for item in changed_files],
        ),
        "no_unexpected_files": _check(
            "warning",
            not unexpected_files,
            [f"unexpected package file: {item}" for item in unexpected_files],
        ),
        "package_digest_match": _check(
            "blocker",
            digest_match,
            [] if digest_match else ["package digest differs from archive manifest"],
        ),
    }
    blockers = [
        detail
        for check in checks.values()
        if check["severity"] == "blocker" and check["passed"] is False
        for detail in _str_list(check.get("details"))
    ]
    warnings = [
        detail
        for check in checks.values()
        if check["severity"] == "warning" and check["passed"] is False
        for detail in _str_list(check.get("details"))
    ]
    return {
        "schema_version": ARCHIVE_VERIFICATION_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "package_dir": str(package_dir),
        "source_run_dir": _str(manifest.get("source_run_dir")),
        "archive_manifest_path": str(archive_manifest_path),
        "mutation_policy": ARCHIVE_VERIFICATION_MUTATION_POLICY,
        "status": "archive_drift" if blockers or warnings else "archive_verified",
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "expected_file_count": len(expected_files),
        "actual_file_count": len(actual_files),
        "checked_file_count": len(expected_files) - len(missing_files),
        "excluded_paths": excluded_paths,
        "missing_files": missing_files,
        "changed_files": changed_files,
        "unexpected_files": unexpected_files,
        "package_digest_expected": expected_digest,
        "package_digest_actual": actual_digest,
        "boundary_warning": (
            "Archive verification checks transfer integrity only; it is not a "
            "compliance certificate and does not mutate source run artifacts."
        ),
    }


def render_handoff_archive_verification_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Handoff Archive Verification",
        "",
        f"Status: `{_str(payload.get('status'))}`",
        f"Mutation policy: `{_str(payload.get('mutation_policy'))}`",
        f"Expected digest: `{_str(payload.get('package_digest_expected'))}`",
        f"Actual digest: `{_str(payload.get('package_digest_actual'))}`",
        "",
        _str(payload.get("boundary_warning")),
        "",
        "## Checks",
        "",
        "| Check | Severity | Status | Details |",
        "|---|---|---:|---|",
    ]
    checks = payload.get("checks")
    if isinstance(checks, dict):
        for check_id, raw in checks.items():
            check = raw if isinstance(raw, dict) else {}
            details = "; ".join(_str_list(check.get("details"))) or "-"
            lines.append(
                "| "
                f"{check_id} | "
                f"{_str(check.get('severity'))} | "
                f"{'PASS' if check.get('passed') else 'FAIL'} | "
                f"{details} |"
            )
    _extend_simple_section(lines, "Missing Files", _str_list(payload.get("missing_files")))
    _extend_changed_file_section(lines, _list_of_dicts(payload.get("changed_files")))
    _extend_simple_section(lines, "Unexpected Files", _str_list(payload.get("unexpected_files")))
    lines.append("")
    return "\n".join(lines)


def _copy_artifact(
    run_dir: Path,
    artifacts_dir: Path,
    spec: HandoffArtifactSpec,
) -> dict[str, Any]:
    source = run_dir / spec.name
    package_path = artifacts_dir / spec.name
    if source.is_file():
        shutil.copy2(source, package_path)
        status = "available"
        package_rel = f"artifacts/{spec.name}"
        source_path = str(source)
    else:
        status = "missing"
        package_rel = ""
        source_path = ""
    return {
        "artifact": spec.name,
        "required": spec.required,
        "tier": spec.tier,
        "status": status,
        "source_path": source_path,
        "package_path": package_rel,
        "purpose": spec.purpose,
    }


def _copy_preview_page_artifacts(
    run_dir: Path,
    artifacts_dir: Path,
    existing_statuses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    preview_manifest = run_dir / "preview_pages.json"
    if not preview_manifest.is_file():
        return []
    try:
        payload = json.loads(preview_manifest.read_text("utf-8"))
    except json.JSONDecodeError:
        return []
    layers = payload.get("layers") if isinstance(payload, dict) else None
    if not isinstance(layers, dict):
        return []

    existing_by_artifact = {
        _str(row.get("artifact")): row
        for row in existing_statuses
        if _str(row.get("artifact"))
    }
    statuses: list[dict[str, Any]] = []
    for name in _preview_asset_names(layers):
        existing = existing_by_artifact.get(name)
        if existing and existing.get("status") == "available":
            continue
        if existing:
            existing["required"] = True
            existing["purpose"] = "Preview page image referenced by preview_pages.json."
            continue
        source = run_dir / name
        if not source.is_file():
            statuses.append(
                {
                    "artifact": name,
                    "required": True,
                    "tier": "visual",
                    "status": "missing",
                    "source_path": "",
                    "package_path": "",
                    "purpose": "Preview page image referenced by preview_pages.json.",
                }
            )
            continue
        shutil.copy2(source, artifacts_dir / name)
        statuses.append(
            {
                "artifact": name,
                "required": True,
                "tier": "visual",
                "status": "available",
                "source_path": str(source),
                "package_path": f"artifacts/{name}",
                "purpose": "Preview page image referenced by preview_pages.json.",
            }
        )
    return statuses


def _preview_asset_names(layers: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for rows in layers.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            src = _str(row.get("src"))
            if not src or "/" in src or "\\" in src:
                continue
            names.add(src)
    return sorted(names)


def _write_handoff_index_from_payloads(
    package_dir: Path,
    manifest: dict[str, Any],
    *,
    quality: dict[str, Any] | None = None,
    signoff: dict[str, Any] | None = None,
    manager_checklist: dict[str, Any] | None = None,
    archive_manifest: dict[str, Any] | None = None,
    archive_verification: dict[str, Any] | None = None,
) -> Path:
    quality = quality if quality is not None else _load_optional_json(
        package_dir / "handoff_quality.json"
    )
    signoff = signoff if signoff is not None else _load_optional_json(
        package_dir / "reviewer_signoff.json"
    )
    manager_checklist = (
        manager_checklist
        if manager_checklist is not None
        else _load_optional_json(package_dir / "handoff_manager_checklist.json")
    )
    archive_manifest = (
        archive_manifest
        if archive_manifest is not None
        else _load_optional_json(package_dir / "handoff_archive_manifest.json")
    )
    archive_verification = (
        archive_verification
        if archive_verification is not None
        else _load_optional_json(package_dir / "handoff_archive_verification.json")
    )
    path = package_dir / "index.html"
    path.write_text(
        render_handoff_index_html(
            manifest,
            quality=quality,
            signoff=signoff,
            manager_checklist=manager_checklist,
            archive_manifest=archive_manifest,
            archive_verification=archive_verification,
        ),
        encoding="utf-8",
    )
    return path


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "missing",
            "artifact_statuses": [],
            "missing_required_artifacts": ["handoff_manifest.json"],
            "boundary_warnings": [],
        }
    try:
        raw = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "schema_version": "invalid",
            "artifact_statuses": [],
            "missing_required_artifacts": ["handoff_manifest.json"],
            "boundary_warnings": [],
            "manifest_error": str(exc),
        }
    return raw if isinstance(raw, dict) else {"schema_version": "invalid"}


def _check_manifest_schema(manifest: dict[str, Any]) -> dict[str, Any]:
    passed = manifest.get("schema_version") == SCHEMA_VERSION
    details = [] if passed else [f"manifest schema is {_str(manifest.get('schema_version')) or 'missing'}"]
    return _check("blocker", passed, details)


def _check_read_only_policy(manifest: dict[str, Any]) -> dict[str, Any]:
    passed = (
        manifest.get("read_only") is True
        and manifest.get("mutation_policy") == MUTATION_POLICY
    )
    details = [] if passed else ["handoff manifest must be read_only with copy-only mutation policy"]
    return _check("blocker", passed, details)


def _check_required_artifacts_present(manifest: dict[str, Any]) -> dict[str, Any]:
    missing = _str_list(manifest.get("missing_required_artifacts"))
    return _check("blocker", not missing, [f"required artifact missing: {item}" for item in missing])


def _check_copied_artifacts_exist(
    package_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    missing: list[str] = []
    for row in _artifact_rows(manifest):
        if row.get("status") != "available":
            continue
        artifact = _str(row.get("artifact"))
        rel = _str(row.get("package_path"))
        if not rel or not (package_dir / rel).is_file():
            missing.append(artifact or rel or "unknown")
    return _check("blocker", not missing, [f"copied artifact missing: {item}" for item in missing])


def _check_boundary_warnings_present(manifest: dict[str, Any]) -> dict[str, Any]:
    joined = " ".join(_str_list(manifest.get("boundary_warnings"))).lower()
    required_terms = ["candidate", "preview", "archkg review-state", "missing input", "evidence_ready"]
    missing_terms = [term for term in required_terms if term not in joined]
    return _check("blocker", not missing_terms, [f"boundary warning missing term: {item}" for item in missing_terms])


def _check(severity: str, passed: bool, details: list[str]) -> dict[str, Any]:
    return {"severity": severity, "passed": passed, "details": details}


def _manager_checklist_items(
    manifest: dict[str, Any],
    quality: dict[str, Any],
    signoff: dict[str, Any],
) -> list[dict[str, str]]:
    missing_required = _str_list(manifest.get("missing_required_artifacts"))
    quality_status = _str(quality.get("status")) or "missing"
    signoff_status = _str(signoff.get("status")) or "missing"
    boundary_check = _check_boundary_warnings_present(manifest)
    return [
        _manager_item(
            "required_artifacts_present",
            "pass" if not missing_required else "fail",
            "all required artifacts present"
            if not missing_required
            else f"missing required artifacts: {', '.join(missing_required)}",
        ),
        _manager_item(
            "handoff_quality_ready",
            _quality_manager_item_status(quality_status),
            f"handoff quality {quality_status}",
        ),
        _manager_item(
            "reviewer_signoff_ready",
            _signoff_manager_item_status(signoff_status),
            f"reviewer signoff {signoff_status}",
        ),
        _manager_item(
            "boundary_warnings_present",
            "pass" if boundary_check["passed"] else "fail",
            "boundary warnings present"
            if boundary_check["passed"]
            else "; ".join(_str_list(boundary_check.get("details"))),
        ),
    ]


def _manager_item(item_id: str, status: str, detail: str) -> dict[str, str]:
    return {"id": item_id, "status": status, "detail": detail}


def _quality_manager_item_status(status: str) -> str:
    if status == "handoff_ready":
        return "pass"
    if status == "handoff_ready_with_warnings":
        return "needs_info"
    return "fail" if status == "not_ready" else "needs_info"


def _signoff_manager_item_status(status: str) -> str:
    if status == "ready":
        return "pass"
    if status == "blocked":
        return "fail"
    return "needs_info"


def _manager_status(items: list[dict[str, str]]) -> str:
    statuses = {_str(item.get("status")) for item in items}
    if "fail" in statuses:
        return "manager_blocked"
    if "needs_info" in statuses:
        return "manager_needs_info"
    return "manager_ready"


def _archive_file_entries(
    package_dir: Path,
    *,
    excluded_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    excluded = set(excluded_paths or ARCHIVE_MANIFEST_EXCLUDED_PATHS)
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(package_dir).as_posix()
        if rel in excluded:
            continue
        size_bytes = path.stat().st_size
        entries.append(
            {
                "path": rel,
                "role": _archive_file_role(rel),
                "size_bytes": size_bytes,
                "sha256": _sha256_file(path),
            }
        )
    return entries


def _archive_verification_excluded_paths(
    archive_manifest: dict[str, Any],
) -> list[str]:
    excluded = set(_str_list(archive_manifest.get("excluded_paths")))
    excluded.update(ARCHIVE_MANIFEST_EXCLUDED_PATHS)
    excluded.update(ARCHIVE_VERIFICATION_EXCLUDED_PATHS)
    return sorted(excluded)


def _archive_changed_files(
    expected_by_path: dict[str, dict[str, Any]],
    actual_by_path: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for path in sorted(set(expected_by_path).intersection(actual_by_path)):
        expected = expected_by_path[path]
        actual = actual_by_path[path]
        expected_sha = _str(expected.get("sha256"))
        actual_sha = _str(actual.get("sha256"))
        expected_size = _int(expected.get("size_bytes"))
        actual_size = _int(actual.get("size_bytes"))
        if expected_sha == actual_sha and expected_size == actual_size:
            continue
        changed.append(
            {
                "path": path,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "expected_size_bytes": expected_size,
                "actual_size_bytes": actual_size,
            }
        )
    return changed


def _archive_file_role(rel_path: str) -> str:
    if rel_path.startswith("artifacts/"):
        return "copied_artifact"
    if rel_path in {"handoff_manifest.json", "handoff_summary.md"}:
        return "package_manifest"
    if rel_path.startswith("handoff_quality"):
        return "quality"
    if rel_path.startswith("reviewer_signoff"):
        return "signoff"
    if rel_path.startswith("handoff_manager_checklist"):
        return "manager_checklist"
    return "package_file"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_package_digest(files: list[dict[str, Any]]) -> str:
    stable = [
        {
            "path": _str(row.get("path")),
            "size_bytes": _int(row.get("size_bytes")),
            "sha256": _str(row.get("sha256")),
        }
        for row in sorted(files, key=lambda item: _str(item.get("path")))
    ]
    raw = json.dumps(
        stable,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _extend_simple_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.extend(["", f"## {title}", ""])
    lines.extend(f"- `{item}`" for item in items)


def _extend_changed_file_section(
    lines: list[str],
    changed_files: list[dict[str, Any]],
) -> None:
    if not changed_files:
        return
    lines.extend(
        [
            "",
            "## Changed Files",
            "",
            "| Path | Expected SHA-256 | Actual SHA-256 | Expected Bytes | Actual Bytes |",
            "|---|---|---|---:|---:|",
        ]
    )
    for item in changed_files:
        lines.append(
            "| "
            f"`{_str(item.get('path'))}` | "
            f"`{_str(item.get('expected_sha256'))}` | "
            f"`{_str(item.get('actual_sha256'))}` | "
            f"{_int(item.get('expected_size_bytes'))} | "
            f"{_int(item.get('actual_size_bytes'))} |"
        )


def _kpi(label: str, value: str, class_name: str = "") -> str:
    class_attr = f" {class_name}" if class_name else ""
    return (
        f'<div class="kpi{class_attr}">'
        f'<span class="muted">{_html(label)}</span>'
        f"<b>{_html(value)}</b>"
        "</div>"
    )


def _status_class(status: str) -> str:
    if status in {
        "handoff_ready",
        "ready",
        "manager_ready",
        "archive_manifest_ready",
        "archive_verified",
    }:
        return "ok"
    if status in {
        "not_ready",
        "blocked",
        "manager_blocked",
        "archive_manifest_empty",
        "archive_drift",
    }:
        return "bad"
    if status in {
        "handoff_ready_with_warnings",
        "manager_needs_info",
        "needs_info",
        "not_run",
    }:
        return "warn"
    return ""


def _normalize_signoff_status(status: str) -> str:
    value = status.strip().lower()
    allowed = {"ready", "needs_info", "blocked"}
    if value not in allowed:
        raise ValueError(
            "signoff status must be one of: ready, needs_info, blocked"
        )
    return value


def _validate_paths(run_dir: Path, package_dir: Path) -> None:
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"run_dir not found: {run_dir}")
    if package_dir == run_dir or package_dir.is_relative_to(run_dir):
        raise ValueError(
            "handoff package directory must be outside the source run directory"
        )


def _commands(run_dir: Path) -> list[dict[str, str]]:
    return [
        {
            "label": "open viewer",
            "command": f"archkg viewer -o {run_dir} --source <source.pdf>",
        },
        {
            "label": "update primary review state",
            "command": (
                f"archkg review-state {run_dir} <issue_id> "
                '--status needs_info --reviewer <name> --note "<note>"'
            ),
        },
        {
            "label": "build rerun diff",
            "command": f"archkg review-diff <before_run> {run_dir}",
        },
    ]


def _artifact_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("artifact_statuses")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _list_of_dicts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _str_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _html(raw: object) -> str:
    return html.escape(_str(raw), quote=False)


def _html_attr(raw: object) -> str:
    return html.escape(_str(raw), quote=True)


__all__ = [
    "ARCHIVE_MANIFEST_SCHEMA_VERSION",
    "ARCHIVE_VERIFICATION_SCHEMA_VERSION",
    "ARTIFACTS",
    "BOUNDARY_WARNINGS",
    "MANAGER_CHECKLIST_SCHEMA_VERSION",
    "MUTATION_POLICY",
    "QUALITY_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "SIGNOFF_SCHEMA_VERSION",
    "build_handoff_archive_manifest",
    "build_handoff_archive_verification",
    "build_handoff_manager_checklist",
    "build_handoff_package_quality",
    "render_handoff_archive_manifest_markdown",
    "render_handoff_archive_verification_markdown",
    "render_handoff_index_html",
    "render_handoff_manager_checklist_markdown",
    "render_handoff_package_quality_markdown",
    "render_handoff_reviewer_signoff_markdown",
    "render_handoff_summary",
    "write_handoff_archive_manifest",
    "write_handoff_archive_verification",
    "write_handoff_index",
    "write_handoff_manager_checklist",
    "write_handoff_package",
    "write_handoff_package_quality_json",
    "write_handoff_package_quality_markdown",
    "write_handoff_reviewer_signoff",
]
