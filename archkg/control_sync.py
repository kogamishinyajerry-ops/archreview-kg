from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TASK_MARK = "Notion 页内字段化写入 + 控制中枢同步能力验证 | 本次任务: Codex 全权负责"


_UUID_WITH_DASHES = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_HEX_ONLY = re.compile(r"^[0-9a-fA-F]{32,33}$")


def collect_control_snapshot(*, repo_root: Path = Path("."), run_dir: Path | None = None) -> dict[str, Any]:
    run_dir = run_dir or (repo_root / "out")
    git_snapshot = _collect_git_snapshot(repo_root)
    run_snapshot = _collect_run_snapshot(run_dir)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root.resolve()),
        "run_dir": str(run_dir.resolve()),
        "git": git_snapshot,
        "run": run_snapshot,
    }


def sync_control_state(
    *,
    repo_root: Path,
    run_dir: Path,
    sync_github: bool,
    sync_notion: bool,
    notion_api_key: str | None,
    notion_page_id: str | None,
) -> dict[str, Any]:
    snapshot = collect_control_snapshot(repo_root=repo_root, run_dir=run_dir)
    result: dict[str, Any] = {
        "github": None,
        "notion": None,
    }

    local_status_path = run_dir / "control_sync.json"
    run_dir.mkdir(parents=True, exist_ok=True)
    local_status_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    if sync_github:
        result["github"] = _collect_github_snapshot(snapshot["git"])

    if sync_notion:
        notion_page_id = _normalize_notion_page_id(
            notion_page_id,
            api_key=notion_api_key,
        )
        result["notion"] = _append_notion_sync_note(
            api_key=notion_api_key,
            page_id=notion_page_id,
            snapshot=snapshot,
            local_status_path=local_status_path,
            mode="fieldized",
        )

    return {
        "run_dir": str(run_dir),
        "local_status_file": str(local_status_path),
        "snapshot": snapshot,
        "sync": result,
    }


def _collect_run_snapshot(run_dir: Path) -> dict[str, Any]:
    if not run_dir.exists() or not run_dir.is_dir():
        return {"exists": False}
    artifact_names = [
        p.name
        for p in run_dir.iterdir()
        if p.is_file() and p.name in {
            "issues.json",
            "review_state.json",
            "entity_graph.json",
            "drawing_understanding.json",
            "review_workbench.json",
            "sheet_graphs.json",
            "sheet_issues.json",
            "rule_input_readiness.json",
            "sheet_classification.json",
            "sheet_routing.json",
            "sheet_region_candidates.json",
            "sheet_region_candidates_overlay.png",
            "entity_overlay.png",
            "annotated.pdf",
            "report.md",
            "feedback.yaml",
            "ifc_validation.json",
            "ifc_issues.json",
            "ids_report_raw.json",
            "rule_card_draft.json",
            "run_meta.json",
            "primitives.json",
        }
    ]
    return {
        "exists": True,
        "file_count": len([p for p in run_dir.iterdir() if p.is_file()]),
        "artifacts": artifact_names,
    }


def _collect_git_snapshot(repo_root: Path) -> dict[str, Any]:
    if not (repo_root / ".git").exists() and not (repo_root / "../.git").exists():
        return {"status": "not_a_git_repo"}

    git = _safe_git
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    sha = git(["rev-parse", "HEAD"], repo_root)
    short_sha = git(["rev-parse", "--short", "HEAD"], repo_root)
    commit_subject = git(["log", "-1", "--pretty=%s"], repo_root)
    commit_time = git(["log", "-1", "--pretty=%cI"], repo_root)
    status = git(["status", "--short"], repo_root)
    remote_origin = git(["config", "--get", "remote.origin.url"], repo_root)
    ahead_behind = _calc_ahead_behind(branch, remote_origin, repo_root)

    return {
        "status": "ok" if branch and sha else "partial",
        "branch": branch,
        "commit": {"sha": sha, "short_sha": short_sha, "subject": commit_subject, "time": commit_time},
        "working_tree_dirty": bool(status),
        "status_lines": status.split("\n") if status else [],
        "remote_origin": remote_origin,
        "ahead_behind": ahead_behind,
    }


