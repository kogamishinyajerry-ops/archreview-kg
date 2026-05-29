"""Tests for archkg.kg.store (M5.A.1 — KGStore schema + health_check)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archkg.kg.store import (
    REQUIRED_TABLES,
    SCHEMA_VERSION,
    KGStore,
    KGStoreError,
    default_db_path,
)


def test_schema_version_pinned() -> None:
    assert SCHEMA_VERSION == "kg.v1"


def test_required_tables_complete() -> None:
    expected = {
        "schema_version",
        "project",
        "drawing",
        "sheet",
        "run",
        "rule",
        "clause",
        "entity",
        "issue",
        "reviewer",
        "feedback_event",
        "edge",
    }
    assert set(REQUIRED_TABLES) == expected


def test_init_creates_db_with_full_schema(tmp_path: Path) -> None:
    db = tmp_path / ".archkg" / "kg.db"
    assert not db.exists()
    store = KGStore(db)
    try:
        assert db.exists()
        tables = store.list_tables()
        for t in REQUIRED_TABLES:
            assert t in tables, f"missing required table: {t}"
        assert store.schema_version() == SCHEMA_VERSION
    finally:
        store.close()


def test_health_check_reports_required_tables_and_zero_counts(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    with KGStore(db) as store:
        report = store.health_check()
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["required_tables_present"] is True
    # schema_version row is inserted at init; data tables should be empty.
    assert report["counts"]["schema_version"] == 1
    for t in REQUIRED_TABLES:
        if t == "schema_version":
            continue
        assert report["counts"][t] == 0, f"{t} should be empty on init"
    assert report["query_p95_ms"] >= 0
    # On a fresh empty DB, queries should be fast (<<50ms on any sane disk)
    assert report["query_p95_ms"] < 50.0
    assert report["db_path"] == str(db)


def test_create_false_errors_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "absent.db"
    with pytest.raises(KGStoreError):
        KGStore(missing, create=False)


def test_existing_db_does_not_duplicate_schema_version_row(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    KGStore(db).close()
    KGStore(db).close()
    KGStore(db).close()
    with KGStore(db) as store:
        cur = store._conn.execute(
            "SELECT COUNT(*) AS c FROM schema_version WHERE version = ?",
            (SCHEMA_VERSION,),
        )
        row = cur.fetchone()
        assert row["c"] == 1


def test_upsert_project_idempotent(tmp_path: Path) -> None:
    with KGStore(tmp_path / "kg.db") as store:
        id1 = store.upsert_project("medfield", name="Medfield Plan Set")
        id2 = store.upsert_project("medfield", name="Medfield Plan Set (renamed)")
        assert id1 == id2
        cur = store._conn.execute("SELECT name FROM project WHERE id = ?", (id1,))
        assert cur.fetchone()["name"] == "Medfield Plan Set (renamed)"


def test_upsert_drawing_unique_per_project_path(tmp_path: Path) -> None:
    with KGStore(tmp_path / "kg.db") as store:
        proj = store.upsert_project("p1")
        d1 = store.upsert_drawing(project_id=proj, source_path="a.pdf", page_count=3)
        d2 = store.upsert_drawing(project_id=proj, source_path="a.pdf", page_count=5)
        d3 = store.upsert_drawing(project_id=proj, source_path="b.pdf", page_count=1)
        assert d1 == d2
        assert d1 != d3
        cur = store._conn.execute("SELECT page_count FROM drawing WHERE id = ?", (d1,))
        assert cur.fetchone()["page_count"] == 5


def test_upsert_run_unique_per_project_dir(tmp_path: Path) -> None:
    with KGStore(tmp_path / "kg.db") as store:
        proj = store.upsert_project("p1")
        draw = store.upsert_drawing(project_id=proj, source_path="a.pdf")
        r1 = store.upsert_run(
            project_id=proj, drawing_id=draw, run_dir="out/run-1", artifacts=["issues.json"]
        )
        r2 = store.upsert_run(
            project_id=proj,
            drawing_id=draw,
            run_dir="out/run-1",
            artifacts=["issues.json", "entity_graph.json"],
        )
        r3 = store.upsert_run(project_id=proj, drawing_id=draw, run_dir="out/run-2")
        assert r1 == r2
        assert r1 != r3
        artifacts_row = store._conn.execute(
            "SELECT artifacts_json FROM run WHERE id = ?", (r1,)
        ).fetchone()
        loaded = json.loads(artifacts_row["artifacts_json"])
        assert loaded == ["entity_graph.json", "issues.json"]


def test_count_runs(tmp_path: Path) -> None:
    with KGStore(tmp_path / "kg.db") as store:
        assert store.count_runs() == 0
        proj = store.upsert_project("p1")
        store.upsert_run(project_id=proj, drawing_id=None, run_dir="r1")
        store.upsert_run(project_id=proj, drawing_id=None, run_dir="r2")
        store.upsert_run(project_id=proj, drawing_id=None, run_dir="r2")  # upsert no-op
        assert store.count_runs() == 2


def test_foreign_keys_enforced(tmp_path: Path) -> None:
    import sqlite3

    with KGStore(tmp_path / "kg.db") as store:
        with pytest.raises(sqlite3.IntegrityError):
            # Inserting a drawing pointing at a non-existent project should fail
            store._conn.execute(
                "INSERT INTO drawing(project_id, source_path, created_at) VALUES (?, ?, ?)",
                (999, "a.pdf", "2026-01-01T00:00:00Z"),
            )


def test_default_db_path_uses_repo_when_provided(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    p = default_db_path(repo)
    assert p == repo / ".archkg" / "kg.db"


def test_default_db_path_falls_back_to_home() -> None:
    p = default_db_path(None)
    assert p == Path.home() / ".archkg" / "kg.db"


def test_wal_mode_enabled(tmp_path: Path) -> None:
    with KGStore(tmp_path / "kg.db") as store:
        cur = store._conn.execute("PRAGMA journal_mode")
        assert cur.fetchone()[0].lower() == "wal"
