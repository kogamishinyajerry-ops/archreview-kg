"""End-to-end CLI tests for `archkg review --project-meta`.

The Phase 9 P2 nit (Codex review): malformed YAML or schema-violating YAML
must produce a concise typer.BadParameter error, not a full Python traceback.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app


def test_review_rejects_malformed_yaml(tmp_path: Path, sample_pdf: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("project_id: P\nbuilding_type: [oops\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["review", str(sample_pdf), "-o", str(tmp_path / "out"), "--project-meta", str(bad)],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "Invalid value for --project-meta" in result.output
    assert "not valid YAML" in result.output


def test_review_rejects_meta_missing_required_fields(tmp_path: Path, sample_pdf: Path) -> None:
    bad = tmp_path / "missing.yaml"
    bad.write_text(
        "project_id: P-X\n"  # missing building_type and height_class
        "project_name: 不完整\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["review", str(sample_pdf), "-o", str(tmp_path / "out"), "--project-meta", str(bad)],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "Invalid value for --project-meta" in result.output
    # Rich wraps "schema validation" across lines; check for the pydantic detail instead.
    assert "Field required" in result.output
