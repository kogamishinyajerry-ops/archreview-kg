"""SQLite-backed knowledge graph store for ArchReview-KG.

Design choices:

- SQLite over Neo4j / Postgres: M5 is local-first; SQLite + WAL handles the
  expected single-writer reviewer workflow well and keeps the project
  zero-dependency for users.
- Schema is versioned in a `schema_version` table. Forward-only migrations.
- Append-only `feedback_event` and `edge` tables — no destructive history.
- All timestamps stored as ISO-8601 UTC strings.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kg.v1"

DEFAULT_DB_DIRNAME = ".archkg"
DEFAULT_DB_FILENAME = "kg.db"


REQUIRED_TABLES: tuple[str, ...] = (
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
)


# DDL for schema kg.v1. Forward-only; future schemas add migrations rather
# than mutating this string.
SCHEMA_V1_DDL: tuple[str, ...] = (
    # PRAGMAs are applied per-connection by _connect.
    """CREATE TABLE IF NOT EXISTS schema_version (
        version TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS project (
        id INTEGER PRIMARY KEY,
        slug TEXT UNIQUE NOT NULL,
        name TEXT,
        created_at TEXT NOT NULL,
        meta_json TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS drawing (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
        source_path TEXT,
        source_hash TEXT,
        page_count INTEGER,
        created_at TEXT NOT NULL,
        meta_json TEXT,
        UNIQUE(project_id, source_path)
    )""",
    """CREATE TABLE IF NOT EXISTS sheet (
        id INTEGER PRIMARY KEY,
        drawing_id INTEGER NOT NULL REFERENCES drawing(id) ON DELETE CASCADE,
        page_index INTEGER NOT NULL,
        sheet_type TEXT,
        confidence REAL,
        meta_json TEXT,
        UNIQUE(drawing_id, page_index)
    )""",
    """CREATE TABLE IF NOT EXISTS run (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
        drawing_id INTEGER REFERENCES drawing(id) ON DELETE SET NULL,
        run_dir TEXT NOT NULL,
        ingested_at TEXT NOT NULL,
        archkg_version TEXT,
        artifacts_json TEXT,
        UNIQUE(project_id, run_dir)
    )""",
    """CREATE TABLE IF NOT EXISTS rule (
        id INTEGER PRIMARY KEY,
        rule_id TEXT NOT NULL,
        version TEXT NOT NULL DEFAULT '1',
        source_clause_ids TEXT,
        inputs TEXT,
        logic_expression TEXT,
        meta_json TEXT,
        UNIQUE(rule_id, version)
    )""",
    """CREATE TABLE IF NOT EXISTS clause (
        id INTEGER PRIMARY KEY,
        clause_id TEXT NOT NULL,
        standard_id TEXT,
        standard_version TEXT,
        text TEXT,
        meta_json TEXT,
        UNIQUE(clause_id, standard_version)
    )""",
    """CREATE TABLE IF NOT EXISTS entity (
        id INTEGER PRIMARY KEY,
        run_id INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
        sheet_id INTEGER REFERENCES sheet(id) ON DELETE SET NULL,
        entity_type TEXT NOT NULL,
        source_id TEXT,
        bbox_json TEXT,
        properties_json TEXT,
        confidence REAL
    )""",
    """CREATE TABLE IF NOT EXISTS issue (
        id INTEGER PRIMARY KEY,
        run_id INTEGER NOT NULL REFERENCES run(id) ON DELETE CASCADE,
        sheet_id INTEGER REFERENCES sheet(id) ON DELETE SET NULL,
        rule_id INTEGER REFERENCES rule(id) ON DELETE SET NULL,
        entity_id INTEGER REFERENCES entity(id) ON DELETE SET NULL,
        source_issue_id TEXT,
        severity TEXT,
        message TEXT,
        bbox_json TEXT,
        evidence_json TEXT,
        confidence REAL,
        status TEXT NOT NULL DEFAULT 'candidate'
    )""",
    """CREATE TABLE IF NOT EXISTS reviewer (
        id INTEGER PRIMARY KEY,
        reviewer_id TEXT UNIQUE NOT NULL,
        display_name TEXT,
        meta_json TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS feedback_event (
        id INTEGER PRIMARY KEY,
        issue_id INTEGER NOT NULL REFERENCES issue(id) ON DELETE CASCADE,
        reviewer_id INTEGER REFERENCES reviewer(id) ON DELETE SET NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS edge (
        id INTEGER PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_id INTEGER NOT NULL,
        edge_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        meta_json TEXT,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_drawing_project ON drawing(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_sheet_drawing ON sheet(drawing_id)",
    "CREATE INDEX IF NOT EXISTS idx_run_project ON run(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_entity_run ON entity(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_entity_sheet ON entity(sheet_id)",
    "CREATE INDEX IF NOT EXISTS idx_issue_run ON issue(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_issue_rule ON issue(rule_id)",
    "CREATE INDEX IF NOT EXISTS idx_issue_status ON issue(status)",
    "CREATE INDEX IF NOT EXISTS idx_issue_sheet ON issue(sheet_id)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_issue ON feedback_event(issue_id)",
    "CREATE INDEX IF NOT EXISTS idx_edge_source ON edge(source_type, source_id)",
    "CREATE INDEX IF NOT EXISTS idx_edge_target ON edge(target_type, target_id)",
    "CREATE INDEX IF NOT EXISTS idx_edge_type ON edge(edge_type)",
)


class KGStoreError(RuntimeError):
    pass


@dataclass
class HealthReport:
    schema_version: str | None
    tables_present: list[str]
    required_tables_present: bool
    counts: dict[str, int]
    query_p95_ms: float
    db_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tables_present": self.tables_present,
            "required_tables_present": self.required_tables_present,
            "counts": self.counts,
            "query_p95_ms": round(self.query_p95_ms, 3),
            "db_path": self.db_path,
        }


def default_db_path(repo: Path | None = None) -> Path:
    """Return the default KG db location.

    Prefer `<repo>/.archkg/kg.db` when a repo path is provided; fall back to
    `~/.archkg/kg.db` for global use.
    """
    if repo is not None:
        return repo / DEFAULT_DB_DIRNAME / DEFAULT_DB_FILENAME
    return Path.home() / DEFAULT_DB_DIRNAME / DEFAULT_DB_FILENAME


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class KGStore:
    """Thin wrapper over a sqlite3 connection.

    Construction is cheap; the database is created (with schema) if it does
    not exist. Connections are not pooled — each KGStore owns one
    connection and is single-threaded. For test isolation, instantiate a
    new KGStore per test against a tmp_path db.
    """

    def __init__(self, db_path: Path, *, create: bool = True) -> None:
        self.db_path = db_path
        if not db_path.exists():
            if not create:
                raise KGStoreError(f"KG database not found: {db_path}")
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._connect(db_path)
        self._migrate()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _connect(db_path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> KGStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        with self._conn:
            for stmt in SCHEMA_V1_DDL:
                self._conn.execute(stmt)
            cur = self._conn.execute(
                "SELECT version FROM schema_version WHERE version = ?",
                (SCHEMA_VERSION,),
            )
            if cur.fetchone() is None:
                self._conn.execute(
                    "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _utcnow_iso()),
                )

    def list_tables(self) -> list[str]:
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row["name"] for row in cur.fetchall()]

    def schema_version(self) -> str | None:
        cur = self._conn.execute(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        return row["version"] if row else None

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        tables = self.list_tables()
        required_present = all(t in tables for t in REQUIRED_TABLES)
        counts: dict[str, int] = {}
        for t in REQUIRED_TABLES:
            if t in tables:
                cur = self._conn.execute(f"SELECT COUNT(*) AS c FROM {t}")
                row = cur.fetchone()
                counts[t] = int(row["c"]) if row else 0
            else:
                counts[t] = 0

        # Latency sample: 10 lightweight SELECTs against `run` and `issue`
        samples_ms: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            self._conn.execute("SELECT COUNT(*) FROM run").fetchone()
            self._conn.execute("SELECT COUNT(*) FROM issue").fetchone()
            samples_ms.append((time.perf_counter() - start) * 1000.0)
        samples_ms.sort()
        p95 = samples_ms[int(0.95 * (len(samples_ms) - 1))]

        report = HealthReport(
            schema_version=self.schema_version(),
            tables_present=tables,
            required_tables_present=required_present,
            counts=counts,
            query_p95_ms=p95,
            db_path=str(self.db_path),
        )
        return report.to_dict()

    def count_runs(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) AS c FROM run")
        row = cur.fetchone()
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------
    # Generic insert / upsert helpers used by ingest in M5.A.2
    # ------------------------------------------------------------------

    def upsert_project(self, slug: str, name: str | None = None, meta: Mapping[str, Any] | None = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO project(slug, name, created_at, meta_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, meta_json=excluded.meta_json",
                (slug, name, _utcnow_iso(), json.dumps(meta or {}, ensure_ascii=False)),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = self._conn.execute("SELECT id FROM project WHERE slug = ?", (slug,)).fetchone()
            return int(row["id"])

    def upsert_drawing(
        self,
        *,
        project_id: int,
        source_path: str,
        source_hash: str | None = None,
        page_count: int | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO drawing(project_id, source_path, source_hash, page_count, created_at, meta_json) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(project_id, source_path) DO UPDATE SET "
                "source_hash=excluded.source_hash, page_count=excluded.page_count, meta_json=excluded.meta_json",
                (
                    project_id,
                    source_path,
                    source_hash,
                    page_count,
                    _utcnow_iso(),
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = self._conn.execute(
                "SELECT id FROM drawing WHERE project_id = ? AND source_path = ?",
                (project_id, source_path),
            ).fetchone()
            return int(row["id"])

    def upsert_run(
        self,
        *,
        project_id: int,
        drawing_id: int | None,
        run_dir: str,
        archkg_version: str | None = None,
        artifacts: Iterable[str] | None = None,
    ) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO run(project_id, drawing_id, run_dir, ingested_at, archkg_version, artifacts_json) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(project_id, run_dir) DO UPDATE SET "
                "drawing_id=excluded.drawing_id, ingested_at=excluded.ingested_at, "
                "archkg_version=excluded.archkg_version, artifacts_json=excluded.artifacts_json",
                (
                    project_id,
                    drawing_id,
                    run_dir,
                    _utcnow_iso(),
                    archkg_version,
                    json.dumps(sorted(set(artifacts or [])), ensure_ascii=False),
                ),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = self._conn.execute(
                "SELECT id FROM run WHERE project_id = ? AND run_dir = ?",
                (project_id, run_dir),
            ).fetchone()
            return int(row["id"])
