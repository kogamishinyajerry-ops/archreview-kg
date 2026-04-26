from __future__ import annotations

from enum import StrEnum
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
        typer.echo("1.2.0")


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
    project_meta: Path | None = typer.Option(
        None, "--project-meta", exists=True, dir_okay=False, readable=True,
        help="Optional ProjectMeta YAML (building_type/height_class etc.) to filter inapplicable rules.",
    ),
    room_schedule: Path | None = typer.Option(
        None, "--room-schedule", exists=True, dir_okay=False, readable=True,
        help="Optional room schedule YAML supplying Room.properties (净高/楼层/坡屋顶) the PDF builder doesn't extract. Unlocks 4 PARTIAL_AUTODETECT rules.",
    ),
    stair_schedule: Path | None = typer.Option(
        None, "--stair-schedule", exists=True, dir_okay=False, readable=True,
        help="Optional stair schedule YAML declaring Stair entities the PDF builder doesn't detect. Unlocks 5 STAIR_PENDING rules.",
    ),
) -> None:
    """One-shot: ingest -> build-graph -> evaluate rules -> annotate -> report."""
    import json as _json

    import yaml as _yaml
    from pydantic import ValidationError as _ValidationError

    from archkg.annotate.pdf_annotator import annotate as annotate_pdf
    from archkg.annotate.report import render as render_report
    from archkg.graph.builder import build_graph, render_overlay
    from archkg.graph.builder import write_json as write_graph
    from archkg.ingest.primitive_extractor import extract
    from archkg.ingest.primitive_extractor import write_json as write_prims
    from archkg.knowledge.loader import load_rules, load_standards
    from archkg.rules.engine import evaluate
    from archkg.schemas import ProjectMeta

    out.mkdir(parents=True, exist_ok=True)

    meta: ProjectMeta | None = None
    if project_meta is not None:
        try:
            raw = _yaml.safe_load(project_meta.read_text("utf-8"))
        except _yaml.YAMLError as exc:
            raise typer.BadParameter(
                f"--project-meta '{project_meta}' is not valid YAML: {exc}",
                param_hint="--project-meta",
            ) from exc
        try:
            meta = ProjectMeta.model_validate(raw)
        except _ValidationError as exc:
            raise typer.BadParameter(
                f"--project-meta '{project_meta}' failed schema validation:\n{exc}",
                param_hint="--project-meta",
            ) from exc
        # Persist meta into the run directory so `archkg feedback --apply` can
        # promote project-scope confirmed cases without losing project context.
        (out / "project_meta.yaml").write_text(
            _yaml.safe_dump(meta.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    primitives = extract(pdf, points_per_meter=points_per_meter)
    primitives_path = write_prims(primitives, out / "primitives.json")

    graph = build_graph(primitives)

    schedule_apply = None
    if room_schedule is not None:
        # Codex P18-B R1 P0: --room-schedule requires --project-meta. The
        # schedule is project-scoped data (it carries a project_id field by
        # design); applying it without a meta means there's no anchor to
        # cross-check against and a stray schedule for project A could
        # silently land on project B's review run.
        if meta is None:
            raise typer.BadParameter(
                "--room-schedule requires --project-meta so the schedule's project_id can be cross-checked.",
                param_hint="--room-schedule",
            )
        from archkg.graph.schedule import apply_room_schedule
        from archkg.knowledge.room_schedule import (
            RoomScheduleError,
            load_room_schedule,
        )

        try:
            schedule = load_room_schedule(room_schedule)
        except RoomScheduleError as exc:
            raise typer.BadParameter(
                str(exc), param_hint="--room-schedule"
            ) from exc
        if schedule.project_id != meta.project_id:
            raise typer.BadParameter(
                f"--room-schedule project_id '{schedule.project_id}' does not match "
                f"--project-meta project_id '{meta.project_id}'",
                param_hint="--room-schedule",
            )
        schedule_apply = apply_room_schedule(graph, schedule)
        graph = schedule_apply.graph

    stair_schedule_apply = None
    if stair_schedule is not None:
        # Phase 18-C: same project-meta requirement as room schedule.
        # The schedule carries project_id and we cross-check it; without
        # a meta there's no anchor and a stray schedule could land on the
        # wrong project.
        if meta is None:
            raise typer.BadParameter(
                "--stair-schedule requires --project-meta so the schedule's project_id can be cross-checked.",
                param_hint="--stair-schedule",
            )
        from archkg.graph.stair_schedule import (
            StairScheduleApplyError,
            apply_stair_schedule,
        )
        from archkg.knowledge.stair_schedule import (
            StairScheduleError,
            load_stair_schedule,
        )

        try:
            stairs_sched = load_stair_schedule(stair_schedule)
        except StairScheduleError as exc:
            raise typer.BadParameter(
                str(exc), param_hint="--stair-schedule"
            ) from exc
        if stairs_sched.project_id != meta.project_id:
            raise typer.BadParameter(
                f"--stair-schedule project_id '{stairs_sched.project_id}' does not match "
                f"--project-meta project_id '{meta.project_id}'",
                param_hint="--stair-schedule",
            )
        try:
            stair_schedule_apply = apply_stair_schedule(graph, stairs_sched)
        except StairScheduleApplyError as exc:
            raise typer.BadParameter(
                str(exc), param_hint="--stair-schedule"
            ) from exc
        graph = stair_schedule_apply.graph

    graph_path = write_graph(graph, out / "entity_graph.json")
    render_overlay(graph, pdf, out / "entity_overlay.png")

    standards = load_standards()
    rules = load_rules(standards=standards)
    result = evaluate(graph, rules, standards, project_meta=meta)
    (out / "issues.json").write_text(
        _json.dumps([i.model_dump() for i in result.issues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    annotated = annotate_pdf(pdf, result.issues, out / "annotated.pdf")
    report_path = render_report(
        source_pdf=pdf,
        entity_graph_path=graph_path,
        annotated_pdf=annotated,
        issues=result.issues,
        clauses=standards,
        out_md=out / "report.md",
        project_meta=meta,
        skipped=result.skipped,
    )
    _print_review_summary(
        out_dir=out,
        primitives_path=primitives_path,
        graph_path=graph_path,
        annotated_path=annotated,
        report_path=report_path,
        graph=graph,
        issues=result.issues,
        skipped=result.skipped,
        project_meta=meta,
        schedule_apply=schedule_apply,
        stair_schedule_apply=stair_schedule_apply,
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
    skipped: list[Any] | None = None,
    project_meta: Any = None,
    schedule_apply: Any = None,
    stair_schedule_apply: Any = None,
) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Project context
    if project_meta is not None:
        from archkg.labels import label_building_type

        ctx = Table(title="项目上下文", show_header=False, header_style="bold magenta")
        ctx.add_column("k", style="magenta")
        ctx.add_column("v")
        ctx.add_row("project_id", project_meta.project_id)
        if project_meta.project_name:
            ctx.add_row("project_name", project_meta.project_name)
        ctx.add_row("building_type", label_building_type(project_meta.building_type))
        ctx.add_row("height_class", project_meta.height_class)
        if project_meta.fire_class:
            ctx.add_row("fire_class", project_meta.fire_class)
        if project_meta.climate_zone:
            ctx.add_row("climate_zone", project_meta.climate_zone)
        if project_meta.height_m is not None:
            ctx.add_row("height_m", f"{project_meta.height_m:.1f}")
        if project_meta.floors is not None:
            ctx.add_row("floors", str(project_meta.floors))
        console.print(ctx)

    # Detection summary
    g = graph  # EntityGraph
    detect = Table(title="实体识别", show_header=False, header_style="bold cyan")
    detect.add_column("kind", style="cyan")
    detect.add_column("count", justify="right")
    detect.add_row("rooms", str(len(g.rooms)))
    detect.add_row("doors", str(len(g.doors)))
    detect.add_row("corridors", str(len(g.corridors)))
    detect.add_row("dimensions", str(len(g.dimensions)))
    if g.stairs:
        detect.add_row("stairs", str(len(g.stairs)))
    console.print(detect)

    # Room schedule application audit (Phase 18-B)
    if schedule_apply is not None:
        n_matched_rooms = sum(len(v) for v in schedule_apply.matched.values())
        sched = Table(title="房间明细表", show_header=False, header_style="bold green")
        sched.add_column("k", style="green")
        sched.add_column("v")
        sched.add_row("命中房间数", str(n_matched_rooms))
        sched.add_row("命中条目数", f"{len(schedule_apply.matched)} / {len(schedule_apply.matched) + len(schedule_apply.unmatched) + len(schedule_apply.empty_property_entries)}")
        if schedule_apply.unmatched:
            sched.add_row(
                "[yellow]未匹配条目[/yellow]",
                f"{len(schedule_apply.unmatched)} 条（selector 未命中任何房间，请核对房号/标签）",
            )
        if schedule_apply.empty_property_entries:
            sched.add_row(
                "[yellow]空属性条目[/yellow]",
                f"{len(schedule_apply.empty_property_entries)} 条（仅有 selector，没填任何 net_height_m / level / pitched_roof）",
            )
        console.print(sched)

    # Stair schedule application audit (Phase 18-C)
    if stair_schedule_apply is not None:
        ssched = Table(title="楼梯明细表", show_header=False, header_style="bold green")
        ssched.add_column("k", style="green")
        ssched.add_column("v")
        ssched.add_row("新增楼梯数", str(len(stair_schedule_apply.materialized)))
        if stair_schedule_apply.conflicted:
            ssched.add_row(
                "[yellow]ID 冲突条目[/yellow]",
                f"{len(stair_schedule_apply.conflicted)} 条（stair_id 已在 graph 中，未覆盖）",
            )
        if stair_schedule_apply.empty_metric_entries:
            ssched.add_row(
                "[yellow]空指标条目[/yellow]",
                f"{len(stair_schedule_apply.empty_metric_entries)} 条（创建了 Stair 但未填任何 tread/riser/...）",
            )
        console.print(ssched)

    # Skipped rules due to project context
    if skipped:
        sk = Table(title=f"因项目上下文跳过的规则（{len(skipped)}）", header_style="bold yellow")
        sk.add_column("rule_card_id", style="yellow")
        sk.add_column("跳过原因")
        for s in skipped:
            sk.add_row(s.rule_id, s.reason)
        console.print(sk)

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
    with_project_meta: bool = typer.Option(
        True, "--meta/--no-meta",
        help="Use samples/project_meta_demo.yaml for context-aware filtering. Disable for pre-Phase-9 behaviour.",
    ),
    with_room_schedule: bool = typer.Option(
        False, "--room-schedule/--no-room-schedule",
        help="Layer samples/room_schedule_demo.yaml on top to populate Room.properties (净高/楼层/坡屋顶) and demonstrate the 4 PARTIAL_AUTODETECT rules firing.",
    ),
    with_stair_schedule: bool = typer.Option(
        False, "--stair-schedule/--no-stair-schedule",
        help="Layer samples/stair_schedule_demo.yaml on top to materialize Stair entities and demonstrate the 5 STAIR_PENDING rules firing.",
    ),
) -> None:
    """One-key demo: regenerate sample PDF, run review, print where artifacts landed."""
    from rich.console import Console

    from samples.make_sample import build as build_sample

    console = Console()
    sample_dir = Path(__file__).parent.parent.parent / "samples"
    pdf = build_sample(sample_dir / "sample_clean.pdf")
    console.print(f"[cyan]生成测试图纸:[/cyan] {pdf}")
    meta_path = (sample_dir / "project_meta_demo.yaml") if with_project_meta else None
    schedule_path = (
        (sample_dir / "room_schedule_demo.yaml") if with_room_schedule else None
    )
    stair_schedule_path = (
        (sample_dir / "stair_schedule_demo.yaml") if with_stair_schedule else None
    )
    review(
        pdf=pdf,
        out=out,
        points_per_meter=50.0,
        project_meta=meta_path,
        room_schedule=schedule_path,
        stair_schedule=stair_schedule_path,
    )


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


@app.command()
def studio(
    port: int = typer.Option(8765, "-p", "--port"),
    state: Path = typer.Option(
        Path("tmp/studio"),
        "--state",
        help="State directory holding per-run output subdirs (./tmp/studio/runs/<id>/).",
    ),
    no_browser: bool = typer.Option(False, "--no-browser"),
) -> None:
    """Upload-and-review studio (Phase 19-B): drag-drop PDF → browser shows
    annotated PDF + report. First-time-user friendly entry point that calls
    the same in-process pipeline as `archkg review`."""
    from archkg.viewer.studio import serve as serve_studio

    archkg_version = "1.2.0"
    try:
        from importlib.metadata import version as _v

        archkg_version = _v("archkg")
    except Exception:
        pass

    serve_studio(
        port=port,
        state_dir=state,
        open_browser=not no_browser,
        archkg_version=archkg_version,
    )


clause_app = typer.Typer(
    help="Knowledge-base introspection: search and coverage.",
    no_args_is_help=True,
)
app.add_typer(clause_app, name="clause")


adversarial_app = typer.Typer(
    help="Adversarial training lane: examiner ↔ candidate ↔ adjudicator (Phase 18-D).",
    no_args_is_help=True,
)
app.add_typer(adversarial_app, name="adversarial")


@adversarial_app.command("run")
def adversarial_run(
    battery_size: int = typer.Option(
        10, "-n", "--battery-size", min=1,
        help="Number of cases to generate and score.",
    ),
    seed_start: int = typer.Option(
        42, "--seed",
        help="Starting seed; case k uses seed=seed_start+k.",
    ),
    out: Path = typer.Option(
        Path("out/battery"), "-o", "--out",
        help="Battery output directory; one subdir per case + scoreboard.",
    ),
) -> None:
    """Generate a battery, run candidate over each case, score per-rule."""
    from rich.console import Console
    from rich.table import Table

    from archkg.adversarial.battery import run_battery

    console = Console()
    summary = run_battery(n=battery_size, seed_start=seed_start, out_dir=out)
    overall = summary.score.overall()

    table = Table(title=f"Battery summary ({summary.score.total_cases} cases)", show_header=False, header_style="bold cyan")
    table.add_column("k", style="cyan")
    table.add_column("v")
    table.add_row("总 cases", str(summary.score.total_cases))
    table.add_row("TP / FN / FP", f"{overall.tp} / {overall.fn} / {overall.fp}")
    table.add_row(
        "precision / recall / F1",
        f"{_fmt(overall.precision)} / {_fmt(overall.recall)} / {_fmt(overall.f1)}",
    )
    table.add_row("scoreboard", str(out / "scoreboard.md"))
    console.print(table)

    # Print per-rule recall, sorted ascending so the worst offenders surface.
    rules_table = Table(title="Per-rule signals (sorted by recall asc)", header_style="bold cyan")
    rules_table.add_column("rule_id", style="yellow")
    rules_table.add_column("TP", justify="right")
    rules_table.add_column("FN", justify="right")
    rules_table.add_column("FP", justify="right")
    rules_table.add_column("recall", justify="right")
    rules_table.add_column("F1", justify="right")
    rule_scores = sorted(
        summary.score.rule_scores.values(),
        key=lambda r: (r.recall if r.recall is not None else 1.0, r.rule_id),
    )
    for r in rule_scores:
        rules_table.add_row(
            r.rule_id,
            str(r.tp),
            str(r.fn),
            str(r.fp),
            _fmt(r.recall),
            _fmt(r.f1),
        )
    console.print(rules_table)


@adversarial_app.command("sample-stats")
def adversarial_sample_stats(
    n: int = typer.Option(
        1000, "-n", "--n", min=1,
        help="Number of seeds to sample for the audit.",
    ),
    seed_start: int = typer.Option(
        5000, "--seed",
        help="Starting seed; seed_start..seed_start+n is examined.",
    ),
) -> None:
    """Audit per-rule fire rates across N seeds without running the
    builder/engine. Pure predictor sweep — fast (<1s for 1000 seeds) —
    surfaces rules whose fire rate is too low for stable statistical
    signal in the battery (Phase 18-I).

    Two columns:
      - cases / case_rate: number of CASES where the rule was expected
        to fire at least once. Mirrors the adjudicator's set-based
        scoring (a case with 4 failing doors counts once for
        RC-DOOR-WIDTH). This is the primary signal.
      - occurrences / mean_per_case: total ExpectedViolation entries
        for that rule across the sweep, exposing the per-case load
        (RC-DOOR-WIDTH may fire 4 times per case when all 4 doors are
        sub-threshold). Useful for distribution tuning.

    Codex P18-I R1 P0: zero-fill from TARGETED_RULES so a rule that
    drops to 0% fires shows up in the table instead of silently
    disappearing.
    """
    from collections import Counter

    from rich.console import Console
    from rich.table import Table

    from archkg.adversarial.examiner import (
        TARGETED_RULES,
        predict_expected_violations,
        sample_parameters,
    )

    case_counts: Counter[str] = Counter({rid: 0 for rid in TARGETED_RULES})
    occurrence_counts: Counter[str] = Counter({rid: 0 for rid in TARGETED_RULES})
    for s in range(seed_start, seed_start + n):
        p = sample_parameters(s)
        seen: set[str] = set()
        for v in predict_expected_violations(p):
            occurrence_counts[v.rule_id] += 1
            if v.rule_id not in seen:
                seen.add(v.rule_id)
                case_counts[v.rule_id] += 1

    console = Console()
    table = Table(
        title=f"Sample-stats over {n} seeds (start={seed_start})",
        header_style="bold cyan",
    )
    table.add_column("rule_id", style="yellow")
    table.add_column("cases", justify="right")
    table.add_column("case_rate", justify="right")
    table.add_column("occurrences", justify="right")
    table.add_column("mean_per_case", justify="right")
    # Sort by case_rate desc; zero-fired rules sink to the bottom and
    # surface gaps visually.
    for rid in sorted(
        case_counts.keys(),
        key=lambda r: (-case_counts[r], r),
    ):
        cases = case_counts[rid]
        occ = occurrence_counts[rid]
        case_rate = 100.0 * cases / n
        mean_per_case = occ / cases if cases else 0.0
        table.add_row(
            rid,
            str(cases),
            f"{case_rate:.1f}%",
            str(occ),
            f"{mean_per_case:.2f}" if cases else "—",
        )
    console.print(table)
    min_rid, min_c = min(case_counts.items(), key=lambda x: x[1])
    if min_c == 0:
        console.print(
            f"[red]rules with 0 cases: {sorted(rid for rid, c in case_counts.items() if c == 0)}"
            "[/red]\nthese are in TARGETED_RULES but unreachable from the current "
            "sample distribution. Either widen sampling or drop from TARGETED_RULES."
        )
    else:
        console.print(
            f"lowest case_rate: [yellow]{min_rid}[/yellow] = {100.0 * min_c / n:.1f}%"
        )


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


class BuildingTypeFilter(StrEnum):
    residential = "residential"
    public = "public"
    industrial = "industrial"


class CategoryFilter(StrEnum):
    geometric = "geometric"
    fire = "fire"
    accessibility = "accessibility"
    topological = "topological"
    energy = "energy"
    acoustic = "acoustic"
    general = "general"


@clause_app.command("search")
def clause_search(
    query: str = typer.Argument(..., help="Query string, e.g. '走廊净宽'."),
    top_k: int = typer.Option(5, "-k", "--top-k", min=1, help="Max hits to return."),
    building_type: BuildingTypeFilter | None = typer.Option(
        None, "--building-type", help="Restrict to clauses tagged for this building type.",
        case_sensitive=False,
    ),
    category: CategoryFilter | None = typer.Option(
        None, "--category", help="Restrict to clauses of this category.",
        case_sensitive=False,
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
        if building_type is not None and building_type.value not in c.applies_to_building_type:
            return False
        if category is not None and c.category != category.value:
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


@clause_app.command("fidelity")
def clause_fidelity() -> None:
    """Check rule cards' numeric thresholds against their source clause texts.

    Surfaces numeric-drift findings (a rule uses a threshold the clause text
    doesn't carry — the bug class that survived self-consistency tests in
    Phase 11-C). Exits non-zero when any error-severity finding is present
    so this can gate CI before scaling to LLM-authored rules in Phase 13.
    """
    from rich.console import Console
    from rich.table import Table

    from archkg.knowledge.fidelity import check_all
    from archkg.knowledge.loader import load_rules, load_standards

    standards = load_standards()
    rules = load_rules(standards=standards)
    findings = check_all(rules, standards)

    console = Console()
    if not findings:
        console.print("[green]✓ all rule cards pass numeric-fidelity check[/green]")
        return

    by_severity = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    summary = Table(title="规则保真度检查", show_header=False)
    summary.add_column("k")
    summary.add_column("v", justify="right")
    summary.add_row("rules checked", str(len(rules)))
    summary.add_row("findings", str(len(findings)))
    for sev in ("error", "warning", "info"):
        if by_severity.get(sev):
            summary.add_row(f"  {sev}", str(by_severity[sev]))
    console.print(summary)

    t = Table(title="Findings", header_style="bold yellow")
    t.add_column("severity", style="yellow")
    t.add_column("rule_id", style="cyan")
    t.add_column("clauses")
    t.add_column("kind")
    t.add_column("message")
    for f in findings:
        t.add_row(f.severity, f.rule_id, f.clause_id, f.kind, f.message)
    console.print(t)

    if by_severity.get("error"):
        raise typer.Exit(code=1)


@clause_app.command("readiness")
def clause_readiness() -> None:
    """Report each rule's production-readiness tier.

    Phase 18-A lane: shows the gap between "rule defined" (achieved at v1.0)
    and "rule fires on a real PDF" (depends on graph builder + ProjectMeta).
    """
    from rich.console import Console
    from rich.table import Table

    from archkg.knowledge.loader import load_rules, load_standards
    from archkg.knowledge.readiness import classify_all, summarise

    standards = load_standards()
    rules = load_rules(standards=standards)
    findings = classify_all(rules)
    counts = summarise(findings)

    console = Console()
    summary = Table(title="规则就绪度总览", show_header=False)
    summary.add_column("tier")
    summary.add_column("count", justify="right")
    summary.add_row("总规则数", str(len(findings)))
    summary.add_row("[green]自动判定 (AUTODETECTABLE)[/green]", str(counts["AUTODETECTABLE"]))
    summary.add_row(
        "[cyan]ProjectMeta 驱动 (PROJECT_META_DRIVEN)[/cyan]",
        str(counts["PROJECT_META_DRIVEN"]),
    )
    summary.add_row(
        "[yellow]部分自动 (PARTIAL_AUTODETECT — 需 builder 扩展)[/yellow]",
        str(counts["PARTIAL_AUTODETECT"]),
    )
    summary.add_row(
        "[yellow]楼梯待接入 (STAIR_PENDING — 需 builder 加 Stair)[/yellow]",
        str(counts["STAIR_PENDING"]),
    )
    summary.add_row(
        "[blue]人工核对提醒 (REMINDER_BY_DESIGN)[/blue]",
        str(counts["REMINDER_BY_DESIGN"]),
    )
    console.print(summary)

    color = {
        "AUTODETECTABLE": "green",
        "PROJECT_META_DRIVEN": "cyan",
        "PARTIAL_AUTODETECT": "yellow",
        "STAIR_PENDING": "yellow",
        "REMINDER_BY_DESIGN": "blue",
    }
    tier_order = [
        "AUTODETECTABLE",
        "PROJECT_META_DRIVEN",
        "PARTIAL_AUTODETECT",
        "STAIR_PENDING",
        "REMINDER_BY_DESIGN",
    ]

    t = Table(title="逐条就绪度", header_style="bold cyan")
    t.add_column("tier")
    t.add_column("rule_id", style="cyan")
    t.add_column("scope")
    t.add_column("severity")
    t.add_column("blocker / note")
    findings_sorted = sorted(
        findings,
        key=lambda f: (tier_order.index(f.tier), f.rule_id),
    )
    for f in findings_sorted:
        c = color.get(f.tier, "white")
        blocker = ""
        if f.tier == "PARTIAL_AUTODETECT":
            blocker = f"needs entity.properties[{', '.join(f.needs_properties)}]"
        elif f.tier == "STAIR_PENDING":
            blocker = "graph builder doesn't produce Stair entities"
        elif f.tier == "PROJECT_META_DRIVEN":
            blocker = "needs --project-meta with relevant fields"
        elif f.tier == "REMINDER_BY_DESIGN":
            blocker = "manual-check reminder, not auto-judgement"
        t.add_row(
            f"[{c}]{f.tier}[/{c}]",
            f.rule_id,
            f.applies_to,
            f.severity,
            blocker,
        )
    console.print(t)


@clause_app.command("verbatim")
def clause_verbatim() -> None:
    """Audit paraphrase=true clauses for PDF-vs-yaml number-coverage drift.

    Phase 14 lane. Surfaces numbers the source PDF carries that the yaml
    `clause_text` does not — the bug class behind GB50352-6.7.3 silently
    losing its 1.1m / 1.2m branches in the Phase 8 paraphrase pass.

    Informational only — exits 0 even when findings exist. Use for human
    review when adding or refreshing paraphrased clauses.
    """
    from rich.console import Console
    from rich.table import Table

    from archkg.knowledge.loader import load_standards
    from archkg.knowledge.verbatim import audit_paraphrased

    standards = load_standards()
    standards_root = Path(__file__).resolve().parents[2] / "standards_raw"
    findings = audit_paraphrased(standards, standards_root)

    console = Console()
    if not findings:
        console.print("[green]✓ no paraphrased clauses found, or no PDFs available[/green]")
        return

    summary = Table(title="paraphrase=true clauses · verbatim audit", show_header=False)
    summary.add_column("k")
    summary.add_column("v", justify="right")
    summary.add_row("paraphrased clauses checked", str(len(findings)))
    summary.add_row(
        "clauses with PDF-only numbers",
        str(sum(1 for f in findings if f.pdf_only_numbers)),
    )
    console.print(summary)

    t = Table(title="Per-clause coverage", header_style="bold cyan")
    t.add_column("clause_id", style="cyan")
    t.add_column("PDF body chars", justify="right")
    t.add_column("PDF-only numbers")
    t.add_column("yaml-only numbers")
    for f in findings:
        pdf_only = ", ".join(f"{n:g}" for n in f.pdf_only_numbers) or "—"
        yaml_only = ", ".join(f"{n:g}" for n in f.yaml_only_numbers) or "—"
        t.add_row(f.clause_id, str(f.pdf_body_chars), pdf_only, yaml_only)
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
