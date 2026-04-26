"""Tests for the numeric-fidelity checker (Phase 13 pilot).

The checker catches the bug class that survived self-consistency tests in
Phase 11-C: a rule's logic_expression carries a numeric threshold that the
source clause never mentions (typically because the threshold was copy-pasted
from a different clause's pattern).
"""

from __future__ import annotations

from archkg.knowledge.fidelity import (
    FidelityFinding,
    _numbers_from_clause_text,
    _numbers_from_python_expr,
    _numbers_from_template,
    check_all,
    check_rule_fidelity,
)
from archkg.knowledge.loader import load_rules, load_standards
from archkg.schemas import RuleCard, RuleCardTestCase, StandardClause


def test_numbers_from_python_expr_skips_booleans() -> None:
    nums = _numbers_from_python_expr("(floors is None or floors < 7) and (height_m <= 16.0)")
    assert nums == {7.0, 16.0}


def test_numbers_from_clause_text_extracts_arabic_and_chinese_floor_numerals() -> None:
    nums = _numbers_from_clause_text("七层及七层以上住宅或入口距地高度超过 16 m 的住宅必须设置电梯。")
    assert {7.0, 16.0} <= nums


def test_numbers_from_template_strips_clause_citations() -> None:
    """Codex P11-C nit: GB-style citations and 表 X.Y refs aren't thresholds."""
    nums = _numbers_from_template(
        "项目高度 {height_m} m，按 GB 50016-5.5.27 应采用封闭楼梯间。"
    )
    # 5.5.27 from the citation must NOT appear; nor 50016
    assert 5.5 not in nums
    assert 50016 not in nums
    assert 27 not in nums


def test_numbers_from_template_keeps_real_thresholds() -> None:
    nums = _numbers_from_template(
        "户门净宽 {width_m:.2f} m，小于规范要求的 0.90 m。"
    )
    assert 0.9 in nums


def _clause(cid: str, text: str) -> StandardClause:
    return StandardClause(
        id=cid,
        source="GB TEST",
        clause_text=text,
        unit="m",
    )


def _rule(rid: str, source_ids: list[str], expr: str, template: str = "") -> RuleCard:
    return RuleCard(
        id=rid,
        source_clause_ids=source_ids,
        applies_to="Project",
        inputs=["height_m"],
        logic_expression=expr,
        output_template=template,
        test_cases=[
            RuleCardTestCase(name="t", entity={"height_m": 0.0}, expect_pass=True),
        ],
    )


def test_check_rule_fidelity_clean_rule_no_findings() -> None:
    clause = _clause("X-1", "高度大于 16 m 的住宅必须设置电梯。")
    rule = _rule("RC-X", ["X-1"], "height_m is None or height_m <= 16.0")
    findings = check_rule_fidelity(rule, {clause.id: clause})
    assert findings == []


def test_check_rule_fidelity_catches_phase11c_bug_class() -> None:
    """The exact bug Codex caught: rule has a number the source clause doesn't."""
    clause = _clause("X-1", "七层及七层以上的住宅，应做无障碍设计。")  # mentions 7 only
    rule = _rule("RC-DRIFT", ["X-1"], "(floors is None or floors < 7) and (height_m is None or height_m <= 16.0)")
    # We pass through inputs=["height_m"] for the helper but the expression also references floors.
    # The checker only inspects the expression for numbers, so this test still works.
    findings = check_rule_fidelity(rule, {clause.id: clause})
    error_findings = [f for f in findings if f.severity == "error"]
    assert any(f.kind == "numeric-drift-expression" and "16.0" in f.message for f in error_findings)


def test_check_rule_fidelity_template_drift_is_warning_not_error() -> None:
    clause = _clause("X-1", "户门净宽不应小于 0.90 m。")
    rule = _rule(
        "RC-T",
        ["X-1"],
        "width_m >= 0.90",
        template="门宽不应小于 1.20 m。",  # 1.20 isn't in clause OR expression
    )
    findings = check_rule_fidelity(rule, {clause.id: clause})
    template_findings = [f for f in findings if f.kind == "numeric-drift-template"]
    assert len(template_findings) == 1
    assert template_findings[0].severity == "warning"
    assert "1.2" in template_findings[0].message or "1.20" in template_findings[0].message


def test_check_rule_fidelity_multiclause_union() -> None:
    """A rule citing two source clauses can pull thresholds from EITHER."""
    c1 = _clause("X-1", "电梯不应紧邻卧室布置。")  # no numbers
    c2 = _clause("X-2", "七层及七层以上必须设置电梯，超过 16 m 同样必须设置。")
    rule = _rule("RC-MULTI", ["X-1", "X-2"], "(floors is None or floors < 7) and (height_m is None or height_m <= 16.0)")
    findings = check_rule_fidelity(rule, {c1.id: c1, c2.id: c2})
    error_findings = [f for f in findings if f.severity == "error"]
    assert error_findings == [], f"expected union to cover both 7 and 16; got {error_findings}"


