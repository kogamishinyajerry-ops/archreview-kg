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
