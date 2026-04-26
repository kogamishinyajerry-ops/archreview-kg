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


def test_room_schedule_requires_project_meta(tmp_path: Path, sample_pdf: Path) -> None:
    """Codex P18-B R1 P0: --room-schedule without --project-meta must
    error rather than silently apply (no project_id to cross-check)."""
    schedule = tmp_path / "schedule.yaml"
    schedule.write_text(
        "project_id: WHATEVER\nentries:\n  - label: bedroom\n    net_height_m: 2.30\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "review",
            str(sample_pdf),
            "-o",
            str(tmp_path / "out"),
            "--room-schedule",
            str(schedule),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "Invalid value for --room-schedule" in result.output
    assert "requires --project-meta" in result.output


def test_room_schedule_project_id_must_match_meta(tmp_path: Path, sample_pdf: Path) -> None:
    """Schedule whose project_id differs from ProjectMeta must be rejected."""
    meta = tmp_path / "meta.yaml"
    meta.write_text(
        "project_id: A\nbuilding_type: residential\nheight_class: 多层\n",
        encoding="utf-8",
    )
    schedule = tmp_path / "schedule.yaml"
    schedule.write_text(
        "project_id: B\nentries:\n  - label: bedroom\n    net_height_m: 2.30\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "review",
            str(sample_pdf),
            "-o",
            str(tmp_path / "out"),
            "--project-meta",
            str(meta),
            "--room-schedule",
            str(schedule),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    # Rich wraps long error messages; check a fragment that survives line breaks.
    assert "Invalid value for --room-schedule" in result.output


def test_stair_schedule_rejects_out_of_range_page_index(
    tmp_path: Path, sample_pdf: Path
) -> None:
    """Codex P18-C R1 P0: bad page_index errors at apply time, not in
    annotator with IndexError."""
    meta = tmp_path / "meta.yaml"
    meta.write_text(
        "project_id: A\nbuilding_type: residential\nheight_class: 多层\n",
        encoding="utf-8",
    )
    schedule = tmp_path / "stairs.yaml"
    schedule.write_text(
        "project_id: A\nentries:\n  - stair_id: s1\n    page_index: 99\n    tread_width_m: 0.26\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "review",
            str(sample_pdf),
            "-o",
            str(tmp_path / "out"),
            "--project-meta",
            str(meta),
            "--stair-schedule",
            str(schedule),
        ],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "Invalid value for --stair-schedule" in result.output
