import pytest

from curator.agent.grounding import verify_evidence
from curator.config import Settings
from curator.domain.models import Evidence, JobProfile, ScoreWeights
from curator.evaluation.bias import (
    counterfactual_gender,
    estimate_calls,
    gender_invariance,
    gender_leakage,
    name_invariance,
)
from curator.ingestion.loader import CandidateRepository, load_raw_candidates
from curator.privacy.gender_signals import find_gender_signals, to_unmarked
from curator.service import CurationService
from tests.conftest import CTO_JOB, FakeLLM

JOB = JobProfile(
    role_title="CTO",
    mandate="m",
    company_context="c",
    hard_requirements=[],
    soft_requirements=[],
    search_queries=[],
)


def test_only_feminine_forms_are_signals() -> None:
    text = "Perfil pragmático, voltado para resultados. Acostumada a pressão; ela é diretora."
    assert [s.term for s in find_gender_signals(text)] == ["Acostumada", "ela", "diretora"]


def test_unmarked_counterfactual_keeps_case_and_rest_of_text() -> None:
    text = "Acostumada a ambientes de pressão, formada em Matemática."
    assert to_unmarked(text) == "Acostumado a ambientes de pressão, formado em Matemática."


def test_quote_from_neutralised_text_still_verifies_against_original() -> None:
    original = "Perfil inovador, acostumada a ambientes de alta pressão e pouca estrutura."
    evidence = Evidence(
        requirement="r", claim="c", quote="acostumado a ambientes de alta pressão e pouca estrutura"
    )
    result = verify_evidence(evidence, original, threshold=85)
    assert result.verified and result.start is not None


def test_names_cannot_change_what_the_model_reads(settings: Settings) -> None:
    raw = load_raw_candidates(settings.candidates_dir)
    report = name_invariance(raw, JOB, settings)
    assert report["passed"]
    assert {c["swapped_name"] for c in report["checks"]} >= {"André Souza", "Camila Rocha"}


def test_gender_cues_are_found_and_neutralised(settings: Settings) -> None:
    repo = CandidateRepository.from_directory(settings.candidates_dir)
    leakage = gender_leakage(repo)
    assert [(f["candidate_id"], f["terms"]) for f in leakage] == [
        ("cand-carolina-mendes", ["acostumada"])
    ]
    assert gender_invariance(repo, JOB, settings)["passed"]
    exposed = settings.model_copy(update={"neutralize_gender_cues": False})
    assert not gender_invariance(repo, JOB, exposed)["passed"]


async def test_model_never_reads_gender_cues(service: CurationService, fake_llm: FakeLLM) -> None:
    fake_llm.prompts.clear()
    await service.run(CTO_JOB)
    assert "acostumada" not in "\n".join(fake_llm.prompts).lower()


async def test_counterfactual_reports_no_effect_for_an_unbiased_model(
    settings: Settings, fake_llm: FakeLLM
) -> None:
    repo = CandidateRepository.from_directory(settings.candidates_dir)
    assert estimate_calls(repo, repeats=2) == 1 + 2 * 2
    [result] = await counterfactual_gender(fake_llm, repo, JOB, repeats=2, weights=ScoreWeights())
    assert result["mean_delta"] == 0
    assert result["verdict"].startswith("sem efeito")


@pytest.mark.parametrize("term", ["acostumada", "formada", "executiva", "sócia"])
def test_known_cues_are_detected(term: str) -> None:
    assert find_gender_signals(f"Profissional {term} em finanças")
