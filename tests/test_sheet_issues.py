from __future__ import annotations

from collections import Counter
from pathlib import Path

from archkg.graph.builder import build_graph
from archkg.graph.sheet_graphs import build_sheet_graphs
from archkg.ingest.primitive_extractor import extract
from archkg.ingest.sheet_classification import build_sheet_classification
from archkg.knowledge.loader import load_rules, load_standards
from archkg.rules.engine import evaluate
from archkg.rules.sheet_issues import build_sheet_issues, merge_sheet_issues
from archkg.schemas import ProjectMeta


def _two_page_setup(sample_pdf: Path):
    """Two-page primitives (page 1 = a copy of page 0) plus the per-page sheet
    graphs and the page-0 build_graph result (the merge's ``project_graph``)."""
    first = extract(sample_pdf)
    second_page = first.pages[0].model_copy(update={"page_index": 1})
    primitives = first.model_copy(update={"pages": [first.pages[0], second_page]})
    classification = build_sheet_classification(primitives)
    sheet_graphs = build_sheet_graphs(primitives, classification)
    graph = build_graph(primitives)  # page-0-only, matches the legacy main path
    standards = load_standards()
    rules = load_rules(standards=standards)
    return sheet_graphs, graph, rules, standards


def _is_project_issue(issue) -> bool:
    return bool(issue.entity_ids) and issue.entity_ids[0].startswith("project:")


def test_build_sheet_issues_evaluates_each_sheet_graph(sample_pdf: Path) -> None:
    first = extract(sample_pdf)
    second_page = first.pages[0].model_copy(update={"page_index": 1})
    primitives = first.model_copy(update={"pages": [first.pages[0], second_page]})
    classification = build_sheet_classification(primitives)
    sheet_graphs = build_sheet_graphs(primitives, classification)
    standards = load_standards()
    rules = load_rules(standards=standards)

    preview = build_sheet_issues(sheet_graphs, rules, standards)

    assert preview.schema_version == "sheet_issues.v1"
    assert preview.sheet_count == 2
    assert preview.issue_count >= 4
    assert [group.page_index for group in preview.sheets] == [0, 1]
    for group in preview.sheets:
        rule_ids = {issue.rule_card_id for issue in group.issues}
        assert "RC-CORRIDOR-WIDTH" in rule_ids
        assert "RC-DOOR-WIDTH" in rule_ids


def test_merge_sheet_issues_spans_all_plan_pages(sample_pdf: Path) -> None:
    """Round-7 R6/R7-BUG-002/003: the canonical issue list must now carry
    defects from every plan page, not just page 0."""
    sheet_graphs, graph, rules, standards = _two_page_setup(sample_pdf)
    merged = merge_sheet_issues(sheet_graphs, graph, rules, standards)
    pages = {issue.page_index for issue in merged.issues}
    assert {0, 1} <= pages, f"expected issues on pages 0 and 1, got {pages}"


def test_merge_sheet_issues_entity_count_equals_sum_per_page(sample_pdf: Path) -> None:
    """No entity issue is lost or duplicated: merged entity count == primary
    page (evaluated against the post-schedule graph) + each extra page
    (evaluated against its own sheet graph)."""
    sheet_graphs, graph, rules, standards = _two_page_setup(sample_pdf)
    entity_rules = [r for r in rules if r.applies_to != "Project"]
    primary = evaluate(graph, entity_rules, standards)
    page1_entry = next(e for e in sheet_graphs.graphs if e.page_index == 1)
    page1 = evaluate(page1_entry.graph, entity_rules, standards)
    expected = len(primary.issues) + len(page1.issues)

    merged = merge_sheet_issues(sheet_graphs, graph, rules, standards)
    merged_entity = [i for i in merged.issues if not _is_project_issue(i)]
    assert len(merged_entity) == expected


def test_merge_sheet_issues_runs_project_rules_once(sample_pdf: Path) -> None:
    """PRIMARY-hazard guard: 18/32 rules are applies_to=Project and are
    page-agnostic. They MUST run exactly once, not once per plan page, or a
    2-page run would double every project issue."""
    sheet_graphs, graph, rules, standards = _two_page_setup(sample_pdf)
    meta = ProjectMeta(
        project_id="P-RATIO",
        building_type="residential",
        height_class="多层",
        total_units=200,
        accessible_units=2,  # 1% — fails RC-ACCESSIBLE-RESIDENTIAL-RATIO
    )
    merged = merge_sheet_issues(sheet_graphs, graph, rules, standards, project_meta=meta)
    project_issues = [i for i in merged.issues if _is_project_issue(i)]

    ratio = [i for i in project_issues if i.rule_card_id == "RC-ACCESSIBLE-RESIDENTIAL-RATIO"]
    assert len(ratio) == 1, "project rule must fire once across 2 plan pages"

    counts = Counter(i.rule_card_id for i in project_issues)
    dupes = {rid: c for rid, c in counts.items() if c > 1}
    assert not dupes, f"project rules duplicated across pages: {dupes}"
    assert all(i.page_index == 0 for i in project_issues)


def test_merge_sheet_issues_entity_page_index_matches_evidence(sample_pdf: Path) -> None:
    """Every entity issue's page_index agrees with its evidence, and page-1
    entity issues (previously never extracted) now exist."""
    sheet_graphs, graph, rules, standards = _two_page_setup(sample_pdf)
    merged = merge_sheet_issues(sheet_graphs, graph, rules, standards)
    for issue in merged.issues:
        if not _is_project_issue(issue):
            assert issue.page_index == issue.evidence.page_index
    assert [i for i in merged.issues if i.page_index == 1], (
        "expected at least one issue extracted from plan page 1"
    )


def test_merge_sheet_issues_single_page_matches_legacy(sample_pdf: Path) -> None:
    """Backward-compat: with no extra plan pages the merged issue set is
    content-identical to the legacy single-page evaluate (only fresh
    issue_id uuids and ordering differ)."""
    first = extract(sample_pdf)
    classification = build_sheet_classification(first)
    sheet_graphs = build_sheet_graphs(first, classification)
    graph = build_graph(first)
    standards = load_standards()
    rules = load_rules(standards=standards)

    legacy = evaluate(graph, rules, standards)
    merged = merge_sheet_issues(sheet_graphs, graph, rules, standards)
    assert Counter(i.rule_card_id for i in merged.issues) == Counter(
        i.rule_card_id for i in legacy.issues
    )
