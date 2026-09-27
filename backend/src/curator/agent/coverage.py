"""Which essential requirements does the candidate base actually cover?

Computed from verified evidence only, so it inherits the grounding guarantees:
a requirement counts as covered when some candidate has a quote, found in the
CV, that the assessment linked to it. This is what tells the partner whether
the gap is in the leading candidate or in the base itself.
"""

from rapidfuzz import fuzz

from curator.domain.models import JobProfile, RequirementCoverage, ScoredCandidate

MATCH_THRESHOLD = 80


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def _supports(candidate: ScoredCandidate, requirement: str) -> bool:
    target = _normalise(requirement)
    return any(
        e.verified and fuzz.token_set_ratio(_normalise(e.requirement), target) >= MATCH_THRESHOLD
        for e in candidate.evidence
    )


def requirement_coverage(
    job: JobProfile, ranking: list[ScoredCandidate]
) -> list[RequirementCoverage]:
    """Coverage of each essential requirement; ``ranking`` must be sorted best-first."""
    essentials = [(r.name, "hard") for r in job.hard_requirements if r.importance == "essencial"]
    essentials += [(r.name, "soft") for r in job.soft_requirements if r.importance == "essencial"]

    coverage = []
    for name, kind in essentials:
        covered_by = [c.candidate_id for c in ranking if _supports(c, name)]
        if ranking and ranking[0].candidate_id in covered_by:
            status = "lider"
        elif covered_by:
            status = "outros"
        else:
            status = "ninguem"
        coverage.append(
            RequirementCoverage(
                requirement=name,
                kind=kind,
                status=status,
                covered_by=covered_by,
            )
        )
    return coverage


def needs_search_plan(
    ranking: list[ScoredCandidate], coverage: list[RequirementCoverage], threshold: float
) -> bool:
    """A plan is worth generating when the leader is weak or leaves essentials uncovered."""
    if not ranking:
        return True
    return ranking[0].final_score < threshold or any(c.status != "lider" for c in coverage)
