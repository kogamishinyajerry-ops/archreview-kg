"""Per-rule precision/recall measurement from the KG (M5.E).

Precision is computed from reviewer feedback events:
    TP = number of `confirm` events on issues of that rule.
    FP = number of `reject` events.
    precision = TP / (TP + FP).

Recall requires ground truth on missed issues. The benchmark suite
provides this only for cases that supply an `expected.json` inventory; for
rules without that signal we report recall as `null` and exclude them from
the weighted recall aggregate.

When the benchmark inventory tracks per-rule expected counts, we use:

    FN = max(0, expected_count_for_rule - detected_count_for_rule)
    recall = TP / (TP + FN)  if (TP + FN) > 0 else None

To avoid silently overstating quality, rules with zero confirmed feedback
also have recall null; the aggregate only includes rules where TP > 0
AND ground-truth FN is known.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archkg.kg.store import KGStore, default_db_path


@dataclass
class PerRuleStats:
    rule_id: str
    tp: int
    fp: int
    detected: int  # total issues for this rule in KG, regardless of feedback
    expected: int | None
    precision: float | None
    recall: float | None
    sample_size: int  # TP + FP (precision sample)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "tp": self.tp,
            "fp": self.fp,
            "detected": self.detected,
            "expected": self.expected,
            "precision": (round(self.precision, 4) if self.precision is not None else None),
            "recall": (round(self.recall, 4) if self.recall is not None else None),
            "sample_size": self.sample_size,
        }


def _load_expected_counts(repo: Path) -> dict[str, int]:
    """Aggregate per-rule expected counts across benchmark expect files.

    Returns a flat {rule_id: expected_count} dict; counts are summed across
    benchmark cases that supply this evidence.
    """

    suite_root = repo / "samples" / "understanding_benchmarks"
    out: dict[str, int] = {}
    if not suite_root.is_dir():
        return out
    # Scan all JSON files referenced as `expect` artifacts; this covers both
    # the `*_expected.json` convention and the legacy bare-name fixtures
    # (e.g. sample_clean_full.json) declared in suite_manifest.json.
    candidates: list[Path] = list(suite_root.rglob("*_expected.json"))
    manifest_path = suite_root / "suite_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for case in manifest.get("cases", []) or []:
                expect = case.get("expect")
                if isinstance(expect, str):
                    candidate = suite_root / expect
                    if candidate.exists() and candidate not in candidates:
                        candidates.append(candidate)
        except (json.JSONDecodeError, OSError):
            pass
    for expect_path in candidates:
        try:
            data = json.loads(expect_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, Mapping):
            continue
        rule_counts = data.get("expected_rule_counts") or data.get("rule_counts")
        if isinstance(rule_counts, Mapping):
            for rid, count in rule_counts.items():
                # Skip leading-underscore meta keys like "_note".
                if isinstance(rid, str) and rid.startswith("_"):
                    continue
                if isinstance(count, int):
                    out[rid] = out.get(rid, 0) + count
    return out


def per_rule_quality(
    db_path: Path | None = None,
    *,
    repo: Path | None = None,
) -> dict[str, Any]:
    db = db_path or default_db_path(Path.cwd())
    repo_root = repo or Path.cwd()
    if not db.exists():
        return {"status": "no_kg_db", "rules": []}
    expected_counts = _load_expected_counts(repo_root)

    with KGStore(db, create=False) as store:
        rows = store._conn.execute(
            "SELECT r.rule_id AS rid, "
            "COUNT(i.id) AS detected, "
            "SUM(CASE WHEN fe.event_type = 'confirm' THEN 1 ELSE 0 END) AS tp, "
            "SUM(CASE WHEN fe.event_type = 'reject' THEN 1 ELSE 0 END) AS fp "
            "FROM rule r "
            "LEFT JOIN issue i ON i.rule_id = r.id "
            "LEFT JOIN feedback_event fe ON fe.issue_id = i.id "
            "GROUP BY r.rule_id "
            "HAVING detected > 0"
        ).fetchall()

    per_rule: list[PerRuleStats] = []
    for row in rows:
        rid = row["rid"]
        tp = int(row["tp"] or 0)
        fp = int(row["fp"] or 0)
        detected = int(row["detected"] or 0)
        expected = expected_counts.get(rid)
        # Precision: defined only when we have any labeled feedback.
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else None
        # Recall: STRICTLY requires a benchmark `expected_rule_counts` value
        # for the rule. We intentionally do NOT fall back to detected-based
        # estimates because that conflates precision with recall (tp / detected
        # collapses to 1.0 when feedback labels every detection). Rules
        # without expected counts have recall=None and are excluded from
        # the weighted recall aggregate by the caller.
        recall: float | None
        if expected is None:
            recall = None
        else:
            fn = max(0, expected - detected)
            denom = tp + fn
            recall = (tp / denom) if denom > 0 else None
        per_rule.append(
            PerRuleStats(
                rule_id=rid,
                tp=tp,
                fp=fp,
                detected=detected,
                expected=expected,
                precision=precision,
                recall=recall,
                sample_size=tp + fp,
            )
        )

    # Weighted aggregates
    precision_pool = [s for s in per_rule if s.precision is not None and s.sample_size > 0]
    recall_pool = [s for s in per_rule if s.recall is not None and s.tp > 0]
    if precision_pool:
        denom = sum(s.sample_size for s in precision_pool)
        weighted_precision = sum(s.precision * s.sample_size for s in precision_pool if s.precision is not None) / denom
    else:
        weighted_precision = None
    if recall_pool:
        denom = sum(s.tp for s in recall_pool)
        weighted_recall = sum(s.recall * s.tp for s in recall_pool if s.recall is not None) / denom
    else:
        weighted_recall = None

    return {
        "status": "ok",
        "rules": [s.to_dict() for s in per_rule],
        "weighted_precision": (round(weighted_precision, 4) if weighted_precision is not None else None),
        "weighted_recall": (round(weighted_recall, 4) if weighted_recall is not None else None),
        "rules_with_precision": len(precision_pool),
        "rules_with_recall": len(recall_pool),
    }


__all__ = ["PerRuleStats", "per_rule_quality"]
