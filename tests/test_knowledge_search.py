"""Tests for the BM25 clause index.

The golden retrieval set asserts recall@3 ≥ 80% — i.e. for the listed
queries, the expected clause must appear in the top-3 hits. This is the
Phase 8 acceptance gate for `archkg clause search`.
"""

from __future__ import annotations

import pytest

from archkg.knowledge.loader import load_standards
from archkg.knowledge.search import ClauseIndex, tokenize
from archkg.schemas import StandardClause

# (query, expected_clause_id) — recall@3 ≥ 80% is the gate.
GOLDEN_RETRIEVAL: list[tuple[str, str]] = [
    ("卧室面积", "GB50096-5.3.1"),
    ("卧室净高", "GB50096-5.5.2"),
    ("户门 净宽", "GB50016-5.5.30"),
    ("电梯 七层", "GB50096-6.4.1"),
    ("楼梯 踏步", "GB50096-6.3.2"),
    ("阳台 栏杆", "GB50096-5.6.2"),
    ("无障碍 住房", "GB50763-7.4.3"),
    ("疏散 距离", "GB50016-5.5.29"),
    ("避难层", "GB50016-5.5.31"),
    ("通廊 净宽", "GB50096-5.7.2"),
]


@pytest.fixture(scope="module")
def index() -> ClauseIndex:
    return ClauseIndex(load_standards())


def test_tokenizer_emits_unigrams_and_bigrams() -> None:
    toks = tokenize("走廊净宽")
    assert "走" in toks and "廊" in toks
    assert "走廊" in toks and "廊净" in toks


def test_tokenizer_handles_ascii_and_mixed() -> None:
    toks = tokenize("GB50096-5.5.2 卧室")
    assert "gb50096" in toks
    assert "卧室" in toks


def test_search_returns_empty_for_blank_query(index: ClauseIndex) -> None:
    assert index.search("") == []
    assert index.search("    ") == []


def test_search_id_lookup_finds_exact_clause(index: ClauseIndex) -> None:
    hits = index.search("GB50096-5.5.2")
    assert hits
    assert hits[0][1].id == "GB50096-5.5.2"


@pytest.mark.parametrize(("query", "expected"), GOLDEN_RETRIEVAL)
def test_golden_retrieval_top3(index: ClauseIndex, query: str, expected: str) -> None:
    hits = index.search(query, top_k=3)
    ids = [c.id for _, c in hits]
    assert expected in ids, f"expected {expected} in top-3 for '{query}', got {ids}"


def test_filter_by_category(index: ClauseIndex) -> None:
    def only_accessibility(c: StandardClause) -> bool:
        return c.category == "accessibility"

    hits = index.search("门", top_k=5, filter_fn=only_accessibility)
    assert hits
    for _, c in hits:
        assert c.category == "accessibility"


def test_filter_by_building_type(index: ClauseIndex) -> None:
    def public_only(c: StandardClause) -> bool:
        return "public" in c.applies_to_building_type

    hits = index.search("净高", top_k=5, filter_fn=public_only)
    for _, c in hits:
        assert "public" in c.applies_to_building_type


def test_search_rejects_non_positive_top_k(index: ClauseIndex) -> None:
    """Codex P8 nit: -k <= 0 should not produce surprising slice semantics."""
    assert index.search("卧室净高", top_k=0) == []
    assert index.search("卧室净高", top_k=-1) == []
    assert index.search("卧室净高", top_k=-99) == []


def test_tokenizer_nfkc_normalises_fullwidth_punctuation() -> None:
    """Codex P8 nit: full-width hyphen / period from Chinese IME should match ASCII id."""
    ascii_tokens = set(tokenize("GB50096-5.5.2 卧室净高"))
    fullwidth_tokens = set(tokenize("ＧＢ５００９６－５．５．２ 卧室净高"))
    assert "gb50096-5.5.2" in ascii_tokens
    assert "gb50096-5.5.2" in fullwidth_tokens, (
        f"NFKC failed; got {fullwidth_tokens - ascii_tokens}"
    )


def test_search_fullwidth_id_lookup_finds_target(index: ClauseIndex) -> None:
    """Full-width id query must hit the same top-1 as the ASCII form."""
    hits_ascii = index.search("GB50096-5.5.2", top_k=1)
    hits_fullwidth = index.search("ＧＢ５００９６－５．５．２", top_k=1)
    assert hits_ascii and hits_fullwidth
    assert hits_ascii[0][1].id == hits_fullwidth[0][1].id == "GB50096-5.5.2"


def test_recall_at_3_above_threshold(index: ClauseIndex) -> None:
    """Aggregate gate: ≥80% of golden queries must surface the expected clause in top-3."""
    hits_count = 0
    for query, expected in GOLDEN_RETRIEVAL:
        hits = index.search(query, top_k=3)
        if expected in {c.id for _, c in hits}:
            hits_count += 1
    recall = hits_count / len(GOLDEN_RETRIEVAL)
    assert recall >= 0.8, f"recall@3={recall:.2%} below 80% gate"
