from __future__ import annotations

from pathlib import Path

from archkg.graph.sheet_graphs import build_sheet_graphs
from archkg.ingest.primitive_extractor import extract
from archkg.ingest.sheet_classification import build_sheet_classification
from archkg.knowledge.loader import load_rules, load_standards
from archkg.rules.sheet_issues import build_sheet_issues


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
