"""Local Flask web UI for the ArchReview-KG knowledge graph (M5.D).

Five reviewer flows:
1. Project list (`GET /api/projects`)
2. Drawing browser per project (`GET /api/projects/<slug>/drawings`)
3. Rule trigger heatmap (`GET /api/heatmap`)
4. Issue lineage (`GET /api/issues/<id>`)
5. Reviewer annotation (`POST /api/issues/<id>/feedback`)

The UI is vanilla JS, no build step, no React. `run_e2e_smoke()` exercises
all five flows via Flask's test client and returns timings consumed by the
`web_ui_e2e` scoring dimension.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from archkg.kg.feedback import add_feedback
from archkg.kg.store import KGStore, default_db_path

INDEX_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>ArchReview-KG Workbench</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 0; background: #f8fafc; }
    header { background: #1f2937; color: white; padding: 12px 24px; }
    main { padding: 16px 24px; }
    h1 { font-size: 18px; margin: 0; }
    h2 { font-size: 14px; color: #475569; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 24px; }
    table { border-collapse: collapse; width: 100%; background: white; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 6px 10px; text-align: left; font-size: 13px; }
    th { background: #f1f5f9; font-weight: 600; color: #1e293b; }
    tr:hover { background: #f1f5f9; cursor: pointer; }
    pre { background: white; padding: 12px; border: 1px solid #e5e7eb; font-size: 12px; overflow: auto; }
    nav a { color: white; margin-right: 16px; text-decoration: none; font-size: 13px; }
    nav a:hover { text-decoration: underline; }
    .status { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .candidate { background: #fef3c7; color: #92400e; }
    .confirmed { background: #d1fae5; color: #065f46; }
    .rejected { background: #fee2e2; color: #991b1b; }
    .needs_info { background: #dbeafe; color: #1e40af; }
  </style>
</head>
<body>
  <header>
    <h1>ArchReview-KG Workbench</h1>
    <nav>
      <a href=\"#projects\">Projects</a>
      <a href=\"#heatmap\">Heatmap</a>
      <a href=\"/api/projects\">Raw JSON</a>
    </nav>
  </header>
  <main>
    <h2 id=\"projects\">Projects</h2>
    <table id=\"projects_table\"><thead><tr><th>Slug</th><th>Name</th><th>Drawings</th><th>Issues</th></tr></thead><tbody></tbody></table>

    <h2 id=\"heatmap\">Rule Trigger Heatmap</h2>
    <table id=\"heatmap_table\"><thead><tr><th>Rule</th><th>Total</th><th>Confirmed</th><th>Rejected</th><th>Candidate</th></tr></thead><tbody></tbody></table>

    <h2 id=\"issue_detail\">Selected issue</h2>
    <pre id=\"issue_pre\">(click an issue row in the future Drawings drilldown — out of scope for the M5.D smoke set)</pre>
  </main>
  <script>
    async function fetchJSON(url) {
      const res = await fetch(url);
      return await res.json();
    }
    async function loadProjects() {
      const data = await fetchJSON('/api/projects');
      const tbody = document.querySelector('#projects_table tbody');
      tbody.innerHTML = '';
      for (const p of data) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${p.slug}</td><td>${p.name || ''}</td><td>${p.drawing_count}</td><td>${p.issue_count}</td>`;
        tbody.appendChild(tr);
      }
    }
    async function loadHeatmap() {
      const data = await fetchJSON('/api/heatmap');
      const tbody = document.querySelector('#heatmap_table tbody');
      tbody.innerHTML = '';
      for (const row of data) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${row.rule_id}</td><td>${row.total}</td><td>${row.confirmed}</td><td>${row.rejected}</td><td>${row.candidate}</td>`;
        tbody.appendChild(tr);
      }
    }
    loadProjects(); loadHeatmap();
  </script>
</body>
</html>"""


