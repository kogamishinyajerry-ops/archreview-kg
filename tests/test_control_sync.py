from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import archkg.control_sync as control_sync_module
from archkg import control_sync
from archkg.cli.main import app


def test_run_snapshot_includes_sheet_classification_artifact(tmp_path: Path) -> None:
    (tmp_path / "sheet_classification.json").write_text(
        '{"schema_version":"sheet_classification.v1"}',
        encoding="utf-8",
    )
    (tmp_path / "sheet_routing.json").write_text(
        '{"schema_version":"sheet_routing.v1"}',
        encoding="utf-8",
    )
    (tmp_path / "sheet_graphs.json").write_text(
        '{"schema_version":"sheet_graphs.v1"}',
        encoding="utf-8",
    )
    (tmp_path / "sheet_issues.json").write_text(
        '{"schema_version":"sheet_issues.v1"}',
        encoding="utf-8",
    )
    (tmp_path / "scratch.txt").write_text("ignore me", encoding="utf-8")

    snapshot = control_sync._collect_run_snapshot(tmp_path)

    assert snapshot["exists"] is True
    assert "sheet_classification.json" in snapshot["artifacts"]
    assert "sheet_routing.json" in snapshot["artifacts"]
    assert "sheet_graphs.json" in snapshot["artifacts"]
    assert "sheet_issues.json" in snapshot["artifacts"]
    assert "scratch.txt" not in snapshot["artifacts"]


def test_github_snapshot_falls_back_to_rest_api_when_gh_cli_missing(monkeypatch) -> None:
    monkeypatch.setattr(control_sync.shutil, "which", lambda _name: None)

    def fake_github_api(path: str):
        if path == "/repos/kogamishinyajerry-ops/archreview-kg":
            return {
                "full_name": "kogamishinyajerry-ops/archreview-kg",
                "default_branch": "main",
                "open_issues_count": 0,
                "forks_count": 0,
                "stargazers_count": 0,
            }, None
        if path == "/repos/kogamishinyajerry-ops/archreview-kg/pulls?state=open&per_page=20":
            return [], None
        raise AssertionError(path)

    monkeypatch.setattr(control_sync, "_github_rest_api_with_error", fake_github_api)

    snapshot = control_sync._collect_github_snapshot(
        {"remote_origin": "https://github.com/kogamishinyajerry-ops/archreview-kg.git"}
    )

    assert snapshot["status"] == "ok"
    assert snapshot["repo"] == "kogamishinyajerry-ops/archreview-kg"
    assert snapshot["default_branch"] == "main"


def test_child_database_fallback_exposes_page_field_reason(monkeypatch, tmp_path: Path) -> None:
    snapshot = {
        "generated_at": "2026-04-27T12:00:00+00:00",
        "git": {
            "branch": "main",
            "working_tree_dirty": True,
            "commit": {"short_sha": "465b61a", "subject": "subject"},
        },
        "run": {"exists": True, "file_count": 1, "artifacts": []},
        "run_dir": str(tmp_path),
    }

    def fake_page_fields(**_kwargs):
        return {
            "status": "unavailable",
            "reason": "standalone_page_only_title_property",
        }

    def fake_child_database(**_kwargs):
        return {
            "status": "ok",
            "mode": "child_database_row",
            "database": "tasks-db",
        }

    monkeypatch.setattr(control_sync, "_append_notion_page_fields", fake_page_fields)
    monkeypatch.setattr(control_sync, "_append_notion_child_database_row", fake_child_database)
    monkeypatch.setattr(control_sync, "_append_notion_callout", lambda **_kwargs: True)

    result = control_sync._append_notion_sync_note(
        api_key="secret",
        page_id="page-id",
        snapshot=snapshot,
        local_status_path=tmp_path / "control_sync.json",
    )

    assert result["status"] == "ok"
    assert result["mode"] == "child_database_row"
    assert result["fallback_reason"] == "standalone_page_only_title_property"


def test_cli_prints_notion_fallback_reason(monkeypatch, tmp_path: Path) -> None:
    def fake_sync_control_state(**_kwargs):
        return {
            "local_status_file": str(tmp_path / "control_sync.json"),
            "snapshot": {},
            "sync": {
                "github": None,
                "notion": {
                    "status": "ok",
                    "mode": "child_database_row",
                    "database": "tasks-db",
                    "fallback_reason": "standalone_page_only_title_property",
                },
            },
        }

    monkeypatch.setattr(control_sync_module, "sync_control_state", fake_sync_control_state)

    result = CliRunner().invoke(
        app,
        [
            "control-sync",
            "--run-dir",
            str(tmp_path),
            "--no-github",
            "--notion",
            "--notion-page-id",
            "34dc68942bed81ca843ec26cbffcb6b9b",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "notion: ok (child_database_row; fallback=standalone_page_only_title_property)" in result.output
