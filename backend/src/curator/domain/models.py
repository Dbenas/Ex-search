"""Domain objects shared by ingestion, the agent and the API.

LLM-facing schemas (the ones passed to structured output) carry field
descriptions because they double as instructions to the model.
"""

from typing import Literal

from pydantic import BaseModel, Field

# --- Candidate data ---------------------------------------------------------


class ContactInfo(BaseModel):
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None


class CandidateIdentity(BaseModel):
    """Identifying data. Lives only in the vault, never goes to the LLM or the vector store."""

    candidate_id: str
    name: str
    contact: ContactInfo = Field(default_factory=ContactInfo)


class CandidateProfile(BaseModel):
    """Professional content used for matching. Contains no direct identifiers."""

    candidate_id: str
    alias: str
    current_role: str
    summary: str


class Chunk(BaseModel):
    chunk_id: str
    candidate_id: str
    text: str
    start: int
    end: int


# --- Job analysis (LLM output) ----------------------------------------------


class Requirement(BaseModel):
    name: str = Field(
        description="Competência ou experiência exigida, de forma curta e específica."
    )
    importance: Literal["essencial", "desejavel"]


class JobProfile(BaseModel):
    role_title: str = Field(description="Título normalizado da posição.")
    mandate: str = Field(
        description="O desafio central da posição em uma frase: o que essa pessoa precisa entregar."
    )
    company_context: str = Field(
        description="Estágio, setor e momento da empresa, conforme o texto da vaga."
    )
    hard_requirements: list[Requirement] = Field(
        description=(
            "Requisitos técnicos e de trajetória explícitos ou claramente implícitos na vaga."
        )
    )
    soft_requirements: list[Requirement] = Field(
        description="Traços comportamentais e de estilo de liderança pedidos pela vaga."
    )
    search_queries: list[str] = Field(
        description=(
            "De 3 a 5 frases curtas, em português, descrevendo o perfil ideal como ele "
            "apareceria num currículo. Usadas para busca semântica."
        )
    )


# --- Candidate assessment (LLM output) --------------------------------------


class DimensionScore(BaseModel):
    score: int = Field(ge=0, le=10, description="0 = sem aderência, 10 = aderência plena.")
    rationale: str = Field(description="Justificativa objetiva em até duas frases.")


class Evidence(BaseModel):
    requirement: str = Field(description="Requisito da vaga ao qual a evidência se refere.")
    claim: str = Field(description="O que a evidência demonstra sobre o candidato.")
    quote: str = Field(
        description=(
            "Trecho copiado literalmente do currículo, sem paráfrase, que sustenta a afirmação."
        )
    )


class CandidateAssessment(BaseModel):
    hard_skills: DimensionScore
    soft_skills: DimensionScore
    context_fit: DimensionScore = Field(
        description="Aderência ao momento da empresa e ao desafio central da posição."
    )
    evidence: list[Evidence] = Field(description="Evidências que sustentam a avaliação.")
    gaps: list[str] = Field(
        description=(
            "Até 5 requisitos essenciais da vaga sem evidência no currículo, do mais ao menos "
            "crítico. Não invente; apenas liste o que falta."
        )
    )
    interview_focus: list[str] = Field(
        description="Até 3 pontos que o sócio deveria aprofundar em entrevista."
    )


# --- Agent results ----------------------------------------------------------


class VerifiedEvidence(Evidence):
    verified: bool
    match_score: float
    start: int | None = None
    end: int | None = None


class ShortlistEntry(BaseModel):
    candidate_id: str
    retrieval_score: float
    matched_chunks: list[str]


class ScoredCandidate(BaseModel):
    candidate_id: str
    alias: str
    retrieval_score: float
    assessment: CandidateAssessment
    evidence: list[VerifiedEvidence]
    grounding_rate: float
    final_score: float


class CandidateNarrative(BaseModel):
    alias: str = Field(
        description="Identificador do candidato exatamente como fornecido (ex: CANDIDATO_01)."
    )
    headline: str = Field(description="Síntese do encaixe em uma linha, em tom de board.")
    analysis: str = Field(
        description=(
            "Parágrafo analítico (90 a 140 palavras) conectando hard skills e soft skills "
            "ao desafio da vaga, com ressalvas quando houver."
        )
    )
    recommendation: Literal["avancar", "avancar_com_ressalvas", "nao_priorizar"]


class MatchNarrative(BaseModel):
    executive_summary: str = Field(
        description="Leitura comparativa do shortlist em até 80 palavras, para o sócio responsável."
    )
    next_steps: list[str] = Field(
        description=(
            "2 a 4 próximos passos concretos para o sócio (o que verificar, com quem, "
            "e qual critério decide entre avançar e ampliar a busca)."
        )
    )
    candidates: list[CandidateNarrative]


# --- API-facing report ------------------------------------------------------


class RankedCandidate(BaseModel):
    rank: int
    candidate_id: str
    name: str
    current_role: str
    final_score: float
    retrieval_score: float
    grounding_rate: float
    scores: dict[str, DimensionScore]
    headline: str
    analysis: str
    recommendation: str
    evidence: list[VerifiedEvidence]
    gaps: list[str]
    interview_focus: list[str]
    profile_text: str


class RunMetadata(BaseModel):
    run_id: str
    model: str
    elapsed_ms: int
    candidates_screened: int
    pii_redactions: int
    llm_calls: int


class MatchReport(BaseModel):
    job: JobProfile
    executive_summary: str
    next_steps: list[str]
    top_candidates: list[RankedCandidate]
    also_considered: list[dict[str, str | float]]
    metadata: RunMetadata
