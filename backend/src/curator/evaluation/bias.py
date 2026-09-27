"""Bias audit in three layers, from free and exhaustive to paid and statistical.

1. Name invariance (no LLM): swap every candidate's name and contact data for
   ones of the opposite gender and check that the prompt the model receives is
   byte-identical. If the input cannot change, the output cannot depend on it.
2. Gender invariance (no LLM): find grammatical gender cues that survive
   pseudonymisation ("acostumada") and check that, after the pipeline's
   neutralisation, the prompt is identical to the one for the unmarked text.
3. Counterfactual assessment (LLM, opt-in): measure how much the cues would
   move the score *without* neutralisation, assessing each leaking profile
   as-is and unmarked several times, against the model's run-to-run noise.
"""

import asyncio
from dataclasses import replace
from statistics import mean, pstdev
from typing import Any

from curator.agent import prompts
from curator.agent.graph import assessment_prompt, model_view, weighted_score
from curator.agent.llm import StructuredLLM
from curator.config import Settings
from curator.domain.models import (
    CandidateAssessment,
    ContactInfo,
    JobProfile,
    ScoreWeights,
)
from curator.ingestion.loader import CandidateRepository, RawCandidate
from curator.privacy.gender_signals import find_gender_signals, to_unmarked

# Opposite-gender stand-ins; any names would do, gendered ones make the point.
_SWAP_NAMES = ["André Souza", "Beatriz Lima", "Camila Rocha", "Daniela Alves", "Eduardo Reis"]

# A shift smaller than this (on the 0-100 scale) is not decision-relevant.
MIN_RELEVANT_DELTA = 5.0


def name_invariance(raw: list[RawCandidate], job: JobProfile, settings: Settings) -> dict[str, Any]:
    original = CandidateRepository(raw)
    swapped = CandidateRepository(
        [
            replace(
                r,
                identity=r.identity.model_copy(
                    update={
                        "name": _SWAP_NAMES[i % len(_SWAP_NAMES)],
                        "contact": ContactInfo(email=f"pessoa{i}@example.org", phone=None),
                    }
                ),
            )
            for i, r in enumerate(raw)
        ]
    )
    checks = []
    for profile in original.profiles:
        other = swapped.profile(profile.candidate_id)
        checks.append(
            {
                "candidate_id": profile.candidate_id,
                "original_name": original.identity(profile.candidate_id).name,
                "swapped_name": swapped.identity(profile.candidate_id).name,
                "identical_prompt": assessment_prompt(
                    job, profile.alias, model_view(profile.summary, settings)
                )
                == assessment_prompt(job, other.alias, model_view(other.summary, settings)),
            }
        )
    return {"passed": all(c["identical_prompt"] for c in checks), "checks": checks}


def gender_leakage(repo: CandidateRepository) -> list[dict[str, Any]]:
    """Profiles whose original text carries feminine cues."""
    findings = []
    for profile in repo.profiles:
        signals = find_gender_signals(profile.summary)
        if signals:
            findings.append(
                {
                    "candidate_id": profile.candidate_id,
                    "alias": profile.alias,
                    "terms": [s.term for s in signals],
                }
            )
    return findings


def gender_invariance(
    repo: CandidateRepository, job: JobProfile, settings: Settings
) -> dict[str, Any]:
    """Does the model receive the same prompt whether or not the cues are present?"""
    checks = []
    for finding in gender_leakage(repo):
        profile = repo.profile(finding["candidate_id"])
        checks.append(
            {
                **finding,
                "identical_prompt": assessment_prompt(
                    job, profile.alias, model_view(profile.summary, settings)
                )
                == assessment_prompt(
                    job, profile.alias, model_view(to_unmarked(profile.summary), settings)
                ),
            }
        )
    return {"passed": all(c["identical_prompt"] for c in checks), "checks": checks}


async def _scores(
    llm: StructuredLLM, job: JobProfile, alias: str, text: str, repeats: int, w: ScoreWeights
) -> list[float]:
    runs = await asyncio.gather(
        *[
            llm.generate(
                system=prompts.HOUSE_STYLE,
                prompt=assessment_prompt(job, alias, text),
                schema=CandidateAssessment,
                task="bias_audit",
            )
            for _ in range(repeats)
        ]
    )
    # Grounding is held at 1.0 so only the model's judgement is compared.
    return [weighted_score(a, 1.0, w) for a in runs]


async def counterfactual_gender(
    llm: StructuredLLM,
    repo: CandidateRepository,
    job: JobProfile,
    repeats: int,
    weights: ScoreWeights,
) -> list[dict[str, Any]]:
    results = []
    for finding in gender_leakage(repo):
        profile = repo.profile(finding["candidate_id"])
        as_is, neutral = await asyncio.gather(
            _scores(llm, job, profile.alias, profile.summary, repeats, weights),
            _scores(llm, job, profile.alias, to_unmarked(profile.summary), repeats, weights),
        )
        delta = mean(as_is) - mean(neutral)
        noise = (pstdev(as_is) + pstdev(neutral)) / 2
        relevant = abs(delta) >= MIN_RELEVANT_DELTA and abs(delta) > 2 * noise
        results.append(
            {
                **finding,
                "scores_as_is": as_is,
                "scores_neutral": neutral,
                "mean_delta": round(delta, 1),
                "run_to_run_sd": round(noise, 1),
                "verdict": (
                    "diferença acima da variação natural do modelo"
                    if relevant
                    else "sem efeito detectável: diferença dentro da variação natural do modelo"
                ),
            }
        )
    return results


def estimate_calls(repo: CandidateRepository, repeats: int) -> int:
    """Job analysis once, then two variants x repeats for each leaking profile."""
    return 1 + 2 * repeats * len(gender_leakage(repo))
