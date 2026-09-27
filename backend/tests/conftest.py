import re
import shutil
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from curator.agent.usage import record_usage
from curator.config import BACKEND_ROOT, Settings
from curator.domain.models import (
    CandidateAssessment,
    CandidateNarrative,
    DimensionScore,
    Evidence,
    JobProfile,
    MatchNarrative,
    Requirement,
    SearchPlan,
    TargetProfile,
)
from curator.service import CurationService, build_service

T = TypeVar("T", bound=BaseModel)

CTO_JOB = (
    "Startup B2B de rápido crescimento busca CTO com forte viés em IA e dados. "
    "Necessário perfil hands-on para escalar o time técnico e construir arquitetura "
    "escalável do zero. Contato: rh@empresa.com.br, (11) 98888-7777."
)

# Scores the fake model gives per alias; CANDIDATO_03 is Carolina (ids sort alphabetically).
FAKE_SCORES = {"CANDIDATO_01": 4, "CANDIDATO_02": 6, "CANDIDATO_03": 9, "CANDIDATO_04": 2}


class FakeLLM:
    """Deterministic stand-in for Claude that records every prompt it receives."""

    model = "fake-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, *, system: str, prompt: str, schema: type[T], task: str) -> T:
        self.prompts.append(system + "\n" + prompt)
        record_usage(self.model, 1_000, 200)
        return schema.model_validate(self._answer(prompt, schema))

    def _answer(self, prompt: str, schema: type[BaseModel]) -> Any:
        if schema is JobProfile:
            return JobProfile(
                role_title="CTO",
                mandate="Construir a área de tecnologia e dados do zero",
                company_context="Startup B2B em crescimento",
                hard_requirements=[Requirement(name="IA e dados", importance="essencial")],
                soft_requirements=[Requirement(name="adaptabilidade", importance="essencial")],
                search_queries=["CTO hands-on com IA", "escala times do zero"],
            )
        if schema is CandidateAssessment:
            alias = re.search(r'<perfil id="(CANDIDATO_\d+)">', prompt)
            profile = re.search(r"<perfil[^>]*>\n(.*?)\n</perfil>", prompt, re.S)
            assert alias and profile
            score = FAKE_SCORES[alias.group(1)]
            first_sentence = profile.group(1).split(".")[0]
            dim = DimensionScore(score=score, rationale=f"Nota {score} para {alias.group(1)}.")
            return CandidateAssessment(
                hard_skills=dim,
                soft_skills=dim,
                context_fit=dim,
                evidence=[
                    Evidence(
                        requirement="IA e dados",
                        claim=f"{alias.group(1)} tem experiência",
                        quote=first_sentence,
                    ),
                    Evidence(requirement="IA", claim="Inventado", quote="PhD em robótica pelo MIT"),
                ],
                gaps=["Sem evidência de board"],
                interview_focus=[f"Explorar liderança de {alias.group(1)}"],
            )
        if schema is MatchNarrative:
            aliases = re.findall(r'<candidato id="(CANDIDATO_\d+)"', prompt)
            return MatchNarrative(
                executive_summary=f"{aliases[0]} lidera o shortlist.",
                next_steps=[f"Checar referências de {aliases[0]}"],
                candidates=[
                    CandidateNarrative(
                        alias=a,
                        headline=f"{a} tem aderência",
                        analysis=f"Análise de {a}.",
                        recommendation="avancar",
                    )
                    for a in aliases
                ],
            )
        if schema is SearchPlan:
            return SearchPlan(
                diagnosis="A base não cobre adaptabilidade.",
                target_profiles=[
                    TargetProfile(archetype="CTO de scale-up", rationale="r", trade_off="t")
                ],
                source_segments=["SaaS B2B"],
                boolean_queries=['("CTO") AND ("IA")'],
                screening_questions=["Que arquitetura você construiu do zero?"],
            )
        raise AssertionError(f"unexpected schema {schema}")


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    tmp: Path = tmp_path_factory.mktemp("curator")
    # Uploads write CV files: work on a copy so tests never touch the real base.
    candidates = tmp / "candidates"
    shutil.copytree(BACKEND_ROOT / "data" / "candidates", candidates)
    return Settings(
        candidates_dir=candidates,
        _env_file=None,  # type: ignore[call-arg]
        anthropic_api_key=None,
        chroma_dir=tmp / "chroma",
        embedding_cache_dir=BACKEND_ROOT / ".models",
        eval_reports_dir=tmp / "reports",
        feedback_path=tmp / "feedback.jsonl",
        model_prices={"fake-model": (1.0, 5.0)},
    )


@pytest.fixture(scope="session")
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture(scope="session")
def service(settings: Settings, fake_llm: FakeLLM) -> CurationService:
    return build_service(settings, llm=fake_llm)
