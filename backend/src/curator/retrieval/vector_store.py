import hashlib
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from curator.domain.models import Chunk


def _fingerprint(chunk: Chunk, model_name: str) -> str:
    return hashlib.sha256(f"{model_name}|{chunk.text}".encode()).hexdigest()[:16]


class VectorStore:
    """Thin wrapper over a Chroma collection (cosine space).

    ``path=None`` keeps the index in memory, used by throw-away evaluation runs.
    """

    def __init__(self, path: Path | None, collection: str, embedding_model: str) -> None:
        settings = ChromaSettings(anonymized_telemetry=False)
        self._client = (
            chromadb.PersistentClient(path=str(path), settings=settings)
            if path is not None
            else chromadb.EphemeralClient(settings=settings)
        )
        self._model = embedding_model
        self._collection = self._client.get_or_create_collection(
            collection,
            configuration={"hnsw": {"space": "cosine"}},
            embedding_function=None,
        )

    def count(self) -> int:
        return self._collection.count()

    def stale_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Chunks that are new or whose text/model changed since the last ingestion."""
        if not chunks:
            return []
        existing = self._collection.get(ids=[c.chunk_id for c in chunks], include=["metadatas"])
        known = {
            id_: (meta or {}).get("fingerprint")
            for id_, meta in zip(existing["ids"], existing["metadatas"] or [], strict=False)
        }
        return [c for c in chunks if known.get(c.chunk_id) != _fingerprint(c, self._model)]

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "candidate_id": c.candidate_id,
                    "start": c.start,
                    "end": c.end,
                    "fingerprint": _fingerprint(c, self._model),
                }
                for c in chunks
            ],
        )

    def prune(self, keep_ids: set[str]) -> int:
        current = set(self._collection.get(include=[])["ids"])
        orphans = sorted(current - keep_ids)
        if orphans:
            self._collection.delete(ids=orphans)
        return len(orphans)

    def all_chunks(self) -> list[Chunk]:
        data = self._collection.get(include=["documents", "metadatas"])
        return [
            Chunk(
                chunk_id=id_,
                candidate_id=str(meta["candidate_id"]),
                text=doc,
                start=int(meta["start"]),  # type: ignore[arg-type]
                end=int(meta["end"]),  # type: ignore[arg-type]
            )
            for id_, doc, meta in zip(
                data["ids"], data["documents"] or [], data["metadatas"] or [], strict=True
            )
        ]

    def query(self, embedding: list[float], n_results: int) -> list[tuple[str, str, float]]:
        """Returns (chunk_id, candidate_id, cosine_similarity) ordered by similarity."""
        n = min(n_results, self.count())
        if n == 0:
            return []
        res: Any = self._collection.query(
            query_embeddings=[embedding],  # type: ignore[arg-type]
            n_results=n,
            include=["metadatas", "distances"],
        )
        return [
            (id_, str(meta["candidate_id"]), 1.0 - float(dist))
            for id_, meta, dist in zip(
                res["ids"][0], res["metadatas"][0], res["distances"][0], strict=True
            )
        ]
