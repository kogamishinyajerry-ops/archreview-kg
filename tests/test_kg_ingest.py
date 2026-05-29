"""Tests for archkg.kg.ingest (M5.A.2 — run-dir ingestion into KG)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archkg.kg import (
    INGESTABLE_ARTIFACTS,
    KGStore,
    has_ingestable_artifact,
    ingest_run,
)
from archkg.kg.ingest import _entities_from_graph

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ingestable_artifacts_list_stable() -> None:
    assert "issues.json" in INGESTABLE_ARTIFACTS
    assert "entity_graph.json" in INGESTABLE_ARTIFACTS
    assert "drawing_understanding.json" in INGESTABLE_ARTIFACTS
    assert "review_state.json" in INGESTABLE_ARTIFACTS


def test_has_ingestable_artifact_true_for_real_benchmark() -> None:
    p = REPO_ROOT / "samples" / "understanding_benchmarks" / "real" / "medfield_a1_first_floor_run"
    assert has_ingestable_artifact(p)


def test_has_ingestable_artifact_false_for_empty_dir(tmp_path: Path) -> None:
    assert has_ingestable_artifact(tmp_path) is False


def _write_minimal_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "entity_graph.json").write_text(
        json.dumps(
            {
                "source_pdf": "/abs/path/to/example.pdf",
                "page_index": 0,
                "rooms": [
                    {
                        "id": "room-aaa",
                        "type": "Room",
                        "bbox": [0, 0, 100, 100],
                        "confidence": 0.9,
                        "properties": {"net_height_m": 2.5},
                    }
                ],
                "doors": [
                    {
                        "id": "door-bbb",
                        "type": "Door",
                        "bbox": [50, 100, 90, 100],
                        "confidence": 0.5,
                        "width_m": 0.8,
                        "properties": {},
                    }
                ],
                "corridors": [],
                "stairs": [],
                "dimensions": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "issues.json").write_text(
        json.dumps(
            [
                {
                    "issue_id": "ISS-1",
                    "rule_card_id": "RC-DOOR-WIDTH",
                    "standard_clause_id": "GB50096-5.1.1",
                    "entity_ids": ["door-bbb"],
                    "bbox": [50, 100, 90, 100],
                    "page_index": 0,
                    "severity": "error",
                    "message": "Door width 0.80 m below threshold.",
                    "evidence": {"measured_value": 0.8, "threshold_value": 0.9},
                }
            ]
        ),
        encoding="utf-8",
    )


def test_ingest_minimal_run_populates_kg(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    run_dir = tmp_path / "demo_run"
    _write_minimal_run(run_dir)
    with KGStore(db) as store:
        result = ingest_run(store, run_dir=run_dir, project_slug="demo")
        assert result.project_id > 0
        assert result.drawing_id is not None
        assert result.run_id > 0
        assert result.counts["entities"] == 2
        assert result.counts["issues"] == 1
        assert result.counts["sheets"] == 1
        assert result.counts["rules_added"] == 1
        assert result.counts["clauses_added"] == 1


def test_ingest_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    run_dir = tmp_path / "demo_run"
    _write_minimal_run(run_dir)
    with KGStore(db) as store:
        r1 = ingest_run(store, run_dir=run_dir, project_slug="demo")
        r2 = ingest_run(store, run_dir=run_dir, project_slug="demo")
        assert r1.project_id == r2.project_id
        assert r1.drawing_id == r2.drawing_id
        assert r1.run_id == r2.run_id
        # Issue count must not grow on re-ingest (deletes by source_issue_id first)
        cur = store._conn.execute("SELECT COUNT(*) AS c FROM issue WHERE run_id = ?", (r1.run_id,))
        assert cur.fetchone()["c"] == 1
        # Rule and clause are global; on re-ingest no new rows added
        assert r2.counts["rules_added"] == 0
        assert r2.counts["clauses_added"] == 0


def test_ingest_real_benchmark_run(tmp_path: Path) -> None:
    src = REPO_ROOT / "samples" / "understanding_benchmarks" / "real" / "medfield_a1_first_floor_run"
    db = tmp_path / "kg.db"
    with KGStore(db) as store:
        result = ingest_run(store, run_dir=src, project_slug="medfield-a1")
        assert result.run_id > 0
        # Real benchmark may or may not have issues; at minimum the drawing
        # and run row must exist.
        cur = store._conn.execute("SELECT COUNT(*) AS c FROM drawing")
        assert cur.fetchone()["c"] == 1
        cur = store._conn.execute("SELECT COUNT(*) AS c FROM run")
        assert cur.fetchone()["c"] == 1


def test_ingest_missing_artifact_raises(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    empty_run = tmp_path / "empty_run"
    empty_run.mkdir()
    with KGStore(db) as store, pytest.raises(FileNotFoundError):
        ingest_run(store, run_dir=empty_run, project_slug="x")


def test_entities_from_graph_flattens_all_types() -> None:
    graph = {
        "page_index": 2,
        "rooms": [{"id": "r1", "bbox": [0, 0, 1, 1], "confidence": 0.9}],
        "doors": [{"id": "d1", "type": "Door", "bbox": [0, 0, 1, 1]}],
        "corridors": [{"id": "c1", "bbox": [0, 0, 1, 1]}],
        "stairs": [{"id": "s1", "bbox": [0, 0, 1, 1]}],
        "dimensions": [{"id": "dim1", "bbox": [0, 0, 1, 1]}],
    }
    flat = _entities_from_graph(graph)
    assert {e["entity_type"] for e in flat} == {"Room", "Door", "Corridor", "Stair", "Dimension"}
    assert all(e["page_index"] == 2 for e in flat)


def test_review_state_applied_to_issues(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    run_dir = tmp_path / "demo_run"
    _write_minimal_run(run_dir)
    (run_dir / "review_state.json").write_text(
        json.dumps(
            {
                "issues": {
                    "ISS-1": {"status": "confirmed"},
                }
            }
        ),
        encoding="utf-8",
    )
    with KGStore(db) as store:
        ingest_run(store, run_dir=run_dir, project_slug="demo")
        cur = store._conn.execute("SELECT status FROM issue WHERE source_issue_id = ?", ("ISS-1",))
        assert cur.fetchone()["status"] == "confirmed"


def test_count_runs_reflects_ingest(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    with KGStore(db) as store:
        assert store.count_runs() == 0
        for i in range(3):
            rd = tmp_path / f"run_{i}"
            _write_minimal_run(rd)
            ingest_run(store, run_dir=rd, project_slug=f"p{i}")
        assert store.count_runs() == 3
