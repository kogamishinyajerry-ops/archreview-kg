from __future__ import annotations

import json
import re
from pathlib import Path

from archkg.schemas.rule_card import RuleCardTestCase, RuleScope
from archkg.schemas.rule_draft import DraftSourceClause, DraftThreshold, RuleCardDraft
from archkg.schemas.standard import StandardClause, ThresholdOp

_NUMERIC_WITH_UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:m\^2|m²|m|mm|层|个|%)",
    flags=re.IGNORECASE,
)


def author_rule_card_draft(clause: StandardClause) -> RuleCardDraft:
    """Create a review-only rule-card draft from one existing standard clause."""

    applies_to, required_inputs = _infer_entity_inputs(clause)
    threshold = DraftThreshold(
        op=clause.threshold_op,
        value=clause.threshold_value,
        unit=clause.unit,
        source="standard_clause_schema" if clause.threshold_value is not None else "missing",
    )
    ambiguity_notes: list[str] = []
    missing_evidence: list[str] = []

    numeric_mentions = _NUMERIC_WITH_UNIT_RE.findall(clause.clause_text)
    if len(numeric_mentions) > 1:
        ambiguity_notes.append(
            "Clause text contains multiple numeric thresholds; review rule split/branching before promotion."
        )
        missing_evidence.append("rule_split_or_branching")
    if clause.threshold_value is None or clause.threshold_op is None:
        missing_evidence.append("machine_readable_threshold")
    if applies_to is None or not required_inputs:
        missing_evidence.append("entity_input_mapping")

    logic = _proposed_logic(required_inputs, clause.threshold_op, clause.threshold_value)
    output_template = _proposed_output_template(clause, required_inputs)
    return RuleCardDraft(
        draft_id=f"DRAFT-RC-{_safe_id(clause.id)}",
        source_clause=DraftSourceClause(
            id=clause.id,
            source=clause.source,
            category=clause.category,
            clause_text=clause.clause_text,
            unit=clause.unit,
            threshold_value=clause.threshold_value,
            threshold_op=clause.threshold_op,
            paraphrase=clause.paraphrase,
        ),
        proposed_rule_id=f"RC-DRAFT-{_safe_id(clause.id)}",
        proposed_applies_to=applies_to,
        required_inputs=required_inputs,
        extracted_threshold=threshold,
        proposed_logic_expression=logic,
        proposed_output_template=output_template,
        proposed_tests=_proposed_tests(required_inputs, clause.threshold_op, clause.threshold_value),
        applicability={
            "building_type": list(clause.applies_to_building_type),
            "height_class": list(clause.applies_to_height_class or []),
        },
        ambiguity_notes=ambiguity_notes,
        missing_evidence=sorted(set(missing_evidence)),
    )


def write_rule_card_draft(draft: RuleCardDraft, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(draft.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _infer_entity_inputs(clause: StandardClause) -> tuple[RuleScope | None, list[str]]:
    text = clause.clause_text
    if "走廊" in text or "通廊" in text:
        return "Corridor", ["min_width_m"]
    if "户门" in text or "门" in text:
        return "Door", ["width_m"]
    if "楼梯" in text or "踏步" in text:
        if "扶手" in text:
            return "Stair", ["handrail_height_m"]
        if "宽度" in text:
            return "Stair", ["flight_width_m"]
        return "Stair", []
    if "净高" in text:
        return "Room", ["net_height_m"]
    if "使用面积" in text or "卧室" in text or "起居室" in text:
        return "Room", ["area_m2"]
    if "电梯" in text or "高度" in text or "层" in text:
        return "Project", ["floors", "height_m"]
    if "栏杆" in text or "窗台" in text:
        return "Dimension", ["height_m"]
    return None, []


def _proposed_logic(
    required_inputs: list[str],
    op: ThresholdOp | None,
    value: float | None,
) -> str | None:
    if not required_inputs or op is None or value is None:
        return None
    return f"{required_inputs[0]} {op} {_format_number(value)}"


def _proposed_output_template(
    clause: StandardClause,
    required_inputs: list[str],
) -> str | None:
    if not required_inputs:
        return None
    return (
        f"候选规则草稿, 来源 {clause.id}: "
        f"{{{required_inputs[0]}}} {clause.unit} 不满足条文阈值, 请人工复核。"
    )


def _proposed_tests(
    required_inputs: list[str],
    op: ThresholdOp | None,
    value: float | None,
) -> list[RuleCardTestCase]:
    if not required_inputs or op is None or value is None:
        return []
    key = required_inputs[0]
    if op in {">=", ">"}:
        fail_value = value * 0.9 if value else value - 1.0
        return [
            RuleCardTestCase(
                name="draft_edge_review",
                entity={key: value},
                expect_pass=op == ">=",
                note="Generated draft case; human review required.",
            ),
            RuleCardTestCase(
                name="draft_below_threshold",
                entity={key: fail_value},
                expect_pass=False,
                note="Generated draft case; human review required.",
            ),
        ]
    if op in {"<=", "<"}:
        fail_value = value * 1.1 if value else value + 1.0
        return [
            RuleCardTestCase(
                name="draft_edge_review",
                entity={key: value},
                expect_pass=op == "<=",
                note="Generated draft case; human review required.",
            ),
            RuleCardTestCase(
                name="draft_above_threshold",
                entity={key: fail_value},
                expect_pass=False,
                note="Generated draft case; human review required.",
            ),
        ]
    return []


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()


def _format_number(value: float) -> str:
    return f"{value:.2f}"
