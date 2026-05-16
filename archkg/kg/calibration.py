"""Per-rule confidence calibration report (M5.G).

Bins issues by predicted confidence and computes observed precision from
reviewer feedback events. Reports mean absolute deviation (MAD) of the
per-bin (predicted_mid - observed_precision) gap.

A well-calibrated detector has MAD < 0.08 (8% mean abs deviation).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archkg.kg.store import KGStore, default_db_path

DEFAULT_BINS: tuple[tuple[float, float], ...] = (
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.001),  # include 1.0
)


@dataclass
class CalibrationBin:
    lower: float
    upper: float
    midpoint: float
    sample_size: int
    confirmed: int
    rejected: int
    observed_precision: float
    abs_deviation: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "lower": self.lower,
            "upper": self.upper,
            "midpoint": round(self.midpoint, 3),
            "sample_size": self.sample_size,
            "confirmed": self.confirmed,
            "rejected": self.rejected,
            "observed_precision": round(self.observed_precision, 4),
            "abs_deviation": round(self.abs_deviation, 4),
        }


def build_calibration_report(
    db_path: Path | None = None,
    *,
    bins: Sequence[tuple[float, float]] = DEFAULT_BINS,
    min_samples_per_bin: int = 5,
) -> dict[str, Any]:
    """Build a reliability report.

    Bins with `sample_size < min_samples_per_bin` are reported but excluded
    from the MAD calculation to avoid noisy low-N influence.
    """

    db = db_path or default_db_path(Path.cwd())
    if not db.exists():
        return {
            "status": "no_kg_db",
            "db_path": str(db),
            "bins": [],
            "mean_abs_deviation": None,
        }

    with KGStore(db, create=False) as store:
        # For each issue with a confidence and any confirm/reject feedback,
        # join confidence to feedback outcome.
        rows = store._conn.execute(
            "SELECT i.confidence AS conf, "
            "SUM(CASE WHEN fe.event_type = 'confirm' THEN 1 ELSE 0 END) AS c, "
            "SUM(CASE WHEN fe.event_type = 'reject' THEN 1 ELSE 0 END) AS r "
            "FROM issue i "
            "LEFT JOIN feedback_event fe ON fe.issue_id = i.id "
            "WHERE i.confidence IS NOT NULL "
            "GROUP BY i.id "
            "HAVING c > 0 OR r > 0"
        ).fetchall()

    bin_results: list[CalibrationBin] = []
    deviations: list[float] = []
    for lower, upper in bins:
        sample = [row for row in rows if lower <= row["conf"] < upper]
        confirmed = sum(int(row["c"]) for row in sample)
        rejected = sum(int(row["r"]) for row in sample)
        total = confirmed + rejected
        midpoint = (lower + min(upper, 1.0)) / 2.0
        observed = (confirmed / total) if total > 0 else 0.0
        abs_dev = abs(midpoint - observed)
        bin_results.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                midpoint=midpoint,
                sample_size=total,
                confirmed=confirmed,
                rejected=rejected,
                observed_precision=observed,
                abs_deviation=abs_dev,
            )
        )
        if total >= min_samples_per_bin:
            deviations.append(abs_dev)

    if not deviations:
        return {
            "status": "no_bin_with_enough_samples",
            "db_path": str(db),
            "bins": [b.to_dict() for b in bin_results],
            "min_samples_per_bin": min_samples_per_bin,
            "mean_abs_deviation": None,
        }

    mad = sum(deviations) / len(deviations)
    return {
        "status": "ok",
        "db_path": str(db),
        "bins": [b.to_dict() for b in bin_results],
        "min_samples_per_bin": min_samples_per_bin,
        "mean_abs_deviation": round(mad, 4),
        "bins_used_for_mad": len(deviations),
    }


__all__ = [
    "DEFAULT_BINS",
    "CalibrationBin",
    "build_calibration_report",
]
