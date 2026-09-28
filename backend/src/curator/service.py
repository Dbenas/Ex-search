"""Application service: wires the components and turns graph output into a report."""

import asyncio
import hashlib
import re
import time
import unicodedata
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing, suppress
from dataclasses import replace
from typing import Any, cast

import structlog

from curator.agent.graph import CurationState, Dependencies, build_graph, model_view
from curator.agent.llm import StructuredLLM, build_llm
from curator.agent.usage import UsageMeter, current_meter
from curator.config import Settings
from curator.domain.models import (
    CandidateIdentity,
    CandidateNarrative,
    CandidateScores,
    MatchReport,
    RankedCandidate,
    RequirementCoverage,
    RunMetadata,
    ScoredCandidate,
    ScoreWeights,
    UploadReport,
)
from curator.ingestion.chunking import chunk_text
from curator.ingestion.extraction import ExtractedCV
from curator.ingestion.loader import CandidateRepository, RawCandidate, write_candidate_file
from curator.ingestion.pipeline import ingest
from curator.privacy.gender_signals import find_gender_signals
from curator.retrieval.embeddings import Embedder
from curator.retrieval.hybrid import HybridRetriever
from curator.retrieval.vector_store import VectorStore

log = structlog.get_logger(__name__)

Event = dict[str, Any]


def _deep_map(value: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_deep_map(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _deep_map(v, fn) for k, v in value.items()}
    return value


class CandidateError(ValueError):
    """Invalid candidate operation (duplicate, missing name, protected record)."""


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:30]


class CurationService:
    def __init__(self, deps: Dependencies, store: VectorStore, embedder: Embedder) -> None:
        self._deps = deps
        self._graph = build_graph(deps)
        self._store = store
        self._embedder = embedder
        self._base_lock = asyncio.Lock()

    def _reload_base(self) -> None:
        """Re-read the CV files, re-index incrementally and swap the graph."""
        settings = self._deps.settings
        repo = CandidateRepository.from_directory(settings.candidates_dir)
        ingest(repo, self._store, self._embedder)
        self._deps.retriever.refresh()
        self._deps = replace(self._deps, repo=repo)
        self._graph = build_graph(self._deps)

    async def add_candidate(
        self, cv: ExtractedCV, name: str | None = None, current_role: str | None = None
    ) -> UploadReport:
        final_name = (name or cv.name or "").strip()
        if not final_name:
            raise CandidateError("não foi possível identificar o nome; informe-o no formulário")
        digest = hashlib.sha256(cv.body.encode()).hexdigest()[:6]
        candidate_id = f"up-{_slug(final_name)}-{digest}"
        raw = RawCandidate(
            identity=CandidateIdentity(
                candidate_id=candidate_id, name=final_name, contact=cv.contact
            ),
            current_role=(current_role or cv.current_role or "").strip(),
            body=cv.body,
            source="upload",
        )
        async with self._base_lock:
            if candidate_id in self.repo:
                raise CandidateError("este currículo já está na base")
            path = write_candidate_file(self._deps.settings.candidates_dir, raw)
            try:
                await asyncio.to_thread(self._reload_base)
            except Exception:
                path.unlink(missing_ok=True)
                raise

        repo = self.repo
        profile = repo.profile(candidate_id)
        log.info(
            "candidate.added",
            candidate_id=candidate_id,
            chunks=len(chunk_text(candidate_id, profile.summary)),
        )
        return UploadReport(
            candidate_id=candidate_id,
            name=final_name,
            current_role=raw.current_role,
            name_detected=name is None and cv.name is not None,
            source_format=cv.source_format,
            contacts_found=cv.contacts_found,
            # Name + contacts split off by extraction, plus anything scrubbed from the body.
            pii_removed=1
            + len(cv.contacts_found)
            + repo.pseudonymizer.anonymize(cv.body).redactions,
            chunks_indexed=len(chunk_text(candidate_id, profile.summary)),
            gender_cues=[g.term for g in find_gender_signals(profile.summary)],
            indexed_text=model_view(profile.summary, self._deps.settings),
        )

    async def remove_candidate(self, candidate_id: str) -> None:
        async with self._base_lock:
            if candidate_id not in self.repo:
                raise KeyError(candidate_id)
            if self.repo.source(candidate_id) != "upload":
                raise CandidateError("só currículos adicionados pela interface podem ser removidos")
            (self._deps.settings.candidates_dir / f"{candidate_id}.md").unlink()
            await asyncio.to_thread(self._reload_base)
            log.info("candidate.removed", candidate_id=candidate_id)

    @property
    def repo(self) -> CandidateRepository:
        return self._deps.repo

    @property
    def model(self) -> str:
        return self._deps.llm.model

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
                        yield {"type": "stage", "stage": node, **self._describe(node, delta)}

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            report = self._build_report(state, run_id, elapsed_ms, meter)
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
            case "plan_search":
                plan = delta["search_plan"]
                return {
                    "message": f"Plano de busca com {len(plan.target_profiles)} perfis-alvo",
                    "data": {},
                }
        return {"message": node, "data": {}}

    def _build_report(
        self, state: CurationState, run_id: str, elapsed_ms: int, meter: UsageMeter
    ) -> MatchReport:
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
        report = MatchReport(
            job=state["job_profile"],
            executive_summary=pseudo.reidentify(state["narrative"].executive_summary),
            next_steps=[pseudo.reidentify(step) for step in state["narrative"].next_steps],
            top_candidates=top,
            also_considered=also_considered,
            weights=state["weights"],
            assessed=[
                CandidateScores(
                    candidate_id=c.candidate_id,
                    name=repo.identity(c.candidate_id).name,
                    scores={
                        "hard_skills": c.assessment.hard_skills.score,
                        "soft_skills": c.assessment.soft_skills.score,
                        "context_fit": c.assessment.context_fit.score,
                    },
                    grounding_rate=c.grounding_rate,
                    retrieval_score=c.retrieval_score,
                    final_score=c.final_score,
                )
                for c in ranking
            ],
            coverage=[
                RequirementCoverage(
                    requirement=c.requirement,
                    kind=c.kind,
                    status=c.status,
                    covered_by=[repo.identity(cid).name for cid in c.covered_by],
                )
                for c in state.get("coverage", [])
            ],
            search_plan=state.get("search_plan"),
            metadata=RunMetadata(
                run_id=run_id,
                model=self._deps.llm.model,
                elapsed_ms=elapsed_ms,
                candidates_screened=self._deps.retriever.candidate_count,
                pii_redactions=state.get("redactions", 0),
                llm_calls=state.get("llm_calls", 0),
                input_tokens=meter.input_tokens,
                output_tokens=meter.output_tokens,
                cost_usd=meter.cost_usd(settings.model_prices, self._deps.llm.model),
            ),
        )
        # Safety net at the boundary: no pseudonym may reach the partner, whatever the field.
        return MatchReport.model_validate(_deep_map(report.model_dump(), pseudo.reidentify))

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
            llm=llm or build_llm(settings),
            repo=repo,
            retriever=retriever,
        ),
        store=store,
        embedder=embedder,
    )
