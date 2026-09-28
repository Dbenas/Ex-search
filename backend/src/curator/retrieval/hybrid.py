"""Candidate retrieval: dense (semantic) search, optionally fused with BM25.

Dense retrieval captures intent ("constrói do zero" ~ "escala times do zero").
BM25 can add exact-term matching (SAP, Series B), fused by weighted Reciprocal
Rank Fusion, which combines rankings without calibrating raw scores. It is off
by default: on the retrieval benchmark (docs/avaliacao.md) BM25 matched
incidental words in paraphrased mandates and pushed the right candidate down
at every weight tried. Worth re-testing on a real base with rare technical terms.

Scores are aggregated from chunks to candidates (parent-document retrieval):
a candidate ranks by its best-matching passage for each query.
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence

from rank_bm25 import BM25Okapi

from curator.domain.models import Chunk, ShortlistEntry
from curator.retrieval.embeddings import Embedder
from curator.retrieval.vector_store import VectorStore

RRF_K = 60

_STOPWORDS = frozenset(
    "a o as os de da do das dos e em no na nos nas um uma para por com sem que se ao aos "
    "à às ou mais muito como sua seu suas seus é são foi ser the and of".split()
)


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return [t for t in re.findall(r"[a-z0-9&]+", ascii_text) if t not in _STOPWORDS and len(t) > 1]


def _best_per_candidate(hits: Sequence[tuple[str, str, float]]) -> list[tuple[str, str]]:
    """From (chunk_id, candidate_id, score) sorted desc, keep each candidate's best chunk."""
    seen: dict[str, str] = {}
    for chunk_id, candidate_id, _ in hits:
        seen.setdefault(candidate_id, chunk_id)
    return list(seen.items())


class HybridRetriever:
    def __init__(self, store: VectorStore, embedder: Embedder, lexical_weight: float = 1.0) -> None:
        self._store = store
        self._embedder = embedder
        self._lexical_weight = lexical_weight
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None
        self.refresh()

    def refresh(self) -> None:
        self._chunks = self._store.all_chunks()
        corpus = [tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    @property
    def candidate_count(self) -> int:
        return len({c.candidate_id for c in self._chunks})

    def _lexical(self, query: str) -> list[tuple[str, str, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        hits = [
            (c.chunk_id, c.candidate_id, float(s))
            for c, s in zip(self._chunks, scores, strict=True)
            if s > 0
        ]
        return sorted(hits, key=lambda h: h[2], reverse=True)

    def search(
        self,
        queries: Sequence[str],
        limit: int,
        dense: bool = True,
        lexical: bool = True,
        lexical_weight: float | None = None,
    ) -> list[ShortlistEntry]:
        """Fused ranking of candidates; ``dense``/``lexical`` toggle each half for ablations."""
        w_lex = self._lexical_weight if lexical_weight is None else lexical_weight
        if not self._chunks or not (dense or lexical):
            return []

        fused: dict[str, float] = defaultdict(float)
        evidence: dict[str, set[str]] = defaultdict(set)
        rankings: list[tuple[float, list[tuple[str, str]]]] = []

        vectors = self._embedder.embed_queries(queries) if dense else [None] * len(queries)
        for query, vector in zip(queries, vectors, strict=True):
            if vector is not None:
                hits = self._store.query(vector, len(self._chunks))
                rankings.append((1.0, _best_per_candidate(hits)))
            if lexical and w_lex > 0:
                rankings.append((w_lex, _best_per_candidate(self._lexical(query))))

        for weight, ranking in rankings:
            for position, (candidate_id, chunk_id) in enumerate(ranking, start=1):
                fused[candidate_id] += weight / (RRF_K + position)
                evidence[candidate_id].add(chunk_id)

        # Normalise so a candidate ranked first everywhere scores 1.0.
        ceiling = sum(weight for weight, _ in rankings) / (RRF_K + 1)
        ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [
            ShortlistEntry(
                candidate_id=cid,
                retrieval_score=round(score / ceiling, 4),
                matched_chunks=sorted(evidence[cid]),
            )
            for cid, score in ordered
        ]
