"""ArchReview-KG knowledge graph layer (M5).

A local SQLite-backed graph store for cross-project entity / rule / issue /
reviewer / feedback persistence. Intended to be local-first; no server,
no network, no cloud.

Schema is versioned via `schema_version` table. Migrations are forward-only.
"""

from archkg.kg.calibration import CalibrationBin, build_calibration_report
from archkg.kg.feedback import (
    EVENT_TYPES,
    RulePrior,
    add_feedback,
    feedback_loop_synthetic_test,
    rule_priors,
)
from archkg.kg.ingest import INGESTABLE_ARTIFACTS, IngestResult, has_ingestable_artifact, ingest_run
from archkg.kg.query import CANONICAL_QUERIES, issues_by_filter, run_canonical_queries
from archkg.kg.store import KGStore, KGStoreError

__all__ = [
    "CANONICAL_QUERIES",
    "EVENT_TYPES",
    "INGESTABLE_ARTIFACTS",
    "CalibrationBin",
    "IngestResult",
    "KGStore",
    "KGStoreError",
    "RulePrior",
    "add_feedback",
    "build_calibration_report",
    "feedback_loop_synthetic_test",
    "has_ingestable_artifact",
    "ingest_run",
    "issues_by_filter",
    "rule_priors",
    "run_canonical_queries",
]