def _collect_github_snapshot(git_snapshot: dict[str, Any]) -> dict[str, Any]:
    remote = str(git_snapshot.get("remote_origin") or "").strip()
    parsed = _parse_github_repo(remote)
    if not parsed:
        return {"status": "unavailable", "reason": "missing_or_unparsed_origin"}
    owner, repo = parsed

    repo_meta, repo_detail = _gh_api_with_error(f"/repos/{owner}/{repo}")
    if repo_meta is None:
        return {
            "status": "error",
            "reason": "repo_meta_api_failed",
            "detail": repo_detail or "no response",
        }

    pulls, pulls_detail = _gh_api_with_error(f"/repos/{owner}/{repo}/pulls?state=open&per_page=20")
    if isinstance(repo_meta, dict):
        open_prs = [
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "author": item.get("user", {}).get("login"),
                "url": item.get("html_url"),
            }
            for item in (pulls or [])
            if isinstance(item, dict)
        ]
        result: dict[str, Any] = {
            "status": "ok",
            "repo": f"{owner}/{repo}",
            "default_branch": repo_meta.get("default_branch"),
            "open_issues": repo_meta.get("open_issues_count"),
            "forks": repo_meta.get("forks_count"),
            "stars": repo_meta.get("stargazers_count"),
            "open_pull_requests": open_prs,
        }
        if pulls_detail:
            result["pulls_detail"] = pulls_detail
        return result
    if pulls_detail:
        return {
            "status": "error",
            "reason": "repo_meta_shape_invalid",
            "detail": pulls_detail,
        }
    return {"status": "error", "reason": "repo_meta_shape_invalid", "detail": str(repo_meta)}


def _append_notion_sync_note(
    *,
    api_key: str | None,
    page_id: str | None,
    snapshot: dict[str, Any],
    local_status_path: Path,
    mode: str = "fieldized",
) -> dict[str, Any]:
    if not api_key:
        return {"status": "unavailable", "reason": "missing_api_key"}
    if not page_id:
        return {"status": "unavailable", "reason": "missing_page_id"}
    if mode == "fieldized":
        fieldized = _append_notion_page_fields(
            api_key=api_key,
            page_id=page_id,
            snapshot=snapshot,
            local_status_path=local_status_path,
        )
        if fieldized.get("status") == "ok":
            _append_notion_callout(
                api_key=api_key,
                page_id=page_id,
                content=(
                    "Notion 字段化成功(可见字段已更新) | 任务:"
                    "Notion 页内字段化写入 + 控制中枢同步能力验证 | "
                    "责任: Codex 全权负责 | 结果: 本次 run meta 已成功写入 Notion 可见同步痕迹"
                ),
                icon="✅",
                color="blue",
            )
            return fieldized
        fallback_reason = fieldized.get("reason")
        db_row = _append_notion_child_database_row(
            api_key=api_key,
            page_id=page_id,
            snapshot=snapshot,
            local_status_path=local_status_path,
        )
        if db_row.get("status") == "ok":
            db_row = dict(db_row)
            if fallback_reason:
                db_row["fallback_reason"] = fallback_reason
            _append_notion_callout(
                api_key=api_key,
                page_id=page_id,
                content=(
                    f"Notion 字段化未命中页面字段({fallback_reason or 'unknown'}), 已落库到子页面数据库 | 任务:"
                    "Notion 页内字段化写入 + 控制中枢同步能力验证 | 责任: Codex 全权负责"
                ),
                icon="🧾",
                color="blue",
            )
            return db_row
        if not fallback_reason and db_row.get("reason"):
            fallback_reason = db_row.get("reason")
    else:
        fallback_reason = None

    # 回退策略: 页面非数据库行/字段不可写时, 写一段可见子块, 确保同步可见.
    payload = {
        "children": [
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": _notion_note_text(snapshot, local_status_path),
                            },
                        }
                    ]
                },
            },
            *_fieldized_fallback_table(snapshot, local_status_path),
        ]
    }
    if fallback_reason:
        fallback_label = f"Notion 字段化写入失败 ({fallback_reason}), 已回退到块级落盘。"
    else:
        fallback_label = "Notion 字段化写入已回退到块级落盘。"
    children = [
        *_normalize_children(payload["children"]),
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": fallback_label}}],
                "icon": {"emoji": "⚠️"},
                "color": "yellow",
            },
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "字段化成功要求: 请在 Notion 页面设置匹配字段(时间/分支/commit/run 目录/任务责任/本次任务等), "
                            "或将此页设置为任务数据库后续追加子页面。"
                        },
                    }
                ],
                "icon": {"emoji": "🧭"},
                "color": "blue",
            },
        },
    ]
    payload = {"children": children}
    req = Request(
        url=f"https://api.notion.com/v1/blocks/{page_id}/children",
        data=json.dumps(payload).encode("utf-8"),
        method="PATCH",
        headers=_notion_headers(api_key),
    )
    try:
        with urlopen(req, timeout=8) as response:
            response.read()
        return {
            "status": "ok",
            "mode": "fallback",
            "page": page_id,
            "status_code": 200,
        }
    except HTTPError as exc:
        return {"status": "error", "reason": f"notion_http_{exc.code}"}
    except (URLError, OSError, ValueError) as exc:
        return {"status": "error", "reason": str(exc)}


