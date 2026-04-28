from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "handoff_package.v1"

MUTATION_POLICY = "copy_artifacts_only_no_source_run_mutation"

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
        "source_preview.png",
        False,
        "visual",
        "Rendered source preview.",
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


def _str_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


__all__ = [
    "ARTIFACTS",
    "BOUNDARY_WARNINGS",
    "MUTATION_POLICY",
    "SCHEMA_VERSION",
    "render_handoff_summary",
    "write_handoff_package",
]
