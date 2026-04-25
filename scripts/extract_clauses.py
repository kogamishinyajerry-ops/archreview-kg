"""One-off helper: scan a GB-standard PDF for clause headers like '5.5.2'
and extract their text. Output is a draft for human curation, not a final
yaml — the curator picks which clauses are review-relevant, normalises
threshold_value/op, and decides paraphrase status.

Usage:
    uv run python scripts/extract_clauses.py standards_raw/GB50096-2011.pdf
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz  # PyMuPDF


CLAUSE_HEADER = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{1,2})\b")


def extract(pdf_path: Path) -> list[tuple[str, str]]:
    doc = fitz.open(str(pdf_path))
    try:
        full = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()

    # Normalise: collapse stray whitespace inside a paragraph but keep newlines as separators
    lines = [ln.rstrip() for ln in full.splitlines()]

    out: list[tuple[str, str]] = []
    cur_id: str | None = None
    cur_buf: list[str] = []

    def flush() -> None:
        if cur_id is not None and cur_buf:
            text = " ".join(s.strip() for s in cur_buf if s.strip())
            text = re.sub(r"\s+", " ", text)
            out.append((cur_id, text))

    for ln in lines:
        m = CLAUSE_HEADER.match(ln.strip())
        if m:
            flush()
            cur_id = m.group(1)
            rest = ln.strip()[len(cur_id):].lstrip()
            cur_buf = [rest] if rest else []
        else:
            if cur_id is not None:
                cur_buf.append(ln)
    flush()
    return out


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: extract_clauses.py <pdf>")
    pdf = Path(sys.argv[1])
    clauses = extract(pdf)
    print(f"# {pdf.name} — {len(clauses)} clause-shaped headers")
    for cid, text in clauses:
        snippet = text[:160].replace("\n", " ")
        print(f"{cid:>10}  {snippet}")


if __name__ == "__main__":
    main()
