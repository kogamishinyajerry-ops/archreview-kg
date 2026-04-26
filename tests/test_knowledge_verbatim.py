"""Tests for the Phase 14 verbatim audit lane.

Two concerns:
1. The audit module itself works on representative inputs (PDF resolution,
   clause-body extraction, self-id stripping).
2. The Phase 14 verbatim restorations stay restored — i.e. nobody silently
   re-trims GB50352-6.7.3 / 5.5.27 / 5.5.29 / 5.5.31 / 3.5.3 back to their
   pre-Phase-14 (paraphrase=true, branches dropped) state.
"""

from __future__ import annotations

from pathlib import Path

from archkg.knowledge.loader import load_standards
from archkg.knowledge.verbatim import (
    _SOURCE_TO_PDF,
    _resolve_pdf,
    _strip_self_id_numbers,
    audit_paraphrased,
)

_STANDARDS_ROOT = Path(__file__).resolve().parent.parent / "standards_raw"


def test_strip_self_id_drops_only_leaf() -> None:
    """5.5.27 should drop 27 but keep 5.5 — the parent overlaps with
    cross-references like "第 5.5.23 条" and stripping it would mute
    legitimate coverage signals on those references."""
    out = _strip_self_id_numbers({5.5, 27.0, 33.0, 21.0}, "GB50016-5.5.27")
    assert out == {5.5, 33.0, 21.0}


def test_resolve_pdf_known_sources() -> None:
    for source, name in _SOURCE_TO_PDF.items():
        p = _resolve_pdf(source, _STANDARDS_ROOT)
        assert p is not None, f"{source} → {name} not found at {_STANDARDS_ROOT}"
        assert p.name == name


def test_audit_returns_findings_for_each_paraphrased_clause() -> None:
    standards = load_standards()
    findings = audit_paraphrased(standards, _STANDARDS_ROOT)
    paraphrase_ids = {c.id for c in standards if c.paraphrase}
    audited_ids = {f.clause_id for f in findings}
    assert audited_ids == paraphrase_ids
    # Sanity: every audit produced *some* PDF body — boundary detection is
    # approximate but never empty for the 5 known paraphrased clauses.
    for f in findings:
        assert f.pdf_body_chars > 0, f"{f.clause_id} extracted no PDF body"


def test_phase14_verbatim_restorations_locked_in() -> None:
    """Lock-in: numbers/phrases Phase 14 restored to clause_text after
    Codex caught the GB50352-6.7.3 paraphrase-loses-branches bug must
    keep appearing in the yaml so the harness doesn't silently regress.

    The point isn't full PDF parity — it's preserving the substantive
    branches that downstream rule cards (or future rule cards) depend on.
    """
    standards = load_standards()
    by_id = {c.id: c for c in standards}

    # (clause_id, must-appear substring, why it was added in Phase 14)
    expectations: list[tuple[str, str, str]] = [
        # GB 50352-6.7.3: Codex round-2 P1 fix — 1.1m and 1.2m branches restored.
        ("GB50352-6.7.3", "1.05", "<24m branch"),
        ("GB50352-6.7.3", "1.1", "≥24m branch (was silently dropped pre-Phase-14)"),
        ("GB50352-6.7.3", "1.2", "上人屋面/公共建筑临开敞中庭 branch"),
        ("GB50352-6.7.3", "24.0", "临空高度 threshold"),

        # GB 50016-5.5.27: 乙级防火门 exemptions restored.
        ("GB50016-5.5.27", "21", "敞开/封闭 cutoff"),
        ("GB50016-5.5.27", "33", "封闭/防烟 cutoff"),
        ("GB50016-5.5.27", "乙级防火门", "exemption branch"),
        ("GB50016-5.5.27", "电梯井", "electrical-shaft adjacency exemption"),

        # GB 50016-5.5.29: full table cells restored beyond the original 40m cell.
        ("GB50016-5.5.29", "40", "一二级 + 单多层 + 两个安全出口之间"),
        ("GB50016-5.5.29", "35", "三级 + 单多层 cell"),
        ("GB50016-5.5.29", "25", "四级 + 单多层 cell"),
        ("GB50016-5.5.29", "22", "袋形走道 一二级 单多层"),
        ("GB50016-5.5.29", "20", "袋形走道 三级 单多层 / 高层 cell"),
        ("GB50016-5.5.29", "袋形走道", "table branch label"),
        ("GB50016-5.5.29", "敞开式外廊", "注 1 adjustment"),
        ("GB50016-5.5.29", "1.50", "注 4 跃廊式 multiplier"),
        ("GB50016-5.5.29", "跃廊式", "注 4 trailing note about 跃廊式住宅 (Codex P14 P2 lock)"),

        # GB 50016-5.5.31: cross-reference to §5.5.23 restored.
        ("GB50016-5.5.31", "100", "避难层 height threshold"),
        ("GB50016-5.5.31", "5.5.23", "cross-reference to 避难层 details clause"),

        # GB 50763-3.5.3: §1 弹簧门 + §4-§7 dimensional branches restored.
        ("GB50763-3.5.3", "1.00", "§2 自动门 net width"),
        ("GB50763-3.5.3", "800", "§3 平开/推拉/折叠门 net width (mm)"),
        ("GB50763-3.5.3", "900", "§3 有条件时建议值 / §6 把手高度"),
        ("GB50763-3.5.3", "1.50", "§4 轮椅回转直径"),
        ("GB50763-3.5.3", "400", "§5 把手墙面宽度 (mm)"),
        ("GB50763-3.5.3", "350", "§6 护门板高度 (mm)"),
        ("GB50763-3.5.3", "弹簧门", "§1 forbidden door type"),
    ]

    failures: list[str] = []
    for cid, needle, reason in expectations:
        clause = by_id.get(cid)
        if clause is None:
            failures.append(f"{cid}: clause missing from standards.yaml")
            continue
        if needle not in clause.clause_text:
            failures.append(f"{cid}: missing '{needle}' ({reason})")
    assert not failures, "Phase 14 verbatim drift: " + "; ".join(failures)


def test_rc_door_to_exit_40m_locked_to_correct_branch() -> None:
    """Codex Phase 14 P2: GB50016-5.5.29 now carries the full table (40/35/25/22/20),
    so a regression where RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB drifts from the
    一二级 + 单多层 + 两个安全出口之间 cell (40m) to a different cell (35m, 25m,
    22m, 20m) would still pass fidelity check — every number is now in the
    clause text. Lock the rule's intended branch to its narrow table cell.
    """
    from archkg.knowledge.loader import load_rules

    standards = load_standards()
    rules = load_rules(standards=standards)
    target = next((r for r in rules if r.id == "RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB"), None)
    assert target is not None, "RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB missing — was it deleted?"

    template = target.output_template
    # Must mention the cell threshold the rule is asserting.
    assert "40 m" in template, "rule must assert the 40 m branch threshold"
    # Must explicitly name the table branch it covers (一/二级 + 单/多层 +
    # 两个安全出口之间) so a future maintainer can't silently widen it.
    assert "一/二级" in template or "一二级" in template, (
        "rule must name the fire-class branch (一二级) it covers"
    )
    assert "单/多层" in template or "单多层" in template, (
        "rule must name the height-class branch (单多层) it covers"
    )
    # The narrow-rule scope marker (other branches need their own rule cards).
    assert any(s in template for s in ("仅覆盖", "本规则仅", "narrow")), (
        "rule template must signal partial coverage of 表 5.5.29"
    )
