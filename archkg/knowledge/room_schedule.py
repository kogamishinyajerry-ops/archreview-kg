"""Loader + validator for room schedule YAML files (Phase 18-B)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from archkg.schemas import RoomSchedule


class RoomScheduleError(RuntimeError):
    """Raised when a room schedule file is missing, malformed, or inconsistent."""


def load_room_schedule(path: Path) -> RoomSchedule:
    """Load and validate a room schedule YAML file.

    The file is expected to deserialize directly into the `RoomSchedule`
    model. We don't cross-check `project_id` against ProjectMeta here —
    that's the caller's responsibility because the meta isn't always
    loaded by then.
    """
    if not path.exists():
        raise RoomScheduleError(f"room schedule file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise RoomScheduleError(
            f"{path.name} must be a YAML mapping, got {type(raw).__name__}"
        )
    try:
        return RoomSchedule.model_validate(raw)
    except ValidationError as exc:
        raise RoomScheduleError(f"invalid room schedule {path.name}: {exc}") from exc
