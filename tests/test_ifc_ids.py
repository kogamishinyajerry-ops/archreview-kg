from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from archkg.cli.main import app


def _write_fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    ifc_path = tmp_path / "model.ifc"
    ids_path = tmp_path / "requirements.ids"
    ifc_path.write_text(
        "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n",
        encoding="utf-8",
    )
    ids_path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?><ids><specification name='demo'/></ids>\n",
        encoding="utf-8",
    )
    return ifc_path, ids_path


def test_ifc_validate_cli_degrades_when_optional_dependency_missing(
    tmp_path: Path,
) -> None:
    ifc_path, ids_path = _write_fixture_files(tmp_path)
    out_dir = tmp_path / "ifc-out"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "validate",
            "--ifc",
            str(ifc_path),
            "--ids",
            str(ids_path),
            "-o",
            str(out_dir),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "optional dependency" in result.output
    assert "ifcopenshell" in result.output
    assert "ifctester" in result.output
    assert not (out_dir / "issues.json").exists()


def test_ifc_validate_maps_fake_ids_failures_without_pdf_issue_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from archkg.ifc.ids_validator import validate_ifc_ids

    _install_fake_ifc_modules(monkeypatch)
    ifc_path, ids_path = _write_fixture_files(tmp_path)
    out_dir = tmp_path / "ifc-out"

    result = validate_ifc_ids(ifc_path=ifc_path, ids_path=ids_path, out_dir=out_dir)

    assert result.status == "failed"
    assert result.issue_count == 1
    assert (out_dir / "ids_report_raw.json").exists()
    assert (out_dir / "ifc_validation.json").exists()
    assert (out_dir / "ifc_issues.json").exists()
    assert not (out_dir / "issues.json").exists()

    issues = json.loads((out_dir / "ifc_issues.json").read_text(encoding="utf-8"))
    assert issues[0]["issue_id"] == "IFC-IDS-0001"
    assert issues[0]["source_ifc"] == str(ifc_path)
    assert issues[0]["source_ids"] == str(ids_path)
    assert issues[0]["requirement"] == "FireRating must exist"
    assert issues[0]["target_entity"] == "IfcDoor:0DOOR"
    assert issues[0]["actual_value"] == "missing"
    assert issues[0]["expected_value"] == "FireRating"

    summary = json.loads((out_dir / "ifc_validation.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == "ifc_ids_validation.v1"
    assert summary["status"] == "failed"
    assert summary["raw_report_path"] == str(out_dir / "ids_report_raw.json")


def test_ifc_validate_cli_with_fake_dependency_writes_separate_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ifc_modules(monkeypatch)
    ifc_path, ids_path = _write_fixture_files(tmp_path)
    out_dir = tmp_path / "ifc-out"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "validate",
            "--ifc",
            str(ifc_path),
            "--ids",
            str(ids_path),
            "-o",
            str(out_dir),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "ifc_validation.json" in result.output
    assert "ifc_issues.json" in result.output
    assert (out_dir / "ifc_issues.json").exists()
    assert not (out_dir / "issues.json").exists()


def _install_fake_ifc_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    ifcopenshell = types.ModuleType("ifcopenshell")
    ifctester = types.ModuleType("ifctester")
    ids_module = types.ModuleType("ifctester.ids")
    reporter_module = types.ModuleType("ifctester.reporter")

    class FakeIds:
        def __init__(self, path: str) -> None:
            self.path = path
            self.model: dict[str, str] | None = None

        def validate(self, model: dict[str, str]) -> None:
            self.model = model

    class FakeJsonReporter:
        def __init__(self, ids_spec: FakeIds) -> None:
            self.ids_spec = ids_spec

        def report(self) -> dict[str, Any]:
            return {
                "status": False,
                "specifications": [
                    {
                        "name": "Door requirements",
                        "requirements": [
                            {
                                "status": False,
                                "description": "FireRating must exist",
                                "expected": "FireRating",
                                "failed_entities": [
                                    {
                                        "global_id": "0DOOR",
                                        "type": "IfcDoor",
                                        "name": "Door A",
                                        "actual": "missing",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }

    def fake_open_ifc(path: str) -> dict[str, str]:
        return {"ifc": path}

    def fake_open_ids(path: str) -> FakeIds:
        return FakeIds(path)

    ifcopenshell.open = fake_open_ifc  # type: ignore[attr-defined]
    ids_module.open = fake_open_ids  # type: ignore[attr-defined]
    reporter_module.Json = FakeJsonReporter  # type: ignore[attr-defined]
    ifctester.ids = ids_module  # type: ignore[attr-defined]
    ifctester.reporter = reporter_module  # type: ignore[attr-defined]
    ifctester.__path__ = []  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "ifcopenshell", ifcopenshell)
    monkeypatch.setitem(sys.modules, "ifctester", ifctester)
    monkeypatch.setitem(sys.modules, "ifctester.ids", ids_module)
    monkeypatch.setitem(sys.modules, "ifctester.reporter", reporter_module)
