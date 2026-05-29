from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IfcIdsValidationStatus = Literal["passed", "failed"]


class IfcIdsIssue(BaseModel):
    """Issue-like evidence row mapped from an IDS validation failure."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    source_ifc: str
    source_ids: str
    specification: str | None = None
    requirement: str
    target_entity: str | None = None
    actual_value: str | None = None
    expected_value: str | None = None
    message: str | None = None


class IfcIdsValidationReport(BaseModel):
    """Summary artifact for the optional IFC/IDS side lane."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ifc_ids_validation.v1"] = "ifc_ids_validation.v1"
    source_ifc: str
    source_ids: str
    status: IfcIdsValidationStatus
    issue_count: int = Field(..., ge=0)
    raw_report_path: str
    issues_path: str
