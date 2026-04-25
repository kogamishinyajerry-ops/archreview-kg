from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="archkg",
    help="ArchReview-KG: civil-architecture drawing review CLI.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """ArchReview-KG."""


@app.command()
def version() -> None:
    """Print archkg version."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _v

    try:
        typer.echo(_v("archkg"))
    except PackageNotFoundError:
        typer.echo("0.0.1")


@app.command()
def ingest(
    pdf: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path = typer.Option(Path("primitives.json"), "-o", "--out"),
    points_per_meter: float = typer.Option(50.0, "--ppm", help="PDF points per meter."),
    use_ocr: bool = typer.Option(False, "--ocr/--no-ocr"),
) -> None:
    """Extract vector lines + text (and optionally OCR) into primitives.json."""
    from archkg.ingest.primitive_extractor import extract, write_json

    primitives = extract(pdf, points_per_meter=points_per_meter, use_ocr=use_ocr)
    written = write_json(primitives, out)
    n_lines = sum(len(p.lines) for p in primitives.pages)
    n_texts = sum(len(p.texts) for p in primitives.pages)
    typer.echo(f"wrote {written}  pages={len(primitives.pages)} lines={n_lines} texts={n_texts}")


@app.command()
def review(
    pdf: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path = typer.Option(Path("out"), "-o", "--out"),
    points_per_meter: float = typer.Option(50.0, "--ppm"),
) -> None:
    """One-shot: ingest -> build-graph -> evaluate rules -> annotate -> report."""
    import json as _json

    from archkg.annotate.pdf_annotator import annotate as annotate_pdf
    from archkg.annotate.report import render as render_report
    from archkg.graph.builder import build_graph, render_overlay
    from archkg.graph.builder import write_json as write_graph
    from archkg.ingest.primitive_extractor import extract
    from archkg.ingest.primitive_extractor import write_json as write_prims
    from archkg.knowledge.loader import load_rules, load_standards
    from archkg.rules.engine import evaluate

    out.mkdir(parents=True, exist_ok=True)

    primitives = extract(pdf, points_per_meter=points_per_meter)
    primitives_path = write_prims(primitives, out / "primitives.json")

    graph = build_graph(primitives)
    graph_path = write_graph(graph, out / "entity_graph.json")
    render_overlay(graph, pdf, out / "entity_overlay.png")

    standards = load_standards()
    rules = load_rules(standards=standards)
    issues = evaluate(graph, rules, standards)
    (out / "issues.json").write_text(
        _json.dumps([i.model_dump() for i in issues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    annotated = annotate_pdf(pdf, issues, out / "annotated.pdf")
    report_path = render_report(
        source_pdf=pdf,
        entity_graph_path=graph_path,
        annotated_pdf=annotated,
        issues=issues,
        clauses=standards,
        out_md=out / "report.md",
    )
    typer.echo(
        f"primitives -> {primitives_path}\n"
        f"graph -> {graph_path}\n"
        f"issues={len(issues)}  annotated -> {annotated}\n"
        f"report -> {report_path}"
    )


@app.command("build-graph")
def build_graph_cmd(
    primitives: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path = typer.Option(Path("entity_graph.json"), "-o", "--out"),
    overlay_pdf: Path | None = typer.Option(
        None, "--overlay-pdf", help="If set, also render an overlay PNG against this PDF."
    ),
    overlay_out: Path = typer.Option(Path("entity_overlay.png"), "--overlay-out"),
) -> None:
    """Build entity_graph.json from primitives.json (and optionally a debug overlay PNG)."""
    import json as _json

    from archkg.graph.builder import build_graph, render_overlay, write_json
    from archkg.schemas import Primitives

    raw = _json.loads(primitives.read_text(encoding="utf-8"))
    p = Primitives.model_validate(raw)
    graph = build_graph(p)
    written = write_json(graph, out)
    typer.echo(
        f"wrote {written}  rooms={len(graph.rooms)} doors={len(graph.doors)} "
        f"corridors={len(graph.corridors)} dims={len(graph.dimensions)}"
    )
    if overlay_pdf is not None:
        png = render_overlay(graph, overlay_pdf, overlay_out)
        typer.echo(f"wrote overlay {png}")


if __name__ == "__main__":
    app()
