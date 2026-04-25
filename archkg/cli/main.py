from __future__ import annotations

from pathlib import Path
from typing import Any

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
    _print_review_summary(
        out_dir=out,
        primitives_path=primitives_path,
        graph_path=graph_path,
        annotated_path=annotated,
        report_path=report_path,
        graph=graph,
        issues=issues,
    )


def _print_review_summary(
    *,
    out_dir: Path,
    primitives_path: Path,
    graph_path: Path,
    annotated_path: Path,
    report_path: Path,
    graph: Any,
    issues: list[Any],
) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Detection summary
    g = graph  # EntityGraph
    detect = Table(title="实体识别", show_header=False, header_style="bold cyan")
    detect.add_column("kind", style="cyan")
    detect.add_column("count", justify="right")
    detect.add_row("rooms", str(len(g.rooms)))
    detect.add_row("doors", str(len(g.doors)))
    detect.add_row("corridors", str(len(g.corridors)))
    detect.add_row("dimensions", str(len(g.dimensions)))
    console.print(detect)

    # Issues table
    if issues:
        t = Table(title=f"问题清单（共 {len(issues)} 条）", header_style="bold red")
        t.add_column("#", style="dim", width=3, justify="right")
        t.add_column("rule_card", style="yellow")
        t.add_column("条文", style="cyan")
        t.add_column("测量", justify="right")
        t.add_column("阈值", justify="right")
        t.add_column("说明")
        for idx, i in enumerate(issues, 1):  # i is Issue
            ev = i.evidence
            t.add_row(
                str(idx),
                i.rule_card_id,
                i.standard_clause_id,
                f"{ev.measured_value:.2f}" if ev.measured_value is not None else "—",
                f"{ev.threshold_value:.2f}" if ev.threshold_value is not None else "—",
                i.message,
            )
        console.print(t)
    else:
        console.print("[green]✓ 未发现违反规则的实体。[/green]")

    # Artifacts
    art = Table(title="产出文件", show_header=False)
    art.add_column("kind", style="cyan")
    art.add_column("path", style="white")
    art.add_row("primitives", str(primitives_path))
    art.add_row("entity graph", str(graph_path))
    art.add_row("entity overlay PNG", str(out_dir / "entity_overlay.png"))
    art.add_row("issues JSON", str(out_dir / "issues.json"))
    art.add_row("annotated PDF", str(annotated_path))
    art.add_row("report MD", str(report_path))
    console.print(art)
    console.print(
        Panel(
            f"下一步：\n"
            f"  • 打开 [bold]{annotated_path}[/bold] 看红框标注\n"
            f"  • 打开 [bold]{report_path}[/bold] 看可复核的问题清单\n"
            f"  • 编辑 status=confirmed 后跑 [bold]archkg feedback {out_dir} --apply[/bold]",
            title="✅ 审图完成",
            border_style="green",
        )
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


@app.command()
def demo(
    out: Path = typer.Option(Path("out"), "-o", "--out"),
) -> None:
    """One-key demo: regenerate sample PDF, run review, print where artifacts landed."""
    from rich.console import Console

    from samples.make_sample import build as build_sample

    console = Console()
    sample_dir = Path(__file__).parent.parent.parent / "samples"
    pdf = build_sample(sample_dir / "sample_clean.pdf")
    console.print(f"[cyan]生成测试图纸:[/cyan] {pdf}")
    review(pdf=pdf, out=out, points_per_meter=50.0)


@app.command()
def viewer(
    out: Path = typer.Option(Path("out"), "-o", "--out"),
    source_pdf: Path = typer.Option(
        Path("samples/sample_clean.pdf"),
        "--source", "-s",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Source PDF used for previews and download link.",
    ),
    port: int = typer.Option(8765, "-p", "--port"),
    no_browser: bool = typer.Option(False, "--no-browser"),
) -> None:
    """Start a static, read-only demo viewer (http.server) over the run directory."""
    from archkg.viewer.server import serve

    serve(out, source_pdf, port=port, open_browser=not no_browser)


clause_app = typer.Typer(help="Knowledge-base introspection: search and coverage.")
app.add_typer(clause_app, name="clause")


@clause_app.command("search")
def clause_search(
    query: str = typer.Argument(..., help="Query string, e.g. '走廊净宽'."),
    top_k: int = typer.Option(5, "-k", "--top-k"),
    building_type: str | None = typer.Option(
        None, "--building-type", help="Filter: residential / public / industrial."
    ),
    category: str | None = typer.Option(
        None, "--category", help="Filter: geometric / fire / accessibility / topological / energy / acoustic / general."
    ),
) -> None:
    """BM25 search over the packaged standards library, with metadata filters."""
    from rich.console import Console
    from rich.table import Table

    from archkg.knowledge.loader import load_standards
    from archkg.knowledge.search import ClauseIndex
    from archkg.schemas import StandardClause

    clauses = load_standards()
    idx = ClauseIndex(clauses)

    def filter_fn(c: StandardClause) -> bool:
        if building_type is not None and building_type not in c.applies_to_building_type:
            return False
        if category is not None and c.category != category:
            return False
        return True

    hits = idx.search(query, top_k=top_k, filter_fn=filter_fn)
    console = Console()
    if not hits:
        console.print("[yellow]no matching clauses[/yellow]")
        return

    t = Table(title=f"clause search · '{query}'", header_style="bold cyan")
    t.add_column("#", style="dim", width=3, justify="right")
    t.add_column("score", justify="right")
    t.add_column("clause_id", style="cyan")
    t.add_column("category", style="yellow")
    t.add_column("source")
    t.add_column("clause_text")
    for i, (score, c) in enumerate(hits, 1):
        excerpt = c.clause_text if len(c.clause_text) <= 70 else c.clause_text[:67] + "…"
        t.add_row(str(i), f"{score:.2f}", c.id, c.category, c.source, excerpt)
    console.print(t)


@clause_app.command("coverage")
def clause_coverage() -> None:
    """Report which standards clauses are covered by at least one rule card."""
    from rich.console import Console
    from rich.table import Table

    from archkg.knowledge.loader import load_rules, load_standards

    standards = load_standards()
    rules = load_rules(standards=standards)
    referenced = {cid for r in rules for cid in r.source_clause_ids}

    console = Console()
    summary = Table(title="知识库覆盖率", show_header=False)
    summary.add_column("k", style="cyan")
    summary.add_column("v", justify="right")
    summary.add_row("standards clauses", str(len(standards)))
    summary.add_row("rule cards", str(len(rules)))
    covered = sum(1 for c in standards if c.id in referenced)
    pct = covered * 100 // max(len(standards), 1)
    summary.add_row("clauses with ≥1 rule", f"{covered} / {len(standards)} ({pct}%)")
    console.print(summary)

    uncovered = [c for c in standards if c.id not in referenced]
    if uncovered:
        t = Table(title=f"未覆盖条文（{len(uncovered)}）", header_style="bold red")
        t.add_column("clause_id", style="cyan")
        t.add_column("category", style="yellow")
        t.add_column("source")
        t.add_column("clause")
        for c in uncovered:
            excerpt = c.clause_text if len(c.clause_text) <= 80 else c.clause_text[:77] + "…"
            t.add_row(c.id, c.category, c.source, excerpt)
        console.print(t)


@app.command()
def feedback(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    apply_to_rules: bool = typer.Option(
        False,
        "--apply/--no-apply",
        help="Append confirmed cases to rule_cards.yaml as regression test_cases.",
    ),
    rules_path: Path | None = typer.Option(
        None, "--rules-path", help="Override rule_cards.yaml location for --apply."
    ),
) -> None:
    """Read run_dir/report.md, persist feedback.yaml, optionally promote confirmed cases."""
    from archkg.feedback.recorder import record

    out = record(run_dir, rules_path=rules_path, apply_to_rules=apply_to_rules)
    typer.echo(f"wrote {out}")


if __name__ == "__main__":
    app()
