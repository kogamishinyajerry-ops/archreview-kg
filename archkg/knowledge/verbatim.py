"""Verbatim coverage audit for paraphrase=true clauses.

Phase 14 background: GB50352-6.7.3 was paraphrased into standards.yaml in
Phase 8 with only the `<24m => 1.05m` branch encoded — the `>=24m => 1.1m`
and `上人屋面/公共 => 1.2m` branches were silently dropped. Codex caught
this in Phase 13 round-2 review, but only because that one rule card got
human attention. The general risk is that any paraphrase=true clause may
have lost branches the harness should reason about, and the numeric-fidelity
check (archkg.knowledge.fidelity) does NOT catch this — fidelity only checks
that rule numbers ⊆ clause numbers, not that yaml clause numbers ⊇ PDF
clause numbers.

This module diffs paraphrased clause_text against the source PDF body so
authors get an explicit list of numbers the PDF carries that the yaml does
not. It is intentionally informational rather than gating: PDF OCR is noisy
(page numbers, broken tokenisations) and clause body boundaries are
approximate, so the output is meant for human review during Phase 14 audits
and future paraphrase additions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from archkg.knowledge.fidelity import _numbers_from_clause_text
from archkg.schemas import StandardClause

# Maps StandardClause.source short name → PDF filename in standards_raw/.
# Keep this in lock-step with standards_raw/SOURCES.md.
_SOURCE_TO_PDF: dict[str, str] = {
    "GB 50096-2011": "GB50096-2011.pdf",
    "GB 50352-2019": "GB50352-2019.pdf",
    "GB 50016-2014": "GB50016-2014.pdf",
    "GB 50763-2012": "GB50763-2012.pdf",
}


@dataclass(frozen=True)
class VerbatimFinding:
    """One paraphrased clause's PDF-vs-yaml number-coverage diff."""

    clause_id: str
    pdf_path: str
    pdf_only_numbers: tuple[float, ...]
    yaml_only_numbers: tuple[float, ...]
    pdf_body_chars: int


def _resolve_pdf(source: str, standards_root: Path) -> Path | None:
    name = _SOURCE_TO_PDF.get(source)
    if name is None:
        return None
    p = standards_root / name
    return p if p.exists() else None


def _extract_clause_body(pdf_path: Path, clause_id: str) -> str:
    """Pull text starting at the clause id (e.g. "5.5.27") up to the next
    sibling-or-ancestor clause id (e.g. "5.5.28" or "5.6"). Returns "" if
    not found. Best-effort — boundaries are approximate."""
    try:
        import fitz
    except ImportError:
        return ""

    parts = clause_id.split(".")
    if len(parts) < 2 or not parts[-1].isdigit():
        return ""
    next_sibling = ".".join([*parts[:-1], str(int(parts[-1]) + 1)])
    next_section: str | None = None
    if len(parts) >= 2:
        try:
            next_section = ".".join([*parts[:-2], str(int(parts[-2]) + 1)])
        except ValueError:
            next_section = None
    truncators: list[str] = [next_sibling]
    if next_section is not None:
        truncators.append(next_section + ".")

    pat = re.compile(r"(?:^|\n)\s*" + re.escape(clause_id) + r"(?!\d)")
    pdf = fitz.open(str(pdf_path))
    try:
        collected = ""
        capturing = False
        for page in pdf:
            text = page.get_text()
            if not capturing:
                m = pat.search(text)
                if not m:
                    continue
                collected = text[m.start():]
                capturing = True
            else:
                collected += text
            for trunc in truncators:
                end = collected.find(trunc, len(clause_id))
                if end > 0:
                    return str(collected[:end])
        return str(collected)
    finally:
        pdf.close()


def _strip_self_id_numbers(numbers: set[float], clause_id: str) -> set[float]:
    """Remove the trailing leaf number that appears because the clause body
    literally repeats its own id (e.g. "5.5.27" decomposes to {5.5, 27} —
    27 is noise). The parent-pair (5.5) is intentionally NOT stripped: it
    overlaps with cross-references like "本规范第 5.5.23 条", and removing
    it would mute legitimate yaml↔PDF coverage signals on those references."""
    parts = clause_id.split("-", 1)
    if len(parts) != 2:
        return numbers
    nums_path = parts[1].split(".")
    if len(nums_path) < 2:
        return numbers
    out = set(numbers)
    try:
        out.discard(float(nums_path[-1]))
    except ValueError:
        pass
    return out


def audit_paraphrased(
    standards: Iterable[StandardClause],
    standards_root: Path,
) -> list[VerbatimFinding]:
    """Audit every paraphrase=true clause for PDF-vs-yaml number coverage."""
    findings: list[VerbatimFinding] = []
    for clause in standards:
        if not clause.paraphrase:
            continue
        pdf_path = _resolve_pdf(clause.source, standards_root)
        if pdf_path is None:
            continue
        body = _extract_clause_body(pdf_path, clause.id.split("-", 1)[1] if "-" in clause.id else clause.id)
        if not body:
            continue
        pdf_nums = _strip_self_id_numbers(_numbers_from_clause_text(body), clause.id)
        yaml_nums = _numbers_from_clause_text(clause.clause_text)
        pdf_only = pdf_nums - yaml_nums
        yaml_only = yaml_nums - pdf_nums
        findings.append(
            VerbatimFinding(
                clause_id=clause.id,
                pdf_path=str(pdf_path),
                pdf_only_numbers=tuple(sorted(pdf_only)),
                yaml_only_numbers=tuple(sorted(yaml_only)),
                pdf_body_chars=len(body),
            )
        )
    return findings
