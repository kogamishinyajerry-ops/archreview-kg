"""Tests for archkg.kg.web (M5.D — Flask UI + 5 e2e flows)."""

from __future__ import annotations

import json
from pathlib import Path

from archkg.kg import KGStore, add_feedback, create_app, ingest_run, run_e2e_smoke


def _seed_kg(tmp_path: Path) -> Path:
    db = tmp_path / "kg.db"
    run_dir = tmp_path / "demo_run"
    run_dir.mkdir()
    (run_dir / "issues.json").write_text(
        json.dumps(
            [
                {
                    "issue_id": "ISS-1",
                    "rule_card_id": "RC-DOOR-WIDTH",
                    "standard_clause_id": "GB50096-5.1.1",
                    "entity_ids": [],
                    "bbox": [0, 0, 10, 10],
                    "page_index": 0,
                    "severity": "error",
                    "message": "narrow door",
                    "evidence": {"measured_value": 0.8, "threshold": 0.9},
                }
            ]
        ),
        encoding="utf-8",
    )
    with KGStore(db) as store:
        ingest_run(store, run_dir=run_dir, project_slug="demo")
    return db


def test_index_returns_html(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    app = create_app(db)
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"ArchReview-KG Workbench" in resp.data
    assert b"<table" in resp.data


def test_project_list_returns_seeded_project(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    slugs = [p["slug"] for p in data]
    assert "demo" in slugs
    demo = next(p for p in data if p["slug"] == "demo")
    assert demo["issue_count"] == 1
    assert demo["drawing_count"] == 1


def test_project_drawings_404_for_unknown_project(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    resp = client.get("/api/projects/does-not-exist/drawings")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "project not found"


def test_project_drawings_returns_drawings(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    resp = client.get("/api/projects/demo/drawings")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["project"] == "demo"
    assert len(data["drawings"]) == 1


def test_heatmap_returns_rule_with_issue(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    resp = client.get("/api/heatmap")
    assert resp.status_code == 200
    data = resp.get_json()
    rids = [r["rule_id"] for r in data]
    assert "RC-DOOR-WIDTH" in rids
    rule_row = next(r for r in data if r["rule_id"] == "RC-DOOR-WIDTH")
    assert rule_row["total"] == 1
    assert rule_row["candidate"] == 1


def test_issue_detail_returns_full_lineage(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    # Add a feedback event first
    with KGStore(db, create=False) as store:
        rows = store._conn.execute("SELECT id FROM issue").fetchall()
        iid = int(rows[0]["id"])
        add_feedback(store, issue_id=iid, reviewer_id="alice", event_type="needs_info")

    resp = client.get(f"/api/issues/{iid}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source_issue_id"] == "ISS-1"
    assert data["rule_id"] == "RC-DOOR-WIDTH"
    assert data["project_slug"] == "demo"
    assert data["status"] == "needs_info"
    assert data["evidence"] == {"measured_value": 0.8, "threshold": 0.9}
    assert data["bbox"] == [0, 0, 10, 10]
    assert len(data["feedback_events"]) == 1
    assert data["feedback_events"][0]["event_type"] == "needs_info"
    assert data["feedback_events"][0]["reviewer_id"] == "alice"


def test_issue_detail_404_for_unknown_id(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    resp = client.get("/api/issues/99999")
    assert resp.status_code == 404


def test_post_feedback_inserts_event(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    with KGStore(db, create=False) as store:
        iid = int(store._conn.execute("SELECT id FROM issue").fetchone()["id"])
    resp = client.post(
        f"/api/issues/{iid}/feedback",
        json={"reviewer": "bob", "event": "confirm"},
    )
    assert resp.status_code == 200
    assert "feedback_event_id" in resp.get_json()
    with KGStore(db, create=False) as store:
        row = store._conn.execute(
            "SELECT status FROM issue WHERE id = ?", (iid,)
        ).fetchone()
        assert row["status"] == "confirmed"


def test_post_feedback_missing_fields_returns_400(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    resp = client.post("/api/issues/1/feedback", json={})
    assert resp.status_code == 400


def test_post_feedback_rejects_unknown_event_type(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    client = create_app(db).test_client()
    with KGStore(db, create=False) as store:
        iid = int(store._conn.execute("SELECT id FROM issue").fetchone()["id"])
    resp = client.post(
        f"/api/issues/{iid}/feedback",
        json={"reviewer": "bob", "event": "bogus"},
    )
    assert resp.status_code == 400


def test_e2e_smoke_runs_all_five_flows(tmp_path: Path) -> None:
    db = _seed_kg(tmp_path)
    report = run_e2e_smoke(db)
    flows = report["flows"]
    names = {f["name"] for f in flows}
    expected = {"index_html", "project_list", "project_drawings", "heatmap", "issue_detail", "annotate_feedback"}
    assert expected <= names
    # Every flow must complete well under 30s p95
    for f in flows:
        assert f["p95_ms"] < 30000, f"{f['name']} slow: {f['p95_ms']}ms"
    # All flows pass with a seeded KG
    assert all(f["passed"] for f in flows), [f for f in flows if not f["passed"]]


def test_e2e_smoke_empty_db_reports_failures(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"
    KGStore(db).close()
    report = run_e2e_smoke(db)
    flows = {f["name"]: f for f in report["flows"]}
    # index + project_list + heatmap return 200 with empty data
    assert flows["index_html"]["passed"]
    assert flows["project_list"]["passed"]
    assert flows["heatmap"]["passed"]
    # project_drawings, issue_detail, annotate_feedback fail because no data
    assert not flows["project_drawings"]["passed"]
    assert not flows["issue_detail"]["passed"]
    assert not flows["annotate_feedback"]["passed"]
