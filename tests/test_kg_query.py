"""Tests for archkg.kg.query (M5.C — query layer + canonical queries)."""

from __future__ import annotations

import json
from pathlib import Path

from archkg.kg import KGStore, ingest_run, run_canonical_queries
from archkg.kg.query import (
    CANONICAL_QUERIES,
    issues_by_filter,
    write_default_canonical_queries,
)


def _seed(tmp_path: Path) -> Path:
    """Build a populated KG fixture with 2 projects, 2 runs, 3 issues."""
    db = tmp_path / "kg.db"
    # Project A: 2 issues (one confirmed, one rejected)
    run_a = tmp_path / "run_a"
    run_a.mkdir()
    (run_a / "entity_graph.json").write_text(
        json.dumps(
            {
                "source_pdf": "a.pdf",
                "page_index": 0,
                "rooms": [{"id": "room-a", "type": "Room", "bbox": [0, 0, 10, 10]}],
                "doors": [{"id": "door-a", "type": "Door", "bbox": [0, 0, 1, 1]}],
                "corridors": [],
                "stairs": [],
                "dimensions": [],
            }
        ),
        encoding="utf-8",
    )
    (run_a / "issues.json").write_text(
        json.dumps(
            [
                {
                    "issue_id": "ISS-A1",
                    "rule_card_id": "RC-DOOR-WIDTH",
                    "standard_clause_id": "GB50096-5.1.1",
                    "entity_ids": ["door-a"],
                    "page_index": 0,
                    "severity": "error",
                    "message": "narrow door",
                },
                {
                    "issue_id": "ISS-A2",
                    "rule_card_id": "RC-CORRIDOR-WIDTH",
                    "standard_clause_id": "GB50096-5.7.2",
                    "entity_ids": [],
                    "page_index": 0,
                    "severity": "warning",
                    "message": "borderline corridor",
                },
            ]
        ),
        encoding="utf-8",
    )
    (run_a / "review_state.json").write_text(
        json.dumps({"issues": {"ISS-A1": {"status": "confirmed"}, "ISS-A2": {"status": "rejected"}}}),
        encoding="utf-8",
    )

    # Project B: 1 issue (candidate)
    run_b = tmp_path / "run_b"
    run_b.mkdir()
    (run_b / "issues.json").write_text(
        json.dumps(
            [
                {
                    "issue_id": "ISS-B1",
                    "rule_card_id": "RC-DOOR-WIDTH",
                    "standard_clause_id": "GB50096-5.1.1",
                    "entity_ids": [],
                    "page_index": 0,
                    "severity": "error",
                    "message": "another narrow door",
                }
            ]
        ),
        encoding="utf-8",
    )

    with KGStore(db) as store:
        ingest_run(store, run_dir=run_a, project_slug="proj-a")
        ingest_run(store, run_dir=run_b, project_slug="proj-b")
    return db


def test_canonical_queries_ten() -> None:
    assert len(CANONICAL_QUERIES) == 10
    ids = [q.id for q in CANONICAL_QUERIES]
    assert ids == [f"Q{i}" for i in range(1, 11)]


def test_run_canonical_queries_all_correct_on_seeded_kg(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    results = run_canonical_queries(db_path=db)
    assert len(results) == 10
    correct = [r for r in results if r["correct"]]
    assert len(correct) == 10, f"failing: {[r for r in results if not r['correct']]}"


def test_q1_issue_count_per_rule_returns_expected(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    results = run_canonical_queries(db_path=db)
    q1 = next(r for r in results if r["id"] == "Q1")
    assert q1["correct"]
    # Q1 returns [(rule_id, count), ...]; we expect RC-DOOR-WIDTH=2, RC-CORRIDOR-WIDTH=1
    sql_rows = q1["sql_first"]
    expected_map = dict(sql_rows)
    assert expected_map["RC-DOOR-WIDTH"] == 2
    assert expected_map["RC-CORRIDOR-WIDTH"] == 1


def test_q3_issue_count_by_status_includes_seeded_statuses(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    results = run_canonical_queries(db_path=db)
    q3 = next(r for r in results if r["id"] == "Q3")
    assert q3["correct"]
    statuses = dict(q3["sql_first"])
    assert statuses.get("confirmed") == 1
    assert statuses.get("rejected") == 1
    assert statuses.get("candidate") == 1


def test_q5_confirmed_lists_iss_a1(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    results = run_canonical_queries(db_path=db)
    q5 = next(r for r in results if r["id"] == "Q5")
    assert q5["correct"]
    assert q5["sql_first"] == [("proj-a", "ISS-A1")]


def test_q7_rule_with_most_rejections(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    results = run_canonical_queries(db_path=db)
    q7 = next(r for r in results if r["id"] == "Q7")
    assert q7["correct"]
    assert q7["sql_first"] == [("RC-CORRIDOR-WIDTH", 1)]


def test_issues_by_filter_rule_status_project(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    with KGStore(db, create=False) as store:
        rule_filter = issues_by_filter(store, rule="RC-DOOR-WIDTH")
        assert len(rule_filter) == 2
        confirmed_filter = issues_by_filter(store, status="confirmed")
        assert len(confirmed_filter) == 1
        assert confirmed_filter[0]["source_issue_id"] == "ISS-A1"
        proj_filter = issues_by_filter(store, project="proj-b")
        assert len(proj_filter) == 1


def test_canonical_queries_empty_db_reports_failures(tmp_path: Path) -> None:
    # No KG db at all
    results = run_canonical_queries(db_path=tmp_path / "missing.db")
    assert all(not r["correct"] for r in results)
    assert all("KG db not found" in r.get("reason", "") for r in results)


def test_canonical_queries_filter_by_manifest_subset(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    subset = [{"id": "Q1"}, {"id": "Q3"}]
    results = run_canonical_queries(subset, db_path=db)
    assert [r["id"] for r in results] == ["Q1", "Q3"]


def test_write_default_canonical_queries(tmp_path: Path) -> None:
    out = tmp_path / "cq.json"
    written = write_default_canonical_queries(out)
    assert written == out
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "canonical_queries.v1"
    assert len(loaded["queries"]) == 10
    assert loaded["queries"][0]["id"] == "Q1"


def test_canonical_queries_correct_against_empty_seeded_db(tmp_path: Path) -> None:
    """Even with zero issues, all 10 queries should be 'correct' (both sides
    return empty/zero in agreement). This guards against schemas where the
    SQL path raises and the Python path returns empty."""
    db = tmp_path / "kg.db"
    KGStore(db).close()
    results = run_canonical_queries(db_path=db)
    assert all(r["correct"] for r in results), f"failing: {[r for r in results if not r['correct']]}"
