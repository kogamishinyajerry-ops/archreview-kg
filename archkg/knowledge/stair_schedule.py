"""Loader + validator for stair schedule YAML files (Phase 18-C)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from archkg.schemas import StairSchedule


class StairScheduleError(RuntimeError):
    """Raised when a stair schedule file is missing, malformed, or inconsistent."""


def load_stair_schedule(path: Path) -> StairSchedule:
    """Load and validate a stair schedule YAML file.

    Same shape as load_room_schedule: file must deserialize directly
    into the StairSchedule model. Cross-checking project_id against
    ProjectMeta is the caller's job.
    """
    if not path.exists():
        raise StairScheduleError(f"stair schedule file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise StairScheduleError(
            f"{path.name} must be a YAML mapping, got {type(raw).__name__}"
        )
    try:
        return StairSchedule.model_validate(raw)
    except ValidationError as exc:
        raise StairScheduleError(
            f"invalid stair schedule {path.name}: {exc}"
        ) from exc