def _append_notion_callout(
    *,
    api_key: str,
    page_id: str,
    content: str,
    icon: str = "🧭",
    color: str = "blue",
) -> bool:
    """Append a tiny status callout block to a page.

    This is best-effort; sync status is still determined by the primary
    write path, so failures to append the marker do not fail the whole
    sync run.
    """
    payload = {
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": content[:2000]}}],
                    "icon": {"emoji": icon},
                    "color": color,
                },
            }
        ]
    }
    req = Request(
        url=f"https://api.notion.com/v1/blocks/{page_id}/children",
        data=json.dumps(payload).encode("utf-8"),
        method="PATCH",
        headers=_notion_headers(api_key),
    )
    try:
        with urlopen(req, timeout=8) as response:
            response.read()
        return True
    except (HTTPError, URLError, OSError, ValueError):
        return False


def _append_notion_page_fields(
    *,
    api_key: str,
    page_id: str,
    snapshot: dict[str, Any],
    local_status_path: Path,
) -> dict[str, Any]:
    try:
        page = _notion_api_request("GET", f"/pages/{page_id}", api_key=api_key)
    except (HTTPError, URLError, OSError, ValueError):
        return {"status": "unavailable", "reason": "notion_fetch_page_failed"}
    if not isinstance(page, dict):
        return {"status": "unavailable", "reason": "notion_fetch_page_failed"}

    properties = page.get("properties")
    if not isinstance(properties, dict):
        return {"status": "unavailable", "reason": "page_has_no_properties"}

    rows = _notion_field_rows(snapshot, local_status_path)
    payload = _notion_property_payload(properties_schema=properties, rows=rows)
    if not payload:
        parent = page.get("parent")
        property_types = {
            prop.get("type") for prop in properties.values() if isinstance(prop, dict)
        }
        if (
            isinstance(parent, dict)
            and parent.get("type") == "workspace"
            and property_types <= {"title"}
        ):
            return {"status": "unavailable", "reason": "standalone_page_only_title_property"}
        return {"status": "unavailable", "reason": "no_matching_notion_fields"}

    req = Request(
        url=f"https://api.notion.com/v1/pages/{page_id}",
        data=json.dumps({"properties": payload}).encode("utf-8"),
        method="PATCH",
        headers=_notion_headers(api_key),
    )
    try:
        with urlopen(req, timeout=8) as response:
            response.read()
        return {"status": "ok", "mode": "fieldized", "page": page_id}
    except HTTPError as exc:
        return {"status": "error", "reason": f"notion_http_{exc.code}"}
    except (URLError, OSError, ValueError) as exc:
        return {"status": "error", "reason": str(exc)}


