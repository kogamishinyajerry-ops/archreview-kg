from __future__ import annotations

import importlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from archkg.schemas.ifc_validation import IfcIdsIssue, IfcIdsValidationReport

RAW_REPORT_FILENAME = "ids_report_raw.json"
VALIDATION_FILENAME = "ifc_validation.json"
IFC_ISSUES_FILENAME = "ifc_issues.json"


class IfcIdsDependencyError(RuntimeError):
    pass


def validate_ifc_ids(
    *,
    ifc_path: Path,
    ids_path: Path,
    out_dir: Path,
) -> IfcIdsValidationReport:
    """Run IfcTester-backed IDS validation and persist separate IFC artifacts."""

    ifcopenshell, ids_module, reporter_module = _load_dependencies()
    model = ifcopenshell.open(str(ifc_path))
    ids_spec = ids_module.open(str(ids_path))
    ids_spec.validate(model)
    reporter = reporter_module.Json(ids_spec)
    raw_report = _normalize_raw_report(reporter.report())

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_report_path = out_dir / RAW_REPORT_FILENAME
    issues_path = out_dir / IFC_ISSUES_FILENAME
    validation_path = out_dir / VALIDATION_FILENAME

    raw_report_path.write_text(
        json.dumps(raw_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    issues = map_ids_failures_to_issues(
        raw_report,
        source_ifc=ifc_path,
        source_ids=ids_path,
    )
    issues_path.write_text(
        json.dumps([issue.model_dump(mode="json") for issue in issues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = IfcIdsValidationReport(
        source_ifc=str(ifc_path),
        source_ids=str(ids_path),
        status="failed" if issues or _raw_report_failed(raw_report) else "passed",
        issue_count=len(issues),
        raw_report_path=str(raw_report_path),
        issues_path=str(issues_path),
    )
    validation_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def map_ids_failures_to_issues(
    raw_report: Mapping[str, Any],
    *,
    source_ifc: Path,
    source_ids: Path,
) -> list[IfcIdsIssue]:
    issues: list[IfcIdsIssue] = []
    for spec in _iter_mappings(raw_report.get("specifications")):
        spec_name = _first_string(spec, ("name", "description", "identifier"))
        for requirement in _iter_requirements(spec):
            if not _is_failed(requirement):
                continue
            requirement_text = (
                _first_string(
                    requirement,
                    ("description", "requirement", "label", "name", "facet_type", "sentence"),
                )
                or spec_name
                or "IDS requirement failed"
            )
            entities = list(_iter_failed_entities(requirement))
            if not entities:
                entities = [None]
            for entity in entities:
                issue_id = f"IFC-IDS-{len(issues) + 1:04d}"
                issues.append(
                    IfcIdsIssue(
                        issue_id=issue_id,
                        source_ifc=str(source_ifc),
                        source_ids=str(source_ids),
                        specification=spec_name,
                        requirement=requirement_text,
                        target_entity=_target_entity(entity),
                        actual_value=_entity_or_requirement_value(
                            entity, requirement, ("actual", "actual_value", "value")
                        ),
                        expected_value=_entity_or_requirement_value(
                            entity,
                            requirement,
                            ("expected", "expected_value", "restriction", "value"),
                        ),
                        message=_first_string(
                            requirement,
                            ("message", "reason", "failure", "error"),
                        ),
                    )
                )
    return issues


def _load_dependencies() -> tuple[Any, Any, Any]:
    try:
        ifcopenshell = importlib.import_module("ifcopenshell")
        ids_module = importlib.import_module("ifctester.ids")
        reporter_module = importlib.import_module("ifctester.reporter")
    except ModuleNotFoundError as exc:
        raise IfcIdsDependencyError(
            "IFC/IDS validation requires optional dependency modules "
            "`ifcopenshell` and `ifctester`. Install the openBIM stack for "
            "this lane, for example `pip install ifcopenshell`, then rerun "
            "`archkg ifc validate ...`. PDF review remains available without it."
        ) from exc
    for module, attr in (
        (ifcopenshell, "open"),
        (ids_module, "open"),
        (reporter_module, "Json"),
    ):
        if not hasattr(module, attr):
            raise IfcIdsDependencyError(
                "IFC/IDS validation found optional modules but their API is "
                f"missing `{module.__name__}.{attr}`. Check the installed "
                "IfcOpenShell/IfcTester version."
            )
    return ifcopenshell, ids_module, reporter_module


def _normalize_raw_report(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, str):
        loaded = json.loads(raw)
        if isinstance(loaded, Mapping):
            return loaded
        return {"report": loaded}
    if isinstance(raw, Mapping):
        return raw
    return {"report": repr(raw)}


def _iter_requirements(spec: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    for key in ("requirements", "facets", "checks", "applicability"):
        yield from _iter_mappings(spec.get(key))


def _iter_failed_entities(requirement: Mapping[str, Any]) -> Iterable[Any]:
    for key in ("failed_entities", "failures", "failedEntities", "failed_entities_info"):
        value = requirement.get(key)
        if value is None:
            continue
        if isinstance(value, Sequence) and not isinstance(value, str):
            yield from value
        else:
            yield value


def _iter_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for item in value:
            if isinstance(item, Mapping):
                yield item


def _is_failed(row: Mapping[str, Any]) -> bool:
    status = row.get("status")
    if isinstance(status, bool):
        return not status
    if isinstance(status, str):
        return status.lower() in {"false", "fail", "failed", "invalid", "non_compliant"}
    return bool(list(_iter_failed_entities(row)))


def _raw_report_failed(raw_report: Mapping[str, Any]) -> bool:
    status = raw_report.get("status")
    if isinstance(status, bool):
        return not status
    if isinstance(status, str):
        return status.lower() in {"false", "fail", "failed", "invalid", "non_compliant"}
    return False


def _first_string(row: Mapping[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        text = _stringify(value)
        if text:
            return text
    return None


def _target_entity(entity: Any) -> str | None:
    if isinstance(entity, Mapping):
        entity_type = _first_string(entity, ("type", "class", "ifc_class", "entity"))
        global_id = _first_string(entity, ("global_id", "globalId", "GlobalId", "id"))
        name = _first_string(entity, ("name", "Name"))
        if entity_type and global_id:
            return f"{entity_type}:{global_id}"
        return global_id or name or entity_type
    return _stringify(entity)


def _entity_or_requirement_value(
    entity: Any,
    requirement: Mapping[str, Any],
    keys: Iterable[str],
) -> str | None:
    if isinstance(entity, Mapping):
        found = _first_string(entity, keys)
        if found is not None:
            return found
    return _first_string(requirement, keys)


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value else None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