def create_app(db_path: Path | None = None) -> Flask:
    """Build the Flask app. Each request opens its own KGStore connection."""

    app = Flask(__name__)
    app.config["KG_DB_PATH"] = str(db_path or default_db_path(Path.cwd()))

    def _store() -> KGStore:
        return KGStore(Path(app.config["KG_DB_PATH"]), create=False)

    @app.get("/")
    def index() -> tuple[str, int, dict[str, str]]:
        return INDEX_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.get("/api/projects")
    def list_projects() -> Any:
        with _store() as store:
            rows = store._conn.execute(
                "SELECT p.slug, p.name, "
                "(SELECT COUNT(*) FROM drawing d WHERE d.project_id = p.id) AS drawing_count, "
                "(SELECT COUNT(*) FROM issue i JOIN run rn ON i.run_id = rn.id WHERE rn.project_id = p.id) AS issue_count "
                "FROM project p ORDER BY p.slug"
            ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.get("/api/projects/<slug>/drawings")
    def project_drawings(slug: str) -> Any:
        with _store() as store:
            row = store._conn.execute(
                "SELECT id FROM project WHERE slug = ?", (slug,)
            ).fetchone()
            if not row:
                return jsonify({"error": "project not found", "slug": slug}), 404
            project_id = int(row["id"])
            drawings = [
                dict(r)
                for r in store._conn.execute(
                    "SELECT id, source_path, page_count, created_at FROM drawing WHERE project_id = ? ORDER BY id",
                    (project_id,),
                ).fetchall()
            ]
        return jsonify({"project": slug, "drawings": drawings})

    @app.get("/api/heatmap")
    def heatmap() -> Any:
        with _store() as store:
            rows = store._conn.execute(
                "SELECT r.rule_id AS rule_id, "
                "COUNT(i.id) AS total, "
                "SUM(CASE WHEN i.status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed, "
                "SUM(CASE WHEN i.status = 'rejected' THEN 1 ELSE 0 END) AS rejected, "
                "SUM(CASE WHEN i.status = 'candidate' THEN 1 ELSE 0 END) AS candidate "
                "FROM rule r LEFT JOIN issue i ON i.rule_id = r.id "
                "GROUP BY r.rule_id "
                "HAVING total > 0 "
                "ORDER BY total DESC, r.rule_id"
            ).fetchall()
        return jsonify(
            [
                {
                    "rule_id": r["rule_id"],
                    "total": int(r["total"]),
                    "confirmed": int(r["confirmed"] or 0),
                    "rejected": int(r["rejected"] or 0),
                    "candidate": int(r["candidate"] or 0),
                }
                for r in rows
            ]
        )

    @app.get("/api/issues/<int:issue_id>")
    def issue_detail(issue_id: int) -> Any:
        with _store() as store:
            row = store._conn.execute(
                "SELECT i.*, r.rule_id AS rule_label, p.slug AS project_slug, "
                "d.source_path AS source_path "
                "FROM issue i "
                "JOIN run rn ON i.run_id = rn.id "
                "JOIN project p ON rn.project_id = p.id "
                "LEFT JOIN drawing d ON rn.drawing_id = d.id "
                "LEFT JOIN rule r ON i.rule_id = r.id "
                "WHERE i.id = ?",
                (issue_id,),
            ).fetchone()
            if not row:
                return jsonify({"error": "issue not found", "id": issue_id}), 404
            feedback_rows = store._conn.execute(
                "SELECT fe.event_type, fe.created_at, fe.payload_json, rv.reviewer_id "
                "FROM feedback_event fe LEFT JOIN reviewer rv ON fe.reviewer_id = rv.id "
                "WHERE fe.issue_id = ? ORDER BY fe.id",
                (issue_id,),
            ).fetchall()
        return jsonify(
            {
                "id": int(row["id"]),
                "source_issue_id": row["source_issue_id"],
                "status": row["status"],
                "severity": row["severity"],
                "message": row["message"],
                "rule_id": row["rule_label"],
                "project_slug": row["project_slug"],
                "source_path": row["source_path"],
                "bbox": json.loads(row["bbox_json"]) if row["bbox_json"] else None,
                "evidence": json.loads(row["evidence_json"]) if row["evidence_json"] else None,
                "feedback_events": [
                    {
                        "event_type": fr["event_type"],
                        "reviewer_id": fr["reviewer_id"],
                        "created_at": fr["created_at"],
                        "payload": json.loads(fr["payload_json"] or "{}"),
                    }
                    for fr in feedback_rows
                ],
            }
        )

    @app.post("/api/issues/<int:issue_id>/feedback")
    def post_feedback(issue_id: int) -> Any:
        data: Mapping[str, Any] = request.get_json(silent=True) or {}
        reviewer = data.get("reviewer")
        event = data.get("event")
        if not reviewer or not event:
            return jsonify({"error": "reviewer and event are required"}), 400
        with _store() as store:
            try:
                fb_id = add_feedback(
                    store,
                    issue_id=issue_id,
                    reviewer_id=str(reviewer),
                    event_type=str(event),
                    payload=data.get("payload"),
                )
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        return jsonify({"feedback_event_id": fb_id})

    return app


def _time_flow(name: str, fn: Any) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        resp = fn()
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = int(resp.status_code) if hasattr(resp, "status_code") else 500
        return {
            "name": name,
            "p95_ms": round(elapsed_ms, 3),
            "passed": 200 <= status < 300,
            "status_code": status,
        }
    except Exception as exc:
        return {
            "name": name,
            "p95_ms": round((time.perf_counter() - start) * 1000, 3),
            "passed": False,
            "status_code": 0,
            "error": repr(exc),
        }


def run_e2e_smoke(db_path: Path | None = None) -> dict[str, Any]:
    """Exercise all five flows via Flask's test client. Used by scorer."""

    app = create_app(db_path)
    client = app.test_client()

    flows: list[dict[str, Any]] = []
    flows.append(_time_flow("index_html", lambda: client.get("/")))
    flows.append(_time_flow("project_list", lambda: client.get("/api/projects")))

    # Discover one project + one issue to drive remaining flows
    proj_resp = client.get("/api/projects")
    project_slug = None
    if proj_resp.status_code == 200:
        data = proj_resp.get_json() or []
        if data:
            project_slug = data[0]["slug"]
    if project_slug:
        flows.append(
            _time_flow(
                "project_drawings",
                lambda: client.get(f"/api/projects/{project_slug}/drawings"),
            )
        )
    else:
        flows.append({"name": "project_drawings", "p95_ms": 0, "passed": False, "status_code": 0, "error": "no projects in KG"})

    flows.append(_time_flow("heatmap", lambda: client.get("/api/heatmap")))

    # Find any issue id
    issue_id = None
    db = db_path or default_db_path(Path.cwd())
    if db.exists():
        with KGStore(db, create=False) as store:
            row = store._conn.execute("SELECT id FROM issue LIMIT 1").fetchone()
            if row:
                issue_id = int(row["id"])
    if issue_id:
        flows.append(_time_flow("issue_detail", lambda: client.get(f"/api/issues/{issue_id}")))
        flows.append(
            _time_flow(
                "annotate_feedback",
                lambda: client.post(
                    f"/api/issues/{issue_id}/feedback",
                    json={"reviewer": "smoke-runner", "event": "needs_info"},
                ),
            )
        )
    else:
        flows.append({"name": "issue_detail", "p95_ms": 0, "passed": False, "status_code": 0, "error": "no issues in KG"})
        flows.append({"name": "annotate_feedback", "p95_ms": 0, "passed": False, "status_code": 0, "error": "no issues in KG"})

    return {"db_path": str(db_path or default_db_path(Path.cwd())), "flows": flows}


__all__ = ["INDEX_HTML", "create_app", "run_e2e_smoke"]
