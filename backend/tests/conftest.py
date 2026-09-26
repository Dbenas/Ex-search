import re
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from curator.config import BACKEND_ROOT, Settings
from curator.domain.models import (
    CandidateAssessment,
    CandidateNarrative,
    DimensionScore,
    Evidence,
    JobProfile,
    MatchNarrative,
    Requirement,
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
                    Evidence(requirement="trajetória", claim="Experiência", quote=first_sentence),
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
        raise AssertionError(f"unexpected schema {schema}")


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    tmp: Path = tmp_path_factory.mktemp("curator")
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        anthropic_api_key=None,
        chroma_dir=tmp / "chroma",
        embedding_cache_dir=BACKEND_ROOT / ".models",
        eval_report_path=tmp / "evaluation.json",
        feedback_path=tmp / "feedback.jsonl",
    )


@pytest.fixture(scope="session")
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture(scope="session")
def service(settings: Settings, fake_llm: FakeLLM) -> CurationService:
    return build_service(settings, llm=fake_llm)