def _append_notion_child_database_row(
    *,
    api_key: str,
    page_id: str,
    snapshot: dict[str, Any],
    local_status_path: Path,
) -> dict[str, Any]:
    try:
        children = _notion_api_request(
            "GET",
            f"/blocks/{page_id}/children?page_size=100",
            api_key=api_key,
        )
    except (HTTPError, URLError, OSError, ValueError):
        return {"status": "unavailable", "reason": "notion_fetch_children_failed"}

    if not isinstance(children, dict):
        return {"status": "unavailable", "reason": "notion_children_shape_invalid"}

    db_candidates: list[tuple[str, dict[str, Any], int]] = []
    for child in children.get("results", []) or []:
        if not isinstance(child, dict) or child.get("type") != "child_database":
            continue
        db_id = child.get("id")
        if not isinstance(db_id, str):
            continue
        try:
            db_meta = _notion_api_request("GET", f"/databases/{db_id}", api_key=api_key)
        except (HTTPError, URLError, OSError, ValueError):
            continue
        if not isinstance(db_meta, dict):
            continue
        props = db_meta.get("properties")
        if not isinstance(props, dict):
            continue

        score = 0
        has_title = False
        for key, prop in props.items():
            if not isinstance(prop, dict):
                continue
            ptype = prop.get("type")
            if ptype == "title":
                score += 3
                has_title = True
            elif key in {
                "Task",
                "Session",
                "任务",
                "Summary",
                "摘要",
                "Status",
                "Last Review",
                "Last Run",
                "Owner Model",
                "Priority",
                "Phase",
                "Notes",
                "任务摘要",
            }:
                score += 1
        if has_title:
            db_candidates.append((db_id, props, score))

    if not db_candidates:
        return {"status": "unavailable", "reason": "page_has_no_child_databases"}

    db_id, properties, _ = sorted(db_candidates, key=lambda item: item[2], reverse=True)[0]
    payload = _notion_db_payload(properties, snapshot, local_status_path)
    if not payload:
        return {"status": "unavailable", "reason": "database_field_map_empty"}

    create_payload = {
        "parent": {"database_id": db_id},
        "properties": payload,
    }
    try:
        _notion_api_request("POST", "/pages", api_key=api_key, payload=create_payload)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        return {"status": "error", "reason": f"notion_db_update_failed: {exc}"}
    return {"status": "ok", "mode": "child_database_row", "database": db_id}


def _notion_db_payload(
    properties_schema: dict[str, Any],
    snapshot: dict[str, Any],
    local_status_path: Path,
) -> dict[str, Any]:
    git = snapshot["git"]
    run = snapshot["run"]
    commit = git.get("commit") or {}
    ts = snapshot.get("generated_at", "")
    task_label = "ArchReview-KG 控制同步"
    short_sha = commit.get("short_sha", "")
    if short_sha:
        task_label = f"{task_label} ({short_sha})"
    summary = (
        f"任务={TASK_MARK} | 分支={git.get('branch', 'unknown')} | "
        f"commit={short_sha} | 工作区脏={'是' if git.get('working_tree_dirty') else '否'} | "
        f"run_dir={snapshot.get('run_dir', '')} | local_status={local_status_path.as_posix()} | "
        f"artifacts={', '.join(run.get('artifacts') or [])}"
    )

    payload: dict[str, Any] = {}
    for prop_name, prop in properties_schema.items():
        if not isinstance(prop, dict):
            continue
        prop_type = prop.get("type")
        if prop_type == "title":
            payload[prop_name] = {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": task_label[:150]},
                    }
                ]
            }
        elif prop_type == "rich_text":
            payload[prop_name] = {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": summary[:2000]},
                    }
                ]
            }
        elif prop_type == "number":
            payload[prop_name] = {"number": float(run.get("file_count", 0))}
        elif prop_type == "checkbox":
            payload[prop_name] = {"checkbox": bool(run.get("exists", False))}
        elif prop_type == "date":
            payload[prop_name] = {"date": {"start": ts[:10] if ts else None}}
        elif prop_type in {"select", "status"}:
            choices = prop.get(prop_type, {})
            options = (choices.get("options") or []) if isinstance(choices, dict) else []
            option_name: str | None = None
            if options:
                first = options[0]
                if isinstance(first, dict):
                    option_name = first.get("name")
            if option_name is not None:
                payload[prop_name] = {prop_type: {"name": option_name}}
        elif prop_type in {"multi_select"}:
            choices = prop.get("multi_select", {})
            options = (choices.get("options") or []) if isinstance(choices, dict) else []
            values = []
            for option in options[:1]:
                if isinstance(option, dict):
                    values.append({"name": option.get("name")})
            if values:
                payload[prop_name] = {"multi_select": values}
        elif prop_type == "unique_id":
            continue
        elif prop_type in {
            "files",
            "formula",
            "relation",
            "rollup",
            "created_time",
            "created_by",
            "last_edited_time",
            "last_edited_by",
            "people",
            "url",
        }:
            continue

    return payload


