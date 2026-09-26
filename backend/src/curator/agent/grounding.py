"""Deterministic check that every piece of evidence quoted by the LLM exists in the CV.

This is the core anti-hallucination control: the model is asked to quote,
and code (not another LLM) verifies the quote. Unverified evidence is kept
for transparency but flagged, excluded from the narrative and it lowers the
candidate's final score.
"""

from rapidfuzz import fuzz

from curator.domain.models import Evidence, VerifiedEvidence

_STRIP = " \t\n\"'“”‘’.…"


def verify_evidence(evidence: Evidence, source: str, threshold: int) -> VerifiedEvidence:
    quote = evidence.quote.strip(_STRIP)
    if len(quote) < 3:
        return VerifiedEvidence(**evidence.model_dump(), verified=False, match_score=0.0)

    alignment = fuzz.partial_ratio_alignment(quote.lower(), source.lower())
    verified = alignment is not None and alignment.score >= threshold
    return VerifiedEvidence(
        **evidence.model_dump(),
        verified=verified,
        match_score=round(alignment.score if alignment else 0.0, 1),
        start=alignment.dest_start if verified and alignment else None,
        end=alignment.dest_end if verified and alignment else None,
    )


def grounding_rate(items: list[VerifiedEvidence]) -> float:
    if not items:
        return 0.0
    return round(sum(e.verified for e in items) / len(items), 3)
