"""Per-rule confidence calibrator (M5.I.2).

Replaces raw entity-derived issue confidence with the Beta-Binomial
posterior mean of reviewer outcomes for that rule. Once applied, the
calibration reliability diagram should report observed precision close
to predicted confidence per bin (because every issue of rule X now
carries the *measured* per-rule precision as its confidence value).

Honest framing:
- This is a calibration of the **rule layer**, not the entity recogniser.
  All issues of a given rule receive the same posterior-mean confidence.
- It only moves the calibration metric when there is genuine reviewer
  feedback for that rule. Rules with zero feedback retain their original
  (uncalibrated) confidence and an explicit `calibrated: false` flag.
- It does NOT mutate `issues.json` on disk. The KG is the system of
  record for calibrated state; the source artifact stays untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archkg.kg.feedback import PRIOR_ALPHA, PRIOR_BETA, rule_priors
from archkg.kg.store import KGStore


@dataclass
class CalibrationResult:
    rule_id: str
    issues_updated: int
    prior_alpha: float
    prior_beta: float
    posterior_mean: float
    feedback_sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "issues_updated": self.issues_updated,
            "prior_alpha": round(self.prior_alpha, 4),
            "prior_beta": round(self.prior_beta, 4),
            "posterior_mean": round(self.posterior_mean, 4),
            "feedback_sample_size": self.feedback_sample_size,
        }


def calibrate_issue_confidence(
    store: KGStore,
    *,
    prior_alpha: float = PRIOR_ALPHA,
    prior_beta: float = PRIOR_BETA,
    dry_run: bool = False,
) -> list[CalibrationResult]:
    """Apply per-rule Beta-Binomial posterior to issue.confidence.

    Args:
        store: open KGStore.
        prior_alpha, prior_beta: Beta prior parameters (default Beta(1, 1)).
        dry_run: when True, compute results but do not UPDATE the KG.

    Returns one CalibrationResult per rule with feedback. Rules without
    any confirm/reject events are unchanged.
    """

    priors = rule_priors(store, prior_alpha=prior_alpha, prior_beta=prior_beta)
    results: list[CalibrationResult] = []
    for prior in priors:
        # Find rule.id for this rule_id
        row = store._conn.execute(
            "SELECT id FROM rule WHERE rule_id = ? ORDER BY version DESC LIMIT 1",
            (prior.rule_id,),
        ).fetchone()
        if row is None:
            continue
        rule_db_id = int(row["id"])
        if dry_run:
            count_row = store._conn.execute(
                "SELECT COUNT(*) AS n FROM issue WHERE rule_id = ?", (rule_db_id,)
            ).fetchone()
            updated = int(count_row["n"]) if count_row else 0
        else:
            cur = store._conn.execute(
                "UPDATE issue SET confidence = ? WHERE rule_id = ?",
                (prior.posterior_mean, rule_db_id),
            )
            updated = cur.rowcount or 0
        results.append(
            CalibrationResult(
                rule_id=prior.rule_id,
                issues_updated=updated,
                prior_alpha=prior.posterior_alpha,
                prior_beta=prior.posterior_beta,
                posterior_mean=prior.posterior_mean,
                feedback_sample_size=prior.sample_size,
            )
        )
    results.sort(key=lambda r: r.rule_id)
    return results


def calibrate_db(
    db_path: Path,
    *,
    prior_alpha: float = PRIOR_ALPHA,
    prior_beta: float = PRIOR_BETA,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Convenience wrapper that opens the KG and returns a summary dict."""

    with KGStore(db_path, create=False) as store:
        results = calibrate_issue_confidence(
            store,
            prior_alpha=prior_alpha,
            prior_beta=prior_beta,
            dry_run=dry_run,
        )
    issues_updated = sum(r.issues_updated for r in results)
    return {
        "db_path": str(db_path),
        "dry_run": dry_run,
        "rules_calibrated": len(results),
        "issues_updated": issues_updated,
        "results": [r.to_dict() for r in results],
    }


__all__ = ["CalibrationResult", "calibrate_db", "calibrate_issue_confidence"]
