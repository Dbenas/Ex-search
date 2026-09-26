"""Application service: wires the components and turns graph output into a report."""

import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Any, cast

import structlog

from curator.agent.graph import CurationState, Dependencies, build_graph
from curator.agent.llm import ClaudeClient, StructuredLLM
from curator.config import Settings
from curator.domain.models import (
    CandidateNarrative,
    MatchReport,
    RankedCandidate,
    RunMetadata,
    ScoredCandidate,
)
from curator.ingestion.loader import CandidateRepository
from curator.ingestion.pipeline import ingest
from curator.retrieval.embeddings import Embedder
from curator.retrieval.hybrid import HybridRetriever
from curator.retrieval.vector_store import VectorStore

log = structlog.get_logger(__name__)

Event = dict[str, Any]


class CurationService:
    def __init__(self, deps: Dependencies) -> None:
        self._deps = deps
        self._graph = build_graph(deps)

    @property
    def repo(self) -> CandidateRepository:
        return self._deps.repo

    @property
    def model(self) -> str:
        return self._deps.llm.model

    async def stream(self, job_description: str) -> AsyncGenerator[Event]:
        """Yields one event per completed step, then the final report."""
        run_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        state: CurationState = {"job_description": job_description, "llm_calls": 0}
        structlog.contextvars.bind_contextvars(run_id=run_id)
        try:
            stream = self._graph.astream(state, stream_mode=["updates", "values"])
            async for mode, chunk in stream:
                if mode == "values":
                    state = cast(CurationState, chunk)
                    continue
                for node, delta in cast(dict[str, dict[str, Any]], chunk).items():
                    if delta:
                        yield {"type": "stage", "stage": node, **self._describe(node, delta)}

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            report = self._build_report(state, run_id, elapsed_ms)
            log.info("curation.completed", elapsed_ms=elapsed_ms, llm_calls=state["llm_calls"])
            yield {"type": "report", "report": report.model_dump(mode="json")}
        finally:
            structlog.contextvars.unbind_contextvars("run_id")

    async def run(self, job_description: str) -> MatchReport:
        async with aclosing(self.stream(job_description)) as events:
            async for event in events:
                if event["type"] == "report":
                    return MatchReport.model_validate(event["report"])
        raise RuntimeError("curation finished without a report")

    @staticmethod
    def _describe(node: str, delta: dict[str, Any]) -> dict[str, Any]:
        match node:
            case "sanitize":
                n = delta["redactions"]
                message = (
                    f"{n} dado(s) de contato removido(s) antes do envio ao modelo"
                    if n
                    else "Nenhum dado pessoal encontrado no texto da vaga"
                )
                return {"message": message, "data": {"redactions": n}}
            case "analyze_job":
                job = delta["job_profile"]
                return {
                    "message": f"Mandato estruturado: {job.role_title}",
                    "data": {"job": job.model_dump()},
                }
            case "retrieve":
                items = delta["shortlist"]
                return {
                    "message": f"{len(items)} perfis pré-selecionados por busca híbrida",
                    "data": {"shortlist": [i.model_dump() for i in items]},
                }
            case "assess":
                candidate_id, assessment = delta["assessments"][0]
                return {
                    "message": "Avaliação de aderência concluída",
                    "data": {
                        "candidate_id": candidate_id,
                        "scores": {
                            "hard_skills": assessment.hard_skills.score,
                            "soft_skills": assessment.soft_skills.score,
                            "context_fit": assessment.context_fit.score,
                        },
                    },
                }
            case "rank":
                ranking = delta["ranking"]
                verified = sum(sum(e.verified for e in c.evidence) for c in ranking)
                total = sum(len(c.evidence) for c in ranking)
                return {
                    "message": f"{verified}/{total} evidências confirmadas no texto dos currículos",
                    "data": {"verified": verified, "total": total},
                }
            case "synthesize":
                return {"message": "Parecer consultivo redigido", "data": {}}
        return {"message": node, "data": {}}

    def _build_report(self, state: CurationState, run_id: str, elapsed_ms: int) -> MatchReport:
        settings, repo = self._deps.settings, self._deps.repo
        pseudo = repo.pseudonymizer
        narratives = {n.alias: n for n in state["narrative"].candidates}
        ranking = state["ranking"]

        top = [
            self._ranked(position, c, narratives.get(c.alias))
            for position, c in enumerate(ranking[: settings.top_k], start=1)
        ]
        also_considered: list[dict[str, str | float]] = [
            {
                "candidate_id": c.candidate_id,
                "name": repo.identity(c.candidate_id).name,
                "final_score": c.final_score,
                "reason": pseudo.reidentify(c.assessment.context_fit.rationale),
            }
            for c in ranking[settings.top_k :]
        ]
        return MatchReport(
            job=state["job_profile"],
            executive_summary=pseudo.reidentify(state["narrative"].executive_summary),
            next_steps=[pseudo.reidentify(step) for step in state["narrative"].next_steps],
            top_candidates=top,
            also_considered=also_considered,
            metadata=RunMetadata(
                run_id=run_id,
                model=self._deps.llm.model,
                elapsed_ms=elapsed_ms,
                candidates_screened=self._deps.retriever.candidate_count,
                pii_redactions=state.get("redactions", 0),
                llm_calls=state.get("llm_calls", 0),
            ),
        )

    def _ranked(
        self, rank: int, c: ScoredCandidate, narrative: CandidateNarrative | None
    ) -> RankedCandidate:
        repo = self._deps.repo
        pseudo = repo.pseudonymizer
        profile = repo.profile(c.candidate_id)
        a = c.assessment
        if narrative is None:
            # The memo step skipped this candidate: fall back to the assessment itself.
            headline = a.context_fit.rationale
            analysis = " ".join(d.rationale for d in (a.hard_skills, a.soft_skills, a.context_fit))
            recommendation = "avancar_com_ressalvas"
        else:
            headline, analysis = narrative.headline, narrative.analysis
            recommendation = narrative.recommendation

        return RankedCandidate(
            rank=rank,
            candidate_id=c.candidate_id,
            name=repo.identity(c.candidate_id).name,
            current_role=profile.current_role,
            final_score=c.final_score,
            retrieval_score=c.retrieval_score,
            grounding_rate=c.grounding_rate,
            scores={
                "hard_skills": a.hard_skills,
                "soft_skills": a.soft_skills,
                "context_fit": a.context_fit,
            },
            headline=pseudo.reidentify(headline),
            analysis=pseudo.reidentify(analysis),
            recommendation=recommendation,
            evidence=c.evidence,
            gaps=[pseudo.reidentify(g) for g in a.gaps],
            interview_focus=[pseudo.reidentify(q) for q in a.interview_focus],
            profile_text=profile.summary,
        )


def build_service(settings: Settings, llm: StructuredLLM | None = None) -> CurationService:
    repo = CandidateRepository.from_directory(settings.candidates_dir)
    embedder = Embedder(settings.embedding_model, settings.embedding_cache_dir)
    store = VectorStore(settings.chroma_dir, settings.collection_name, settings.embedding_model)
    ingest(repo, store, embedder)
    retriever = HybridRetriever(store, embedder)
    return CurationService(
        Dependencies(
            settings=settings,
            llm=llm or ClaudeClient(settings),
            repo=repo,
            retriever=retriever,
        )
    )
