"""ArchReview-KG knowledge graph layer (M5).

A local SQLite-backed graph store for cross-project entity / rule / issue /
reviewer / feedback persistence. Intended to be local-first; no server,
no network, no cloud.

Schema is versioned via `schema_version` table. Migrations are forward-only.
"""

from archkg.kg.ingest import INGESTABLE_ARTIFACTS, IngestResult, has_ingestable_artifact, ingest_run
from archkg.kg.query import CANONICAL_QUERIES, issues_by_filter, run_canonical_queries
from archkg.kg.store import KGStore, KGStoreError

__all__ = [
    "CANONICAL_QUERIES",
    "INGESTABLE_ARTIFACTS",
    "IngestResult",
    "KGStore",
    "KGStoreError",
    "has_ingestable_artifact",
    "ingest_run",
    "issues_by_filter",
    "run_canonical_queries",
]
