"""Curation workflow as a LangGraph state machine.

    sanitize -> analyze_job -> retrieve -> assess (fan-out, one per candidate)
             -> rank (grounding check, weighted score, requirement coverage)
             -> synthesize  ||  plan_search (only when the base falls short)

The flow is deterministic on purpose: the LLM is used where judgement is
needed (reading the mandate, assessing fit, writing the memo) while
retrieval, verification and ranking stay in code, so they are testable and
auditable.
"""

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from curator.agent import prompts
from curator.agent.coverage import needs_search_plan, requirement_coverage
from curator.agent.grounding import grounding_rate, verify_evidence
from curator.agent.llm import StructuredLLM
from curator.config import Settings
from curator.domain.models import (
    CandidateAssessment,
    JobProfile,
    MatchNarrative,
    RequirementCoverage,
    ScoredCandidate,
    ScoreWeights,
    SearchPlan,
    ShortlistEntry,
)
from curator.ingestion.loader import CandidateRepository
from curator.retrieval.hybrid import HybridRetriever


class CurationError(RuntimeError):
    pass


class CurationState(TypedDict, total=False):
    job_description: str
    weights: ScoreWeights
    sanitized_job: str
    redactions: int
    job_profile: JobProfile
    shortlist: list[ShortlistEntry]
    assessments: Annotated[list[tuple[str, CandidateAssessment]], operator.add]
    ranking: list[ScoredCandidate]
    coverage: list[RequirementCoverage]
    narrative: MatchNarrative
    search_plan: SearchPlan
    llm_calls: Annotated[int, operator.add]


class AssessTask(TypedDict):
    candidate_id: str
    job_profile: JobProfile


@dataclass(frozen=True)
class Dependencies:
    settings: Settings
    llm: StructuredLLM
    repo: CandidateRepository
    retriever: HybridRetriever


def render_job_profile(job: JobProfile) -> str:
    def reqs(items: list[Any]) -> str:
        return "\n".join(f"  - {r.name} ({r.importance})" for r in items) or "  - (nenhum)"

    return (
        f"Posição: {job.role_title}\n"
        f"Mandato: {job.mandate}\n"
        f"Contexto: {job.company_context}\n"
        f"Requisitos técnicos:\n{reqs(job.hard_requirements)}\n"
        f"Requisitos comportamentais:\n{reqs(job.soft_requirements)}"
    )


def render_scored(candidate: ScoredCandidate) -> str:
    a = candidate.assessment
    evidence = "\n".join(
        f'  - {e.requirement}: {e.claim} ("{e.quote}")' for e in candidate.evidence if e.verified
    )
    gaps = "\n".join(f"  - {g}" for g in a.gaps) or "  - (nenhuma relevante)"
    return (
        f'<candidato id="{candidate.alias}" nota_final="{candidate.final_score}">\n'
        f"Hard skills {a.hard_skills.score}/10: {a.hard_skills.rationale}\n"
        f"Soft skills {a.soft_skills.score}/10: {a.soft_skills.rationale}\n"
        f"Fit de contexto {a.context_fit.score}/10: {a.context_fit.rationale}\n"
        f"Evidências verificadas:\n{evidence or '  - (nenhuma)'}\n"
        f"Lacunas:\n{gaps}\n"
        f"</candidato>"
    )


def default_weights(s: Settings) -> ScoreWeights:
    return ScoreWeights(
        hard_skills=s.weight_hard_skills,
        soft_skills=s.weight_soft_skills,
        context_fit=s.weight_context_fit,
    )


def weighted_score(assessment: CandidateAssessment, grounding: float, w: ScoreWeights) -> float:
    """Mirrored in frontend/src/lib/ranking.ts for client-side what-if re-ranking."""
    base = (
        w.hard_skills * assessment.hard_skills.score
        + w.soft_skills * assessment.soft_skills.score
        + w.context_fit * assessment.context_fit.score
    ) * 10
    # Poorly grounded assessments lose up to 25% of their score.
    return round(base * (0.75 + 0.25 * grounding), 1)