def _fieldized_fallback_table(
    snapshot: dict[str, Any],
    local_status_path: Path,
) -> list[dict[str, Any]]:
    payload = _notion_field_payload(snapshot, local_status_path)
    children = payload.get("children")
    if isinstance(children, list):
        return children
    return []


def _notion_api_request(
    method: str,
    path: str,
    *,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 8,
) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = Request(
        url=f"https://api.notion.com/v1{path}",
        data=data,
        method=method,
        headers=_notion_headers(api_key),
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _notion_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
        "Accept": "application/json",
}


def _notion_field_rows(snapshot: dict[str, Any], local_status_path: Path) -> list[tuple[str, str]]:
    git = snapshot["git"]
    run = snapshot["run"]
    ts = snapshot.get("generated_at", "")
    commit = git.get("commit") or {}
    fields = [
        ("时间", ts),
        ("项目", "ArchReview-KG"),
        ("分支", str(git.get("branch", "")) or "unknown"),
        ("commit", f"{commit.get('short_sha', '')} - {commit.get('subject', '')}".strip(" -")),
        ("工作区脏", "是" if git.get("working_tree_dirty") else "否"),
        ("run 目录", str(snapshot.get("run_dir", "")) if snapshot.get("run_dir") else ""),
        ("run 目录状态", "有" if run.get("exists") else "无"),
        ("run 产物", ", ".join(run.get("artifacts") or [])),
        ("任务责任", "Codex 全权负责"),
        ("本次任务", "Notion 页内字段化写入 + 控制中枢同步能力验证"),
        ("本地快照文件", local_status_path.as_posix()),
    ]
    return [(k, str(v) if v is not None else "") for k, v in fields]


