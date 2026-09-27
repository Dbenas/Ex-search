import pytest

from curator.agent.coverage import needs_search_plan, requirement_coverage
from curator.domain.models import (
    CandidateAssessment,
    DimensionScore,
    JobProfile,
    Requirement,
    ScoredCandidate,
    ScoreWeights,
    VerifiedEvidence,
)

JOB = JobProfile(
    role_title="CFO",
    mandate="m",
    company_context="c",
    hard_requirements=[
        Requirement(name="Captação institucional", importance="essencial"),
        Requirement(name="Preparação para M&A", importance="essencial"),
        Requirement(name="Métricas SaaS", importance="desejavel"),
    ],
    soft_requirements=[Requirement(name="Relação com investidores", importance="essencial")],
    search_queries=["q"],
)


def _candidate(cid: str, score: float, evidence: dict[str, bool]) -> ScoredCandidate:
    dim = DimensionScore(score=5, rationale="r")
    return ScoredCandidate(
        candidate_id=cid,
        alias=cid,
        retrieval_score=1.0,
        assessment=CandidateAssessment(
            hard_skills=dim,
            soft_skills=dim,
            context_fit=dim,
            evidence=[],
            gaps=[],
            interview_focus=[],
        ),
        evidence=[
            VerifiedEvidence(requirement=r, claim="c", quote="q", verified=v, match_score=100)
            for r, v in evidence.items()
        ],
        grounding_rate=1.0,
        final_score=score,
    )


def test_coverage_distinguishes_leader_others_and_nobody() -> None:
    ranking = [
        _candidate("ana", 71, {"captação institucional (Series B/C)": True}),
        _candidate("diego", 27, {"Relação com investidores": True}),
        _candidate("carol", 25, {"Preparação para M&A": False}),
    ]
    coverage = {c.requirement: c for c in requirement_coverage(JOB, ranking)}

    assert set(coverage) == {
        "Captação institucional",
        "Preparação para M&A",
        "Relação com investidores",
    }
    assert coverage["Captação institucional"].status == "lider"
    assert coverage["Relação com investidores"].status == "outros"
    assert coverage["Relação com investidores"].covered_by == ["diego"]
    # Unverified evidence never counts as coverage.
    assert coverage["Preparação para M&A"].status == "ninguem"


def test_search_plan_trigger() -> None:
    strong = [_candidate("a", 90, {"Captação institucional": True})]
    full = requirement_coverage(
        JobProfile(
            **{
                **JOB.model_dump(),
                "hard_requirements": JOB.hard_requirements[:1],
                "soft_requirements": [],
            }
        ),
        strong,
    )
    assert not needs_search_plan(strong, full, threshold=80)
    assert needs_search_plan(strong, full, threshold=95)  # leader below threshold
    partial = requirement_coverage(JOB, strong)
    assert needs_search_plan(strong, partial, threshold=80)  # essentials uncovered


def test_weights_are_normalised() -> None:
    w = ScoreWeights(hard_skills=2, soft_skills=1, context_fit=1)
    assert (w.hard_skills, w.soft_skills, w.context_fit) == (0.5, 0.25, 0.25)
    with pytest.raises(ValueError, match="positive"):
        ScoreWeights(hard_skills=0, soft_skills=0, context_fit=0)
