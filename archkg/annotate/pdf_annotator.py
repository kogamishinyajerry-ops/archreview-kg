"""Draw red bbox + numeric labels on the original PDF for each Issue."""

from __future__ import annotations

from pathlib import Path

import fitz

from archkg.schemas import Issue


def annotate(
    source_pdf: Path,
    issues: list[Issue],
    out_pdf: Path,
    *,
    pad_pt: float = 4.0,
) -> Path:
    doc = fitz.open(str(source_pdf))
    try:
        for idx, issue in enumerate(issues, start=1):
            page = doc[issue.page_index]
            x0, y0, x1, y1 = issue.bbox
            rect = fitz.Rect(x0 - pad_pt, y0 - pad_pt, x1 + pad_pt, y1 + pad_pt)
            page.draw_rect(rect, color=(1, 0, 0), width=1.5)
            label = f"#{idx} {issue.rule_card_id}"
            page.insert_text(
                (rect.x0, max(rect.y0 - 4, 8)),
                label,
                fontsize=8,
                color=(1, 0, 0),
            )
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out_pdf))
    finally:
        doc.close()
    return out_pdf
