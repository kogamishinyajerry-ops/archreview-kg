"""Render the human-readable Markdown review report."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from archkg.schemas import Issue, StandardClause


def _env() -> Environment:
    template_dir = str(files("archkg.annotate.templates"))
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(default=False, default_for_string=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(
    *,
    source_pdf: Path,
    entity_graph_path: Path,
    annotated_pdf: Path,
    issues: list[Issue],
    clauses: list[StandardClause],
    out_md: Path,
) -> Path:
    used_ids = {i.standard_clause_id for i in issues}
    clauses_used = [c for c in clauses if c.id in used_ids]
    template = _env().get_template("report.md.j2")
    rendered = template.render(
        source_pdf=str(source_pdf),
        entity_graph_path=str(entity_graph_path),
        annotated_pdf=str(annotated_pdf),
        issues=[i.model_dump() for i in issues],
        clauses_used=[c.model_dump() for c in clauses_used],
    )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(rendered, encoding="utf-8")
    return out_md
