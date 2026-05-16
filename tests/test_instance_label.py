"""Tests for archkg.kg.instance_label (M7.W5 per-instance reviewer labels)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archkg.kg.instance_label import (
    SYNTHETIC_PREFIXES,
    VALID_REVIEWER_CLASSES,
    batch_import,
    classify_reviewer,
    label_provenance_counts,
    list_instance_labels,
    record_instance_label,
)
from archkg.kg.store import KGStore

# ---- Fixtures ----------------------------------------------------------


@pytest.fixture()
def fresh_kg(tmp_path: Path) -> Path:
    """Build a tiny KG with 1 project / 1 run / 3 issues."""

    db = tmp_path / "kg.db"
    now = "2026-05-16T00:00:00Z"
    with KGStore(db, create=True) as store:
        store._conn.execute(
            "INSERT INTO project(slug, name, created_at) VALUES (?, ?, ?)",
            ("test-proj", "Test Project", now),
        )
        pid = store._conn.execute("SELECT id FROM project WHERE slug='test-proj'").fetchone()["id"]
        store._conn.execute(
            "INSERT INTO drawing(project_id, source_path, page_count, created_at) VALUES (?, ?, ?, ?)",
            (pid, "test.pdf", 1, now),
        )
        did = store._conn.execute("SELECT id FROM drawing").fetchone()["id"]
        store._conn.execute(
            "INSERT INTO run(project_id, drawing_id, run_dir, ingested_at) VALUES (?, ?, ?, ?)",
            (pid, did, "out/test", now),
        )
        rid = store._conn.execute("SELECT id FROM run").fetchone()["id"]
        store._conn.execute("INSERT INTO rule(rule_id) VALUES (?)", ("RC-TEST",))
        rule_pk = store._conn.execute("SELECT id FROM rule").fetchone()["id"]
        for sid in ("a", "b", "c"):
            store._conn.execute(
                "INSERT INTO issue(run_id, rule_id, source_issue_id, status, severity, message) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (rid, rule_pk, f"ISS-{sid}", "candidate", "error", f"test issue {sid}"),
            )
    return db


# ---- classify_reviewer -------------------------------------------------


def test_synthetic_prefixes_resolve_to_synthetic() -> None:
    for prefix in SYNTHETIC_PREFIXES:
        assert classify_reviewer(prefix) == "synthetic"
        assert classify_reviewer(f"{prefix}-something") == "synthetic"


def test_unknown_reviewer_defaults_to_project_internal() -> None:
    assert classify_reviewer("jerry-maintainer") == "project_internal"
    assert classify_reviewer("alice@example.com") == "project_internal"


def test_explicit_class_overrides_inference() -> None:
    assert classify_reviewer("alice", "independent_third_party") == "independent_third_party"
    assert classify_reviewer("alice", "synthetic") == "synthetic"


def test_unknown_class_raises() -> None:
    with pytest.raises(ValueError, match="unknown reviewer_class"):
        classify_reviewer("alice", "weird-class")  # type: ignore[arg-type]


# ---- record_instance_label --------------------------------------------


def test_record_creates_event_with_instance_label_payload(fresh_kg: Path) -> None:
    with KGStore(fresh_kg, create=False) as store:
        issue_id = store._conn.execute("SELECT id FROM issue WHERE source_issue_id='ISS-a'").fetchone()["id"]
        fb = record_instance_label(
            store,
            issue_id=issue_id,
            reviewer_id="jerry-maintainer",
            event_type="confirm",
            note="dogfooding",
        )
        row = store._conn.execute("SELECT payload_json FROM feedback_event WHERE id=?", (fb,)).fetchone()
        payload = json.loads(row["payload_json"])
        assert payload["instance_label"] is True
        assert payload["reviewer_class"] == "project_internal"
        assert payload["note"] == "dogfooding"


def test_synthetic_reviewer_cannot_be_elevated_to_independent(fresh_kg: Path) -> None:
    """Anti-loophole: claiming demo-reviewer-* as independent must downgrade."""
    with KGStore(fresh_kg, create=False) as store:
        issue_id = store._conn.execute("SELECT id FROM issue WHERE source_issue_id='ISS-a'").fetchone()["id"]
        fb = record_instance_label(
            store,
            issue_id=issue_id,
            reviewer_id="demo-reviewer-evil",
            event_type="confirm",
            reviewer_class="independent_third_party",  # attempted elevation
        )
        payload = json.loads(
            store._conn.execute("SELECT payload_json FROM feedback_event WHERE id=?", (fb,)).fetchone()[
                "payload_json"
            ]
        )
        assert payload["reviewer_class"] == "synthetic"  # silently downgraded


def test_extra_payload_cannot_override_trust_fields(fresh_kg: Path) -> None:
    """A caller passing extra_payload={'reviewer_class': 'independent'} must be ignored."""
    with KGStore(fresh_kg, create=False) as store:
        issue_id = store._conn.execute("SELECT id FROM issue WHERE source_issue_id='ISS-a'").fetchone()["id"]
        fb = record_instance_label(
            store,
            issue_id=issue_id,
            reviewer_id="alice",
            event_type="confirm",
            extra_payload={"reviewer_class": "independent_third_party", "color": "red"},
        )
        payload = json.loads(
            store._conn.execute("SELECT payload_json FROM feedback_event WHERE id=?", (fb,)).fetchone()[
                "payload_json"
            ]
        )
        assert payload["reviewer_class"] == "project_internal"  # NOT overridden
        assert payload["color"] == "red"  # but other fields pass through


# ---- list_instance_labels + provenance counts ------------------------


def test_list_and_counts_with_mixed_classes(fresh_kg: Path) -> None:
    with KGStore(fresh_kg, create=False) as store:
        issues = [
            r["id"]
            for r in store._conn.execute("SELECT id FROM issue ORDER BY id").fetchall()
        ]
        # 2 project_internal, 1 independent
        record_instance_label(store, issue_id=issues[0], reviewer_id="jerry", event_type="confirm")
        record_instance_label(store, issue_id=issues[1], reviewer_id="alice-pm", event_type="reject")
        record_instance_label(
            store,
            issue_id=issues[2],
            reviewer_id="external-firm-001",
            event_type="confirm",
            reviewer_class="independent_third_party",
        )
        # Also a regular feedback event (no instance_label) — should NOT count
        from archkg.kg.feedback import add_feedback

        add_feedback(store, issue_id=issues[0], reviewer_id="smoke-runner", event_type="confirm")

        events = list_instance_labels(store)
        assert len(events) == 3
        assert {e.reviewer_id for e in events} == {"jerry", "alice-pm", "external-firm-001"}

        counts = label_provenance_counts(store)
        assert counts["instance_label_event_count"] == 3
        assert counts["project_internal_reviewer_count"] == 2
        assert counts["independent_third_party_reviewer_count"] == 1
        assert counts["any_independent_review"] is True


def test_zero_labels_returns_zero_counts(fresh_kg: Path) -> None:
    with KGStore(fresh_kg, create=False) as store:
        counts = label_provenance_counts(store)
    assert counts["instance_label_event_count"] == 0
    assert counts["project_internal_reviewer_count"] == 0
    assert counts["independent_third_party_reviewer_count"] == 0
    assert counts["any_independent_review"] is False


# ---- batch_import -----------------------------------------------------


def test_batch_import_records_all_rows(fresh_kg: Path) -> None:
    with KGStore(fresh_kg, create=False) as store:
        issues = [r["id"] for r in store._conn.execute("SELECT id FROM issue").fetchall()]
        rows = [
            {"issue_id": issues[0], "reviewer_id": "alice", "event_type": "confirm"},
            {"issue_id": issues[1], "reviewer_id": "bob", "event_type": "reject",
             "reviewer_class": "project_internal", "note": "see plan p.4"},
        ]
        fb_ids = batch_import(store, rows)
    assert len(fb_ids) == 2


def test_batch_import_rejects_missing_keys(fresh_kg: Path) -> None:
    with KGStore(fresh_kg, create=False) as store:
        with pytest.raises(ValueError, match="missing required key"):
            batch_import(store, [{"issue_id": 1, "reviewer_id": "alice"}])  # no event_type


def test_batch_import_rejects_unknown_class(fresh_kg: Path) -> None:
    with KGStore(fresh_kg, create=False) as store:
        with pytest.raises(ValueError, match="unknown reviewer_class"):
            batch_import(store, [{"issue_id": 1, "reviewer_id": "a", "event_type": "confirm",
                                   "reviewer_class": "weird"}])


def test_valid_classes_tuple_is_complete() -> None:
    assert set(VALID_REVIEWER_CLASSES) == {"synthetic", "project_internal", "independent_third_party"}
