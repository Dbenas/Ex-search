"""Application service: runs the curation graph and keeps the candidate base current.

Report assembly lives in ``reporting`` and candidate rules in ``candidates``;
this module only orchestrates.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import aclosing, suppress
from dataclasses import replace
from typing import Any, cast

import structlog

from curator.agent.graph import CurationState, Dependencies, build_graph
from curator.agent.llm import StructuredLLM, build_llm
from curator.agent.usage import UsageMeter, current_meter
from curator.candidates import CandidateError, new_upload, upload_receipt
from curator.config import Settings
from curator.domain.models import MatchReport, ScoreWeights, UploadReport
from curator.ingestion.extraction import ExtractedCV
from curator.ingestion.loader import CandidateRepository, write_candidate_file
from curator.ingestion.pipeline import ingest
from curator.reporting import build_report, describe_stage
from curator.retrieval.embeddings import Embedder
from curator.retrieval.hybrid import HybridRetriever
from curator.retrieval.vector_store import VectorStore

log = structlog.get_logger(__name__)

Event = dict[str, Any]

__all__ = ["CandidateError", "CurationService", "build_service"]


class CurationService:
    def __init__(self, deps: Dependencies, store: VectorStore, embedder: Embedder) -> None:
        self._deps = deps
        self._graph = build_graph(deps)
        self._store = store
        self._embedder = embedder
        self._base_lock = asyncio.Lock()

    @property
    def repo(self) -> CandidateRepository:
        return self._deps.repo

    @property
    def model(self) -> str:
        return self._deps.llm.model

    # --- Curation -------------------------------------------------------------

    async def stream(
        self, job_description: str, weights: ScoreWeights | None = None
    ) -> AsyncGenerator[Event]:
        """Yields one event per completed step, then the final report."""
        run_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        state: CurationState = {"job_description": job_description, "llm_calls": 0}
        if weights is not None:
            state["weights"] = weights
        meter = UsageMeter()
        meter_token = current_meter.set(meter)
        structlog.contextvars.bind_contextvars(run_id=run_id)
        try:
            stream = self._graph.astream(state, stream_mode=["updates", "values"])
            async for mode, chunk in stream:
                if mode == "values":
                    state = cast(CurationState, chunk)
                    continue
                for node, delta in cast(dict[str, dict[str, Any]], chunk).items():
                    if delta:
                        yield {"type": "stage", "stage": node, **describe_stage(node, delta)}

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            report = build_report(self._deps, state, run_id, elapsed_ms, meter)
            log.info("curation.completed", elapsed_ms=elapsed_ms, llm_calls=state["llm_calls"])
            yield {"type": "report", "report": report.model_dump(mode="json")}
        finally:
            structlog.contextvars.unbind_contextvars("run_id")
            # The generator may be finalised from another context (e.g. client disconnect).
            with suppress(ValueError):
                current_meter.reset(meter_token)

    async def run(self, job_description: str, weights: ScoreWeights | None = None) -> MatchReport:
        async with aclosing(self.stream(job_description, weights)) as events:
            async for event in events:
                if event["type"] == "report":
                    return MatchReport.model_validate(event["report"])
        raise RuntimeError("curation finished without a report")

    # --- Candidate base -------------------------------------------------------

    def _reload_base(self) -> None:
        """Re-read the CV files, re-index incrementally and swap the graph."""
        repo = CandidateRepository.from_directory(self._deps.settings.candidates_dir)
        ingest(repo, self._store, self._embedder)
        self._deps.retriever.refresh()
        self._deps = replace(self._deps, repo=repo)
        self._graph = build_graph(self._deps)

    async def add_candidate(
        self, cv: ExtractedCV, name: str | None = None, current_role: str | None = None
    ) -> UploadReport:
        raw = new_upload(cv, name, current_role)
        async with self._base_lock:
            if raw.identity.candidate_id in self.repo:
                raise CandidateError("este currículo já está na base")
            path = write_candidate_file(self._deps.settings.candidates_dir, raw)
            try:
                await asyncio.to_thread(self._reload_base)
            except Exception:
                path.unlink(missing_ok=True)
                raise
        log.info("candidate.added", candidate_id=raw.identity.candidate_id)
        return upload_receipt(raw, cv, name is not None, self.repo, self._deps.settings)

    async def remove_candidate(self, candidate_id: str) -> None:
        async with self._base_lock:
            if candidate_id not in self.repo:
                raise KeyError(candidate_id)
            if self.repo.source(candidate_id) != "upload":
                raise CandidateError("só currículos adicionados pela interface podem ser removidos")
            (self._deps.settings.candidates_dir / f"{candidate_id}.md").unlink()
            await asyncio.to_thread(self._reload_base)
            log.info("candidate.removed", candidate_id=candidate_id)


def build_service(settings: Settings, llm: StructuredLLM | None = None) -> CurationService:
    repo = CandidateRepository.from_directory(settings.candidates_dir)
    embedder = Embedder(settings.embedding_model, settings.embedding_cache_dir)
    store = VectorStore(settings.chroma_dir, settings.collection_name, settings.embedding_model)
    ingest(repo, store, embedder)
    retriever = HybridRetriever(store, embedder, lexical_weight=settings.lexical_weight)
    return CurationService(
        Dependencies(
            settings=settings,
            llm=llm or build_llm(settings),
            repo=repo,
            retriever=retriever,
        ),
        store=store,
        embedder=embedder,
    )
