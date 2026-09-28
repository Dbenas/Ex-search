"""Turns graph state into what the partner sees: stage events and the final report.

Names are restored in one place, at the end of ``build_report``: every string in
the report goes through re-identification, so no field can leak a pseudonym
because someone forgot to map it.
"""

from collections.abc import Callable
from typing import Any

from curator.agent.graph import CurationState, Dependencies
from curator.agent.usage import UsageMeter
from curator.domain.models import (
    CandidateNarrative,
    CandidateScores,
    MatchReport,
    RankedCandidate,
    RequirementCoverage,
    RunMetadata,
    ScoredCandidate,
)
from curator.ingestion.loader import CandidateRepository


def deep_map(value: Any, fn: Callable[[str], str]) -> Any:
    """Apply ``fn`` to every string inside nested lists and dicts."""
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [deep_map(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: deep_map(v, fn) for k, v in value.items()}
    return value


def describe_stage(node: str, delta: dict[str, Any]) -> dict[str, Any]:
    """Progress message for the interface after a graph node completes."""
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


def _ranked(
    repo: CandidateRepository, rank: int, c: ScoredCandidate, narrative: CandidateNarrative | None
) -> RankedCandidate:
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
        headline=headline,
        analysis=analysis,
        recommendation=recommendation,
        evidence=c.evidence,
        gaps=a.gaps,
        interview_focus=a.interview_focus,
        profile_text=profile.summary,
    )


def build_report(
    deps: Dependencies, state: CurationState, run_id: str, elapsed_ms: int, meter: UsageMeter
) -> MatchReport:
    settings, repo = deps.settings, deps.repo
    narratives = {n.alias: n for n in state["narrative"].candidates}
    ranking = state["ranking"]
    report = MatchReport(
        job=state["job_profile"],
        executive_summary=state["narrative"].executive_summary,
        next_steps=state["narrative"].next_steps,
        top_candidates=[
            _ranked(repo, position, c, narratives.get(c.alias))
            for position, c in enumerate(ranking[: settings.top_k], start=1)
        ],
        also_considered=[
            {
                "candidate_id": c.candidate_id,
                "name": repo.identity(c.candidate_id).name,
                "final_score": c.final_score,
                "reason": c.assessment.context_fit.rationale,
            }
            for c in ranking[settings.top_k :]
        ],
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
            model=deps.llm.model,
            elapsed_ms=elapsed_ms,
            candidates_screened=deps.retriever.candidate_count,
            pii_redactions=state.get("redactions", 0),
            llm_calls=state.get("llm_calls", 0),
            input_tokens=meter.input_tokens,
            output_tokens=meter.output_tokens,
            cost_usd=meter.cost_usd(settings.model_prices, deps.llm.model),
        ),
    )
    return MatchReport.model_validate(deep_map(report.model_dump(), repo.pseudonymizer.reidentify))
