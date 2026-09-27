"""Offline evaluation against the reference job descriptions.

Three layers, from objective to subjective:
1. Ranking: is the expected candidate first? (hit@1, reciprocal rank)
2. Grounding: share of cited evidence found verbatim in the CVs.
3. Memo quality: LLM-as-judge with an explicit rubric (tone, usefulness,
   consistency with evidence). Useful as a regression signal, not as truth;
   the real benchmark is agreement with partners' shortlists over time.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import yaml
from pydantic import BaseModel, Field

from curator.agent.llm import StructuredLLM
from curator.domain.models import MatchReport
from curator.service import CurationService

JUDGE_SYSTEM = """\
Você é sócio sênior de uma consultoria de executive search e revisa pareceres \
produzidos por analistas antes de irem ao cliente. Seja exigente e específico."""

JUDGE_PROMPT = """\
Avalie o parecer abaixo, produzido para a vaga descrita. Use a escala de 1 a 5 \
(5 = pronto para ir ao cliente sem edição).

<vaga>
{job}
</vaga>

<parecer>
{memo}
</parecer>

<curriculos_de_referencia>
{profiles}
</curriculos_de_referencia>

Critérios:
- executive_tone: analítico, estratégico, sem jargão de varejo.
- decision_usefulness: ajuda o sócio a decidir (trade-offs claros, ressalvas, próximos passos).
- factual_consistency: nada no parecer contradiz ou extrapola os currículos."""


class JudgeVerdict(BaseModel):
    executive_tone: int = Field(ge=1, le=5)
    decision_usefulness: int = Field(ge=1, le=5)
    factual_consistency: int = Field(ge=1, le=5)
    critique: str = Field(description="Principal ponto de melhoria, em uma ou duas frases.")


class CaseResult(BaseModel):
    case_id: str
    title: str
    expected_top: str
    predicted_ranking: list[str]
    hit_at_1: bool
    reciprocal_rank: float
    grounding_rate: float
    judge: JudgeVerdict | None
    report: MatchReport


def _memo(report: MatchReport) -> str:
    parts = [f"Resumo: {report.executive_summary}"]
    for c in report.top_candidates:
        parts.append(f"{c.rank}. {c.name} ({c.final_score}): {c.headline}\n{c.analysis}")
    return "\n\n".join(parts)


async def evaluate(
    service: CurationService, cases: list[dict[str, str]], judge: StructuredLLM | None
) -> dict[str, Any]:
    profiles = "\n".join(f"- {p.current_role}: {p.summary}" for p in service.repo.profiles)
    results: list[CaseResult] = []

    for case in cases:
        report = await service.run(case["description"])
        ranking = [c.candidate_id for c in report.top_candidates] + [
            str(c["candidate_id"]) for c in report.also_considered
        ]
        rr = (
            1 / (ranking.index(case["expected_top"]) + 1)
            if case["expected_top"] in ranking
            else 0.0
        )
        verdict = None
        if judge is not None:
            verdict = await judge.generate(
                system=JUDGE_SYSTEM,
                prompt=JUDGE_PROMPT.format(
                    job=case["description"], memo=_memo(report), profiles=profiles
                ),
                schema=JudgeVerdict,
                task="judge",
            )
        results.append(
            CaseResult(
                case_id=case["id"],
                title=case["title"],
                expected_top=case["expected_top"],
                predicted_ranking=ranking,
                hit_at_1=ranking[:1] == [case["expected_top"]],
                reciprocal_rank=round(rr, 3),
                grounding_rate=round(mean(c.grounding_rate for c in report.top_candidates), 3),
                judge=verdict,
                report=report,
            )
        )

    judged = [r.judge for r in results if r.judge]
    meta = [r.report.metadata for r in results]
    costs = [m.cost_usd for m in meta if m.cost_usd is not None]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": service.model,
        "judge_model": judge.model if judge else None,
        "summary": {
            "cases": len(results),
            "avg_elapsed_s": round(mean(m.elapsed_ms for m in meta) / 1000, 1),
            "avg_input_tokens": round(mean(m.input_tokens for m in meta)),
            "avg_output_tokens": round(mean(m.output_tokens for m in meta)),
            "avg_cost_usd": round(mean(costs), 4) if len(costs) == len(meta) else None,
            "hit_at_1": round(mean(r.hit_at_1 for r in results), 3),
            "mrr": round(mean(r.reciprocal_rank for r in results), 3),
            "grounding_rate": round(mean(r.grounding_rate for r in results), 3),
            "judge_executive_tone": round(mean(j.executive_tone for j in judged), 2)
            if judged
            else None,
            "judge_decision_usefulness": (
                round(mean(j.decision_usefulness for j in judged), 2) if judged else None
            ),
            "judge_factual_consistency": (
                round(mean(j.factual_consistency for j in judged), 2) if judged else None
            ),
        },
        "cases": [r.model_dump(mode="json") for r in results],
    }


def load_cases(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return cases


def write_report(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