def _notion_property_payload(
    *,
    properties_schema: dict[str, Any],
    rows: list[tuple[str, str]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in rows:
        prop = properties_schema.get(key)
        if not isinstance(prop, dict):
            continue
        prop_type = prop.get("type")
        if prop_type == "title":
            payload[key] = {"title": [{"type": "text", "text": {"content": value}}]}
        elif prop_type == "rich_text":
            payload[key] = {"rich_text": [{"type": "text", "text": {"content": value}}]}
        elif prop_type == "checkbox":
            payload[key] = {"checkbox": value in {"true", "1", "是", "yes", "y", "on"}}
        elif prop_type == "number":
            try:
                payload[key] = {"number": float(value)}
            except (TypeError, ValueError):
                continue
        elif prop_type == "date":
            payload[key] = {"date": {"start": value[:10] if value else None}}
        elif prop_type == "url":
            payload[key] = {"url": value}
        elif prop_type == "email":
            payload[key] = {"email": value}
        elif prop_type == "phone_number":
            payload[key] = {"phone_number": value}
        elif prop_type in {"select", "status"}:
            choices_key = "select" if prop_type == "select" else "status"
            choices = prop.get(choices_key)
            options = (choices.get("options") or []) if isinstance(choices, dict) else []
            option_names = {opt.get("name") for opt in options if isinstance(opt, dict)}
            if value in option_names:
                payload[key] = {prop_type: {"name": value}}
            elif options:
                # Do not silently create non-existing option names.
                payload[key] = {prop_type: {"name": options[0].get("name")}}
            else:
                continue
        else:
            # Fallback: unsupported fields are safer to skip than to fail hard.
            continue
    return payload


def _notion_note_text(snapshot: dict[str, Any], local_status_path: Path) -> str:
    git = snapshot["git"]
    branch = git.get("branch", "unknown")
    sha = (git.get("commit") or {}).get("short_sha") or "unknown"
    ts = snapshot.get("generated_at", "")
    artifacts = ", ".join((snapshot.get("run", {}).get("artifacts") or []) or ["none"])
    return (
        f"[{ts}] ArchReview-KG control sync: "
        f"branch={branch}, commit={sha}, dirty={git.get('working_tree_dirty')}, "
        f"artifacts=[{artifacts}], detail_file={local_status_path.name}"
    )


def _notion_field_payload(snapshot: dict[str, Any], local_status_path: Path) -> dict[str, Any]:
    git = snapshot["git"]
    run = snapshot["run"]
    ts = snapshot.get("generated_at", "")
    commit = git.get("commit") or {}
    fields = [
        ("时间", ts),
        ("项目", "ArchReview-KG"),
        ("分支", str(git.get("branch", "")) or "unknown"),
        ("commit", f"{commit.get('short_sha', '')} - {commit.get('subject', '')}".strip(" -")),
        ("工作区脏", "是" if git.get("working_tree_dirty") else "否"),
        ("run 目录", str(snapshot.get("run_dir", "")) if snapshot.get("run_dir") else ""),
        ("run 目录状态", "有" if run.get("exists") else "无"),
        ("run 产物", ", ".join(run.get("artifacts") or [])),
        ("GitHub", "已尝试"),
        ("任务责任", "Codex 全权负责"),
        ("本次任务", "Notion 页内字段化写入 + 控制中枢同步能力验证"),
        ("本地快照文件", local_status_path.as_posix()),
    ]
    rows = [
        [
            [{"type": "text", "text": {"content": k}}],
            [{"type": "text", "text": {"content": v or "—"}}],
        ]
        for k, v in fields
    ]
    table_blocks = [
        {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": 2,
                "has_column_header": True,
                "children": [
                    {
                        "type": "table_row",
                        "table_row": {
                            "cells": row
                        }
                    }
                    for row in rows
                ],
            },
        },
    ]
    return {
        "children": table_blocks,
    }


def _normalize_children(children: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for child in children:
        if child.get("type") == "table":
            table = child.get("table") or {}
            if "children" not in table:
                table["children"] = []
            if "table_width" not in table:
                table["table_width"] = 2
            if "has_column_header" not in table:
                table["has_column_header"] = True
            out.append(child)
            continue
        out.append(child)
    return out


def _gh_api(path: str) -> dict[str, Any] | list[dict[str, Any]] | None:
    data, _ = _gh_api_with_error(path)
    return data


def _gh_api_with_error(
    path: str,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, str | None]:
    if shutil.which("gh") is None:
        return _github_rest_api_with_error(path)

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token

    cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json", path]
    result, detail = _run_command_with_detail(cmd, cwd=Path("."), env=env)
    if result is None:
        return None, detail
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        return None, "json_decode_error"
    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed), None
    if isinstance(parsed, list):
        out: list[dict[str, Any]] = []
        for item in parsed:
            if isinstance(item, dict):
                out.append(cast(dict[str, Any], item))
        return out, None
    return None, "unsupported_response_shape"


def _github_rest_api_with_error(
    path: str,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, str | None]:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "archreview-kg-control-sync",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url=f"https://api.github.com{path}", headers=headers)
    try:
        with urlopen(req, timeout=8) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return None, f"github_http_{exc.code}: {detail}"
    except (URLError, OSError, ValueError) as exc:
        return None, str(exc)

    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed), None
    if isinstance(parsed, list):
        out: list[dict[str, Any]] = []
        for item in parsed:
            if isinstance(item, dict):
                out.append(cast(dict[str, Any], item))
        return out, None
    return None, "unsupported_response_shape"