def test_check_rule_fidelity_skips_structural_zero_only() -> None:
    """Codex P13-pilot P2 #2: only 0.0 is auto-suppressed; 1.0 stays checked."""
    clause = _clause("X-1", "建筑用房的室内净高不应小于 2.0 m。")
    rule = _rule("RC-S", ["X-1"], "ceiling_m >= 2.0 and ceiling_m > 0")
    findings = check_rule_fidelity(rule, {clause.id: clause})
    assert findings == []


def test_check_rule_fidelity_does_not_hide_one_as_real_threshold() -> None:
    """Codex P13-pilot P2 #2 regression: a rule with `x >= 1.0` against a
    clause that doesn't mention 1.0 must surface as drift, not silently pass."""
    clause = _clause("X-2", "走廊净宽不应小于 0.90 m。")  # no '1' in text
    rule = _rule("RC-DRIFT-1", ["X-2"], "width_m >= 1.0")
    findings = check_rule_fidelity(rule, {clause.id: clause})
    error_findings = [f for f in findings if f.severity == "error"]
    assert any("1.0" in f.message for f in error_findings)


def test_check_rule_fidelity_strips_clause_list_markers() -> None:
    """Codex P13-pilot P2 #1: list enumerator markers like "1．" / "2．" inside
    a clause shouldn't pollute the threshold set, otherwise a future rule
    drifting to `4.0` would silently pass against a 4-item enumerated clause."""
    clause = _clause(
        "X-3",
        "应做无障碍设计：1．建筑入口；2．入口平台；3．候梯厅；4．公共走道。",
    )
    nums = _numbers_from_clause_text(clause.clause_text)
    # Enumerator markers 1/2/3/4 must NOT contaminate the threshold set
    for marker in (1.0, 2.0, 3.0, 4.0):
        assert marker not in nums, f"list marker {marker} leaked into clause numbers: {nums}"


def test_check_rule_fidelity_strips_inline_table_citation() -> None:
    """Codex P13-pilot P2 #1: '表 5.5.29' inside clause text isn't a threshold."""
    clause = _clause("X-4", "应符合 GB 50016 表 5.5.29 的规定，不应大于 40 m。")
    nums = _numbers_from_clause_text(clause.clause_text)
    assert 40.0 in nums  # the real threshold
    assert 50016.0 not in nums  # citation noise
    assert 5.5 not in nums  # table number
    assert 29.0 not in nums  # table number


def test_check_rule_fidelity_fraction_is_quotient() -> None:
    """Codex P13-pilot P2 #1: '1/3' is a single ratio, not {1, 3}."""
    nums = _numbers_from_clause_text("其面积不应大于室内使用面积的 1/3。")
    assert 1.0 not in nums
    assert 3.0 not in nums
    assert any(abs(n - 1.0 / 3.0) < 1e-9 for n in nums)


def test_packaged_rules_pass_numeric_fidelity_check() -> None:
    """Integration gate: every shipped rule card must survive the numeric
    drift check. Phase 11-C.1 demonstrated why this matters; making it a
    test prevents regression as new rules are added (manually or by LLM)."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    findings = check_all(rules, standards)
    errors = [f for f in findings if f.severity == "error"]
    assert errors == [], (
        "packaged rule cards must have zero numeric-fidelity errors. "
        f"Found: {[f for f in errors]}"
    )


def test_finding_dataclass_is_frozen() -> None:
    f = FidelityFinding(
        severity="error", rule_id="X", clause_id="Y", kind="z", message="m"
    )
    try:
        f.severity = "warning"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("FidelityFinding should be frozen")


def test_clause_text_mm_normalization_emits_meter_equivalent() -> None:
    """Phase 17: GB50763-3.5.3 carries '800 mm' for swing-door minimum width;
    a rule expression naturally uses 0.80 m. fidelity must accept both forms."""
    from archkg.knowledge.fidelity import _numbers_from_clause_text
    nums = _numbers_from_clause_text("折叠门开启后的通行净宽度不应小于 800 mm。")
    assert 800.0 in nums  # raw value still present
    assert 0.8 in nums    # m-converted equivalent emitted by Phase 17 normalization


def test_clause_text_cm_normalization_emits_meter_equivalent() -> None:
    from archkg.knowledge.fidelity import _numbers_from_clause_text
    nums = _numbers_from_clause_text("台阶高度 15 cm，宽度 30 cm。")
    assert 15.0 in nums
    assert 30.0 in nums
    assert 0.15 in nums
    assert 0.30 in nums


def test_template_mm_normalization_matches_clause() -> None:
    """Symmetric: rule output_template mentioning '800 mm' must also unlock
    the 0.80 m equivalent into the template number set."""
    from archkg.knowledge.fidelity import _numbers_from_template
    nums = _numbers_from_template("门净宽 {width_m} m，小于 800 mm。")
    assert 800.0 in nums
    assert 0.8 in nums
