"""BM25 search over the standards library with a CJK-aware tokenizer.

Zero external deps: a mixed character/bigram tokenizer (good enough for
short Chinese clause queries — '走廊' will hit '通廊' via shared 廊) plus
inline BM25 scoring. Caller-supplied filter callbacks let us restrict by
building_type / category / height class without baking it into the index.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from archkg.schemas import StandardClause

_CJK = re.compile(r"[一-鿿]+")
_WORD = re.compile(r"[A-Za-z0-9]+")
_CLAUSE_ID = re.compile(r"[A-Za-z]{2,4}\d+(?:[-.]\d+)+")


def tokenize(text: str) -> list[str]:
    """Mixed unigram + bigram (CJK) + lowercase word (ASCII) tokenizer.

    Clause-id-like substrings (e.g. 'GB50096-5.5.2') are also emitted
    verbatim so exact-id queries score uniquely against their target.

    Input is NFKC-normalised so Chinese-IME full-width inputs like
    'GB50096－5．5．2' (full-width hyphen / period) match the same tokens as
    their ASCII counterparts.
    """
    text = unicodedata.normalize("NFKC", text)
    out: list[str] = []
    for m in _CLAUSE_ID.finditer(text):
        out.append(m.group(0).lower())
    for m in _CJK.finditer(text):
        run = m.group(0)
        out.extend(run)
        out.extend(run[i : i + 2] for i in range(len(run) - 1))
    out.extend(w.lower() for w in _WORD.findall(text))
    return out


@dataclass(frozen=True)
class _IndexedDoc:
    clause_id: str
    tokens: tuple[str, ...]


class ClauseIndex:
    """In-memory BM25 index over StandardClause objects.

    Document content = `id + ' ' + clause_text`. The id is included so a
    user typing 'GB50096-5.5.2' goes straight to that clause.
    """

    K1 = 1.5
    B = 0.75

    def __init__(self, clauses: Sequence[StandardClause]) -> None:
        self._clauses: dict[str, StandardClause] = {c.id: c for c in clauses}
        self._docs: list[_IndexedDoc] = []
        self._doc_freq: Counter[str] = Counter()
        for c in clauses:
            tokens = tuple(tokenize(f"{c.id} {c.clause_text}"))
            self._docs.append(_IndexedDoc(c.id, tokens))
            for t in set(tokens):
                self._doc_freq[t] += 1
        self._n_docs = len(self._docs)
        total_dl = sum(len(d.tokens) for d in self._docs)
        self._avgdl = total_dl / self._n_docs if self._n_docs else 0.0

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        return math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def _score(self, doc: _IndexedDoc, q_tokens: list[str]) -> float:
        if not doc.tokens:
            return 0.0
        tf = Counter(doc.tokens)
        dl = len(doc.tokens)
        s = 0.0
        for q in q_tokens:
            f = tf.get(q, 0)
            if f == 0:
                continue
            idf = self._idf(q)
            denom = f + self.K1 * (1 - self.B + self.B * dl / max(self._avgdl, 1.0))
            s += idf * f * (self.K1 + 1) / denom
        return s

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filter_fn: Callable[[StandardClause], bool] | None = None,
    ) -> list[tuple[float, StandardClause]]:
        if top_k <= 0:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scored: list[tuple[float, StandardClause]] = []
        for doc in self._docs:
            clause = self._clauses[doc.clause_id]
            if filter_fn is not None and not filter_fn(clause):
                continue
            s = self._score(doc, q_tokens)
            if s > 0:
                scored.append((s, clause))
        scored.sort(key=lambda p: p[0], reverse=True)
        return scored[:top_k]
