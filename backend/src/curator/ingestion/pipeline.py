from dataclasses import dataclass

import structlog

from curator.ingestion.chunking import chunk_text
from curator.ingestion.loader import CandidateRepository
from curator.retrieval.embeddings import Embedder
from curator.retrieval.vector_store import VectorStore

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class IngestionReport:
    candidates: int
    chunks: int
    embedded: int
    pruned: int


def ingest(repo: CandidateRepository, store: VectorStore, embedder: Embedder) -> IngestionReport:
    """Idempotent: only new or changed chunks are embedded; removed ones are pruned.

    Only pseudonymised profile text is indexed; identities never reach the store.
    """
    chunks = [c for p in repo.profiles for c in chunk_text(p.candidate_id, p.summary)]
    stale = store.stale_chunks(chunks)
    if stale:
        store.upsert(stale, embedder.embed_passages([c.text for c in stale]))
    pruned = store.prune({c.chunk_id for c in chunks})

    report = IngestionReport(
        candidates=len(repo), chunks=len(chunks), embedded=len(stale), pruned=pruned
    )
    log.info("ingestion.completed", **report.__dict__)
    return report