def build_graph(deps: Dependencies) -> CompiledStateGraph[Any, Any, Any, Any]:
    settings, llm, repo, retriever = deps.settings, deps.llm, deps.repo, deps.retriever

    def sanitize(state: CurationState) -> dict[str, Any]:
        result = repo.pseudonymizer.anonymize(state["job_description"])
        return {"sanitized_job": result.text, "redactions": result.redactions}

    async def analyze_job(state: CurationState) -> dict[str, Any]:
        job = await llm.generate(
            system=prompts.HOUSE_STYLE,
            prompt=prompts.JOB_ANALYSIS.format(job_description=state["sanitized_job"]),
            schema=JobProfile,
            task="job_analysis",
        )
        return {"job_profile": job, "llm_calls": 1}

    def retrieve(state: CurationState) -> dict[str, Any]:
        job = state["job_profile"]
        queries = [state["sanitized_job"], job.mandate, *job.search_queries]
        shortlist = retriever.search(queries, limit=settings.shortlist_size)
        if not shortlist:
            raise CurationError("the candidate base is empty; run ingestion first")
        return {"shortlist": shortlist}

    def fan_out(state: CurationState) -> list[Send]:
        return [
            Send(
                "assess", AssessTask(candidate_id=e.candidate_id, job_profile=state["job_profile"])
            )
            for e in state["shortlist"]
        ]

    async def assess(task: AssessTask) -> dict[str, Any]:
        profile = repo.profile(task["candidate_id"])
        assessment = await llm.generate(
            system=prompts.HOUSE_STYLE,
            prompt=prompts.CANDIDATE_ASSESSMENT.format(
                job_profile=render_job_profile(task["job_profile"]),
                alias=profile.alias,
                profile=profile.summary,
            ),
            schema=CandidateAssessment,
            task="candidate_assessment",
        )
        return {"assessments": [(profile.candidate_id, assessment)], "llm_calls": 1}

    def rank(state: CurationState) -> dict[str, Any]:
        weights = state.get("weights") or default_weights(settings)
        retrieval = {e.candidate_id: e.retrieval_score for e in state["shortlist"]}
        scored = []
        for candidate_id, assessment in state["assessments"]:
            profile = repo.profile(candidate_id)
            evidence = [
                verify_evidence(e, profile.summary, settings.grounding_threshold)
                for e in assessment.evidence
            ]
            grounding = grounding_rate(evidence)
            scored.append(
                ScoredCandidate(
                    candidate_id=candidate_id,
                    alias=profile.alias,
                    retrieval_score=retrieval[candidate_id],
                    assessment=assessment,
                    evidence=evidence,
                    grounding_rate=grounding,
                    final_score=weighted_score(assessment, grounding, weights),
                )
            )
        # Retrieval score only breaks ties; the assessment drives the ranking.
        scored.sort(key=lambda c: (c.final_score, c.retrieval_score), reverse=True)
        coverage = requirement_coverage(state["job_profile"], scored)
        return {"ranking": scored, "coverage": coverage, "weights": weights}

    def after_rank(state: CurationState) -> list[str]:
        plan = settings.search_plan_enabled and needs_search_plan(
            state["ranking"], state["coverage"], settings.search_plan_threshold
        )
        return ["synthesize", "plan_search"] if plan else ["synthesize"]

    async def synthesize(state: CurationState) -> dict[str, Any]:
        top = state["ranking"][: settings.top_k]
        narrative = await llm.generate(
            system=prompts.HOUSE_STYLE,
            prompt=prompts.SYNTHESIS.format(
                job_profile=render_job_profile(state["job_profile"]),
                shortlist="\n\n".join(render_scored(c) for c in top),
            ),
            schema=MatchNarrative,
            task="synthesis",
        )
        return {"narrative": narrative, "llm_calls": 1}

    async def plan_search(state: CurationState) -> dict[str, Any]:
        leader = state["ranking"][0]
        labels = {"lider": "coberto pelo melhor candidato", "outros": "só em perfis secundários"}
        coverage = "\n".join(
            f"- {c.requirement}: {labels.get(c.status, 'sem cobertura na base')}"
            for c in state["coverage"]
        )
        plan = await llm.generate(
            system=prompts.HOUSE_STYLE,
            prompt=prompts.SEARCH_PLAN.format(
                job_profile=render_job_profile(state["job_profile"]),
                coverage=coverage or "- (sem requisitos essenciais identificados)",
                leader_score=leader.final_score,
                leader_gaps="; ".join(leader.assessment.gaps) or "nenhuma registrada",
            ),
            schema=SearchPlan,
            task="search_plan",
        )
        return {"search_plan": plan, "llm_calls": 1}

    graph = StateGraph(CurationState)
    graph.add_node("sanitize", sanitize)
    graph.add_node("analyze_job", analyze_job)
    graph.add_node("retrieve", retrieve)
    graph.add_node("assess", assess)  # type: ignore[arg-type]  # receives a Send payload
    graph.add_node("rank", rank)
    graph.add_node("synthesize", synthesize)
    graph.add_node("plan_search", plan_search)

    graph.add_edge(START, "sanitize")
    graph.add_edge("sanitize", "analyze_job")
    graph.add_edge("analyze_job", "retrieve")
    graph.add_conditional_edges("retrieve", fan_out, ["assess"])
    graph.add_edge("assess", "rank")
    graph.add_conditional_edges("rank", after_rank, ["synthesize", "plan_search"])
    graph.add_edge("synthesize", END)
    graph.add_edge("plan_search", END)
    return graph.compile()