def _safe_git(args: list[str], repo_root: Path) -> str:
    result = _run_command(["git", *args], cwd=repo_root)
    if result is None:
        return ""
    return result.strip()


def _calc_ahead_behind(branch: str, remote_origin: str, repo_root: Path) -> dict[str, Any]:
    if not branch or not remote_origin:
        return {"status": "unavailable"}
    local_ref = branch
    remote_ref = f"origin/{branch}"
    # If this is a non-tracked branch, return context-rich neutral status.
    if not (repo_root / ".git").exists():
        return {"status": "unavailable"}
    upstream = _safe_git(["rev-parse", "@{u}"], repo_root)
    if not upstream:
        return {"status": "untracked_from_upstream"}
    try:
        counts = _run_command(
            ["git", "rev-list", "--left-right", "--count", f"{remote_ref}...{local_ref}"],
            cwd=repo_root,
        )
    except Exception:
        counts = None
    if not counts:
        return {"status": "unavailable", "reason": "rev-list_failed"}
    left, right = [x.strip() for x in counts.split("\t") if x.strip()]
    return {
        "status": "ok",
        "behind": int(left),
        "ahead": int(right),
    }


def _parse_github_repo(remote: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
    if not m:
        return None
    return m.group("owner"), m.group("repo")


def _run_command(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str | None:
    result, _ = _run_command_with_detail(cmd, cwd=cwd, env=env)
    return result


def _run_command_with_detail(
    cmd: list[str], cwd: Path, env: dict[str, str] | None = None
) -> tuple[str | None, str | None]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        return None, err
    return proc.stdout.strip(), None

def _normalize_notion_page_id(
    page_id: str | None,
    *,
    api_key: str | None = None,
) -> str | None:
    if not page_id:
        return None

    raw = page_id.strip()
    if "//" in raw:
        raw = raw.split("?", 1)[0].split("#", 1)[0].rstrip("/")
        raw = raw.split("/")[-1]

    if not raw:
        return None

    if _UUID_WITH_DASHES.fullmatch(raw):
        return raw

    tail_match = re.findall(r"([0-9a-fA-F]{32,33})", raw)
    if not tail_match:
        return None
    hex_id = tail_match[-1]
    if _HEX_ONLY.fullmatch(hex_id) is None:
        return None

    candidates: list[str] = []
    if len(hex_id) == 32:
        candidates.append(hex_id)
    if len(hex_id) == 33:
        # User-provided links from Notion sometimes carry one trailing extra char.
        # 优先尝试去尾一位, 若仍不匹配再尝试逐位回删.
        candidates.append(hex_id[:-1])
        candidates.extend(hex_id[:i] + hex_id[i + 1 :] for i in range(len(hex_id) - 1))

    for candidate in candidates:
        if len(candidate) != 32 or not _HEX_ONLY.fullmatch(candidate):
            continue
        dashed = f"{candidate[0:8]}-{candidate[8:12]}-{candidate[12:16]}-{candidate[16:20]}-{candidate[20:32]}"
        if not _is_valid_notion_uuid(dashed):
            continue
        if api_key and not _notion_page_exists(dashed, api_key):
            continue
        return dashed

    if api_key is None:
        for candidate in candidates:
            if len(candidate) != 32 or not _HEX_ONLY.fullmatch(candidate):
                continue
            dashed = f"{candidate[0:8]}-{candidate[8:12]}-{candidate[12:16]}-{candidate[16:20]}-{candidate[20:32]}"
            if _is_valid_notion_uuid(dashed):
                return dashed

        return None

    return None


def _notion_page_exists(page_id: str, api_key: str) -> bool:
    try:
        _notion_api_request("GET", f"/pages/{page_id}", api_key=api_key)
        return True
    except (HTTPError, URLError, OSError, ValueError):
        return False


def _is_valid_notion_uuid(value: str) -> bool:
    return bool(_UUID_WITH_DASHES.fullmatch(value))
