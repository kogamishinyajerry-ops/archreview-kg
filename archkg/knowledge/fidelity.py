"""Static regulatory-fidelity checker for rule cards.

Phase 11-C.1 made it concrete that self-consistency tests aren't enough:
RC-ACCESSIBLE-RESIDENTIAL-7F encoded a `height_m <= 16.0` gate that the
source clause GB50096-6.6.1 ("七层及七层以上") never mentions, and the
self-consistency test_rule_test_cases_match_engine_decision happily passed
because the test cases agreed with the (wrong) expression.

The fix is an independent check that compares the rule's logic against
the source clause's text. This module ships the lightweight version:

  - extract numeric thresholds from the rule's logic_expression and
    output_template,
  - extract numbers from each source clause's clause_text (Arabic + 一/二/.../十
    when used as floor counts),
  - flag any rule-side number that doesn't appear (or have a close
    floating-point match) in any of its source clauses.

What this DOES catch:
  - Copy-pasted thresholds from a different clause (the P11-C.1 bug).
  - Typos like 1.10 written as 11.0.
  - Rule output_template promising a threshold the clause doesn't carry.

What this does NOT catch (deferred to a future LLM-graded check):
  - Threshold-direction bugs (>= vs <= when the clause says "不应小于").
  - Wrong unit (m vs mm).
  - Compound logic that's structurally wrong even though all numbers match.
  - Missing applicability gates that the clause requires.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass

from archkg.schemas import RuleCard, StandardClause

_CN_FLOOR_NUMERAL = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
_NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?")
_FLOOR_PHRASE = re.compile(r"([一二三四五六七八九十])层")
# Clause citation patterns we strip before counting numbers in templates so
# that "GB 50096-6.4.1" doesn't pollute the number set with {50096, 6.4, 1}.
_CITATION = re.compile(r"GB\s*\d{4,5}(?:[\s\-－–]\d+)?(?:\.\d+){0,3}")
_TABLE_REF = re.compile(r"表\s*\d+(?:\.\d+){0,3}")
# List-enumerator markers like "1．" / "2．" / "1)" — these number clauses
# internally, not regulatory thresholds. Match digit + marker followed by
# whitespace OR a CJK char (to catch "1．建筑入口" with no space). Codex
# P13-pilot P2 #1 fix.
_LIST_MARKER = re.compile(r"(?<![\d.])\d+[．）)](?=[\s一-鿿])")
# Fractions like "1/3" — treat as a single value (the float quotient) so
# the numerator/denominator don't pollute the number set independently.
_FRACTION = re.compile(r"(\d+)\s*/\s*(\d+)")


@dataclass(frozen=True)
class FidelityFinding:
    severity: str  # "error" | "warning" | "info"
    rule_id: str
    clause_id: str
    kind: str  # short tag, e.g. "numeric-drift-expression"
    message: str


def _numbers_from_python_expr(expr: str) -> set[float]:
    """Extract numeric literals from a rule logic_expression."""
    tree = ast.parse(expr, mode="eval")
    out: set[float] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            out.add(float(node.value))
    return out


def _numbers_from_template(template: str) -> set[float]:
    """Numeric literals in an f-string-like output template, after stripping
    {field} placeholders, GB-style citations, and 表 X.Y references — those
    aren't regulatory thresholds, just provenance labels."""
    cleaned = re.sub(r"\{[^}]+\}", " ", template)
    cleaned = _CITATION.sub(" ", cleaned)
    cleaned = _TABLE_REF.sub(" ", cleaned)
    return {float(m.group(0)) for m in _NUMBER_TOKEN.finditer(cleaned)}


def _numbers_from_clause_text(text: str) -> set[float]:
    """Numbers a regulatory reader would see: Arabic decimals + Chinese
    numerals when used as a floor-count phrase (`七层`).

    Cleans the same provenance noise the template extractor cleans
    (citations, 表 X.Y refs, list markers like "1．"). Fractions are
    materialised as the float quotient before stripping their digits so
    "1/3" enters the set as 0.333… not as {1, 3}. Codex P13-pilot P2 #1.
    """
    out: set[float] = set()
    cleaned = text
    # Materialise fractions first so "1/3" becomes ~0.333; then drop the
    # original tokens so they don't double-count as 1 and 3.
    for m in _FRACTION.finditer(cleaned):
        num, den = float(m.group(1)), float(m.group(2))
        if den != 0.0:
            out.add(num / den)
    cleaned = _FRACTION.sub(" ", cleaned)
    cleaned = _CITATION.sub(" ", cleaned)
    cleaned = _TABLE_REF.sub(" ", cleaned)
    cleaned = _LIST_MARKER.sub(" ", cleaned)
    for m in _NUMBER_TOKEN.finditer(cleaned):
        out.add(float(m.group(0)))
    for m in _FLOOR_PHRASE.finditer(text):
        out.add(float(_CN_FLOOR_NUMERAL[m.group(1)]))
    return out


def _close(a: float, others: Iterable[float], tol: float = 1e-6) -> bool:
    return any(abs(a - b) < tol for b in others)


def _is_structural_constant(value: float) -> bool:
    """Numbers we expect to appear in expressions for structural reasons
    (boolean coercion, identity comparisons), not as regulatory thresholds.

    Codex P13-pilot P2 #2: only skip 0.0 universally. 1.0 is too commonly
    a real regulatory threshold (clearance ≥1.0 m, ratios) to suppress.
    """
    return value == 0.0


def check_rule_fidelity(
    rule: RuleCard,
    standards_by_id: dict[str, StandardClause],
) -> list[FidelityFinding]:
    findings: list[FidelityFinding] = []
    clauses = [standards_by_id[c] for c in rule.source_clause_ids if c in standards_by_id]
    if not clauses:
        return findings

    # Union of numbers across all source clauses — multi-clause rules can pull
    # different thresholds from different clauses, so the union is the bar.
    clause_nums: set[float] = set()
    for c in clauses:
        clause_nums |= _numbers_from_clause_text(c.clause_text)

    expr_nums = _numbers_from_python_expr(rule.logic_expression)
    for n in expr_nums:
        if _is_structural_constant(n):
            continue
        if not _close(n, clause_nums):
            findings.append(
                FidelityFinding(
                    severity="error",
                    rule_id=rule.id,
                    clause_id=",".join(c.id for c in clauses),
                    kind="numeric-drift-expression",
                    message=(
                        f"logic_expression uses {n!r} but no source clause text "
                        f"mentions it (clause numbers seen: {sorted(clause_nums)})."
                    ),
                )
            )

    tmpl_nums = _numbers_from_template(rule.output_template)
    for n in tmpl_nums:
        if _is_structural_constant(n):
            continue
        if not _close(n, clause_nums | expr_nums):
            findings.append(
                FidelityFinding(
                    severity="warning",
                    rule_id=rule.id,
                    clause_id=",".join(c.id for c in clauses),
                    kind="numeric-drift-template",
                    message=(
                        f"output_template mentions {n!r} but neither clause text "
                        f"nor logic_expression carries it."
                    ),
                )
            )

    return findings


def check_all(rules: list[RuleCard], standards: list[StandardClause]) -> list[FidelityFinding]:
    by_id = {s.id: s for s in standards}
    out: list[FidelityFinding] = []
    for rule in rules:
        out.extend(check_rule_fidelity(rule, by_id))
    return out
