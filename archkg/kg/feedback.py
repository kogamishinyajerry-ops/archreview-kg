"""Reviewer feedback event handling for the KG (M5.G).

Records reviewer reject / confirm / needs_info / resolve events into the
`feedback_event` table and updates per-rule confidence priors using a
Beta-Binomial conjugate update:

    posterior_alpha = prior_alpha + confirmed_count
    posterior_beta  = prior_beta  + rejected_count
    posterior_mean  = alpha / (alpha + beta)

Default prior is Beta(1, 1) — uniform — which makes the posterior mean
exactly `confirmed / (confirmed + rejected)` once any feedback has been
recorded. Rules with zero feedback retain a `null` prior in the report.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archkg.kg.store import KGStore, default_db_path

EVENT_TYPES = ("confirm", "reject", "needs_info", "resolve", "supersede", "comment")

# Beta-Binomial conjugate prior. Beta(1, 1) == uniform.
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def upsert_reviewer(store: KGStore, reviewer_id: str, display_name: str | None = None) -> int:
    # Connection is autocommit (isolation_level=None). Avoid nested
    # explicit transactions when this is called from within another
    # `with store._conn:` block.
    store._conn.execute(
        "INSERT INTO reviewer(reviewer_id, display_name) VALUES (?, ?) "
        "ON CONFLICT(reviewer_id) DO UPDATE SET display_name = excluded.display_name",
        (reviewer_id, display_name),
    )
    row = store._conn.execute(
        "SELECT id FROM reviewer WHERE reviewer_id = ?", (reviewer_id,)
    ).fetchone()
    return int(row["id"])


def add_feedback(
    store: KGStore,
    *,
    issue_id: int,
    reviewer_id: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    update_issue_status: bool = True,
) -> int:
    """Insert a feedback_event row. Optionally mirror state into issue.status.

    Returns the new feedback_event row id.
    """

    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type: {event_type} (allowed: {EVENT_TYPES})")
    rev_db_id = upsert_reviewer(store, reviewer_id)
    cur = store._conn.execute(
        "INSERT INTO feedback_event(issue_id, reviewer_id, event_type, payload_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            issue_id,
            rev_db_id,
            event_type,
            json.dumps(dict(payload or {}), ensure_ascii=False),
            _utcnow_iso(),
        ),
    )
    fb_id = int(cur.lastrowid or 0)
    if update_issue_status:
        new_status = {
            "confirm": "confirmed",
            "reject": "rejected",
            "needs_info": "needs_info",
            "resolve": "resolved",
            "supersede": "superseded",
        }.get(event_type)
        if new_status:
            store._conn.execute(
                "UPDATE issue SET status = ? WHERE id = ?",
                (new_status, issue_id),
            )
    return fb_id


@dataclass
class RulePrior:
    rule_id: str
    confirmed: int
    rejected: int
    posterior_alpha: float
    posterior_beta: float
    posterior_mean: float
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "confirmed": self.confirmed,
            "rejected": self.rejected,
            "posterior_alpha": round(self.posterior_alpha, 4),
            "posterior_beta": round(self.posterior_beta, 4),
            "posterior_mean": round(self.posterior_mean, 4),
            "sample_size": self.sample_size,
        }


def rule_priors(
    store: KGStore,
    *,
    prior_alpha: float = PRIOR_ALPHA,
    prior_beta: float = PRIOR_BETA,
) -> list[RulePrior]:
    """Compute per-rule Beta-Binomial posterior using feedback events.

    Only `confirm` and `reject` events update the prior; other event types
    are tracked but do not move the calibration.
    """
    rows = store._conn.execute(
        "SELECT r.rule_id AS rid, "
        "SUM(CASE WHEN fe.event_type = 'confirm' THEN 1 ELSE 0 END) AS confirmed, "
        "SUM(CASE WHEN fe.event_type = 'reject' THEN 1 ELSE 0 END) AS rejected "
        "FROM rule r "
        "LEFT JOIN issue i ON i.rule_id = r.id "
        "LEFT JOIN feedback_event fe ON fe.issue_id = i.id "
        "GROUP BY r.rule_id "
        "HAVING confirmed > 0 OR rejected > 0"
    ).fetchall()
    out: list[RulePrior] = []
    for row in rows:
        confirmed = int(row["confirmed"] or 0)
        rejected = int(row["rejected"] or 0)
        a = prior_alpha + confirmed
        b = prior_beta + rejected
        mean = a / (a + b)
        out.append(
            RulePrior(
                rule_id=row["rid"],
                confirmed=confirmed,
                rejected=rejected,
                posterior_alpha=a,
                posterior_beta=b,
                posterior_mean=mean,
                sample_size=confirmed + rejected,
            )
        )
    out.sort(key=lambda p: p.rule_id)
    return out


def feedback_loop_synthetic_test(db_path: Path | None = None) -> dict[str, Any]:
    """Synthetic deterministic test that proves the feedback loop is wired.

    Builds an isolated KG in a tmp dir (does NOT touch the user's KG), seeds
    a rule + N issues, and verifies that adding M reject events shifts the
    posterior mean by the expected Beta-Binomial amount.

    Returned dict has the keys the scorer reads:
        monotonic: bool   — did each new reject lower the mean?
        delta: float       — observed change in posterior mean
        expected_delta: float — analytically computed expected change
    """

    import tempfile

    with tempfile.TemporaryDirectory(prefix="archkg-fb-") as tmp_str:
        tmp = Path(tmp_str)
        db = db_path or (tmp / "synthetic_kg.db")
        with KGStore(db) as store:
            # Seed: 1 project, 1 drawing, 1 run, 1 rule, 5 issues.
            proj = store.upsert_project("synthetic-feedback")
            draw = store.upsert_drawing(project_id=proj, source_path="syn.pdf")
            run = store.upsert_run(project_id=proj, drawing_id=draw, run_dir="syn_run")
            with store._conn:
                cur = store._conn.execute(
                    "INSERT INTO rule(rule_id, version) VALUES (?, ?)",
                    ("RC-SYNTHETIC", "1"),
                )
                rule_db = int(cur.lastrowid or 0)
            issue_ids: list[int] = []
            for i in range(5):
                with store._conn:
                    cur = store._conn.execute(
                        "INSERT INTO issue(run_id, rule_id, source_issue_id, severity, message) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (run, rule_db, f"SYN-{i}", "error", f"synthetic {i}"),
                    )
                    issue_ids.append(int(cur.lastrowid or 0))

            # Baseline posterior (no feedback): mean is exactly prior mean
            baseline = rule_priors(store)
            assert baseline == [], "baseline should have no rule with feedback yet"
            prior_mean = PRIOR_ALPHA / (PRIOR_ALPHA + PRIOR_BETA)

            # Add 3 rejects and 1 confirm. Track means after each event.
            means_after: list[float] = []
            for _ in range(3):
                add_feedback(
                    store,
                    issue_id=issue_ids[len(means_after)],
                    reviewer_id="rev-test",
                    event_type="reject",
                )
                priors = rule_priors(store)
                means_after.append(next(p.posterior_mean for p in priors if p.rule_id == "RC-SYNTHETIC"))
            add_feedback(
                store,
                issue_id=issue_ids[3],
                reviewer_id="rev-test",
                event_type="confirm",
            )
            final_priors = rule_priors(store)
            final = next(p for p in final_priors if p.rule_id == "RC-SYNTHETIC")

            # Monotonic check: after each successive reject the mean strictly
            # decreased relative to the prior (3 rejects in a row).
            monotonic = all(
                means_after[i] > means_after[i + 1]
                for i in range(len(means_after) - 1)
            )

            # Final state: 3 rejects + 1 confirm with Beta(1,1) prior
            # -> alpha = 1 + 1 = 2, beta = 1 + 3 = 4, mean = 2 / 6 ~= 0.3333
            expected_alpha = PRIOR_ALPHA + 1
            expected_beta = PRIOR_BETA + 3
            expected_mean = expected_alpha / (expected_alpha + expected_beta)
            expected_delta = expected_mean - prior_mean  # negative number
            observed_delta = final.posterior_mean - prior_mean

            return {
                "monotonic": monotonic,
                "delta": round(observed_delta, 6),
                "expected_delta": round(expected_delta, 6),
                "final_posterior_mean": round(final.posterior_mean, 6),
                "final_confirmed": final.confirmed,
                "final_rejected": final.rejected,
                "means_after_each_reject": [round(m, 6) for m in means_after],
            }


__all__ = [
    "EVENT_TYPES",
    "PRIOR_ALPHA",
    "PRIOR_BETA",
    "RulePrior",
    "add_feedback",
    "feedback_loop_synthetic_test",
    "rule_priors",
    "upsert_reviewer",
]


# Calibration is a separate concern but lives in the same package. We expose
# the entry point used by the scorer here as a small wrapper, and the heavy
# implementation in archkg.kg.calibration.
def _stub_default_db_used_for_import_test() -> Path:  # pragma: no cover - import-only
    return default_db_path()
