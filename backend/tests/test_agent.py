import pytest
import yaml

from curator.config import Settings
from curator.service import CurationService
from tests.conftest import CTO_JOB, FakeLLM

pytestmark = pytest.mark.slow


def _jobs(settings: Settings) -> dict[str, dict[str, str]]:
    cases = yaml.safe_load(settings.eval_cases_path.read_text(encoding="utf-8"))
    return {c["id"]: c for c in cases}


@pytest.mark.parametrize("case_id", ["vaga-1-cto", "vaga-2-cfo"])
def test_hybrid_retrieval_ranks_expected_candidate_first(
    service: CurationService, settings: Settings, case_id: str
) -> None:
    case = _jobs(settings)[case_id]
    shortlist = service._deps.retriever.search([case["description"]], limit=4)
    assert shortlist[0].candidate_id == case["expected_top"]
    assert shortlist[0].retrieval_score == 1.0


async def test_pipeline_produces_grounded_top3(service: CurationService) -> None:
    report = await service.run(CTO_JOB)

    assert [c.rank for c in report.top_candidates] == [1, 2, 3]
    assert report.top_candidates[0].name == "Carolina Mendes"
    assert len(report.also_considered) == 1
    assert report.metadata.llm_calls == 1 + 4 + 1

    top = report.top_candidates[0]
    # The fake model fabricates one of two quotes; only the real one survives.
    assert top.grounding_rate == 0.5
    assert [e.verified for e in top.evidence] == [True, False]
    assert top.final_score < 90  # grounding penalty applied


async def test_names_are_restored_only_in_the_report(service: CurationService) -> None:
    report = await service.run(CTO_JOB)
    assert report.executive_summary == "Carolina Mendes lidera o shortlist."
    assert "CANDIDATO_" not in report.top_candidates[0].analysis


async def test_llm_never_sees_pii(service: CurationService, fake_llm: FakeLLM) -> None:
    fake_llm.prompts.clear()
    await service.run(CTO_JOB)
    sent = "\n".join(fake_llm.prompts)

    for profile in service.repo.profiles:
        identity = service.repo.identity(profile.candidate_id)
        assert identity.name not in sent
        assert identity.contact.email and identity.contact.email not in sent
        assert identity.contact.phone and identity.contact.phone not in sent
    assert "rh@empresa.com.br" not in sent
    assert "98888-7777" not in sent


async def test_stream_emits_every_stage_then_report(service: CurationService) -> None:
    stages = [e["stage"] async for e in service.stream(CTO_JOB) if e["type"] == "stage"]
    assert stages[:3] == ["sanitize", "analyze_job", "retrieve"]
    assert stages.count("assess") == 4
    assert stages[-2:] == ["rank", "synthesize"]


async def test_run_reports_token_usage_and_cost(service: CurationService) -> None:
    report = await service.run(CTO_JOB)
    meta = report.metadata
    # 6 calls x (1000 in, 200 out) recorded by the fake model.
    assert (meta.input_tokens, meta.output_tokens) == (6_000, 1_200)
    assert meta.cost_usd == round((6_000 * 1.0 + 1_200 * 5.0) / 1_000_000, 4)
