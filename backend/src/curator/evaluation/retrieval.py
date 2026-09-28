"""Retrieval benchmark: does search put the right executive on top, before any LLM?

The reference CVs are indexed together with look-alike distractors in a
throw-away vector store, then each query is run three ways (dense only, BM25
only, hybrid) to show what each half contributes. Queries use the raw job text;
the live agent also adds LLM-generated queries, so this is a lower bound.
"""

from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from curator.domain.models import CandidateIdentity
from curator.ingestion.loader import CandidateRepository, RawCandidate, load_raw_candidates
from curator.ingestion.pipeline import ingest
from curator.retrieval.embeddings import Embedder
from curator.retrieval.hybrid import HybridRetriever
from curator.retrieval.vector_store import VectorStore

MODES = {"denso": (True, False), "lexical": (False, True), "hibrido": (True, True)}


def _distractors(entries: list[dict[str, str]]) -> list[RawCandidate]:
    return [
        RawCandidate(
            identity=CandidateIdentity(candidate_id=e["id"], name=f"Distrator {i:02d}"),
            current_role=e["role"],
            body=" ".join(e["text"].split()),
        )
        for i, e in enumerate(entries, start=1)
    ]


def evaluate_retrieval(
    candidates_dir: Path, dataset_path: Path, embedder: Embedder, k: int = 3
) -> dict[str, Any]:
    dataset = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    raw = load_raw_candidates(candidates_dir) + _distractors(dataset["distractors"])
    repo = CandidateRepository(raw)

    # In-memory index: nothing from the benchmark touches the real vector store.
    store = VectorStore(None, "retrieval_eval", embedder.model_name)
    ingest(repo, store, embedder)
    retriever = HybridRetriever(store, embedder)

    rows = []
    for query in dataset["queries"]:
        text = " ".join(query["text"].split())
        expected = query["expected"]
        row: dict[str, Any] = {"expected": expected, "kind": query["kind"]}
        for mode, (dense, lexical) in MODES.items():
            hits = retriever.search([text], len(repo), dense=dense, lexical=lexical)
            ranking = [e.candidate_id for e in hits]
            position = ranking.index(expected) + 1 if expected in ranking else None
            row[mode] = {"position": position, "top": ranking[:k]}
        rows.append(row)

    def summary(mode: str) -> dict[str, float]:
        positions = [r[mode]["position"] for r in rows]
        return {
            "hit_at_1": round(mean(p == 1 for p in positions), 3),
            f"recall_at_{k}": round(mean(p is not None and p <= k for p in positions), 3),
            "mrr": round(mean(1 / p if p else 0.0 for p in positions), 3),
        }

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "embedding_model": embedder.model_name,
        "profiles_indexed": len(repo),
        "queries": len(rows),
        "summary": {mode: summary(mode) for mode in MODES},
        "rows": rows,
    }
