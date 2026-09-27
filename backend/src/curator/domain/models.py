"""Domain objects shared by ingestion, the agent and the API.

LLM-facing schemas (the ones passed to structured output) carry field
descriptions because they double as instructions to the model.
"""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

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
    requirement: str = Field(
        description="Nome do requisito da vaga, copiado exatamente como aparece no mandato."
    )
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


# --- Scoring ------------------------------------------------------------------


class ScoreWeights(BaseModel):
    """Relative weight of each dimension in the final score; normalised to sum 1."""

    hard_skills: float = Field(default=0.40, ge=0)
    soft_skills: float = Field(default=0.30, ge=0)
    context_fit: float = Field(default=0.30, ge=0)

    @model_validator(mode="after")
    def _normalise(self) -> Self:
        total = self.hard_skills + self.soft_skills + self.context_fit
        if total <= 0:
            raise ValueError("at least one weight must be positive")
        self.hard_skills = round(self.hard_skills / total, 4)
        self.soft_skills = round(self.soft_skills / total, 4)
        self.context_fit = round(self.context_fit / total, 4)
        return self


# --- Search plan (LLM output) ------------------------------------------------


class TargetProfile(BaseModel):
    archetype: str = Field(
        description=(
            "Arquétipo de executivo a buscar, específico (ex: CFO de SaaS B2B pós-Series C)."
        )
    )
    rationale: str = Field(description="Por que esse arquétipo cobre as lacunas do mandato.")
    trade_off: str = Field(description="O que se tende a perder ao priorizar esse arquétipo.")


class SearchPlan(BaseModel):
    diagnosis: str = Field(
        description="Por que a base atual não cobre o mandato por completo, em até 60 palavras."
    )
    target_profiles: list[TargetProfile] = Field(description="De 2 a 3 arquétipos alternativos.")
    source_segments: list[str] = Field(
        description=(
            "Segmentos e tipos de empresa onde esses perfis costumam estar. Descreva o tipo "
            "de empresa, sem citar nomes de empresas ou de pessoas."
        )
    )
    boolean_queries: list[str] = Field(
        description="De 2 a 3 buscas booleanas prontas para LinkedIn Recruiter, com termos PT e EN."
    )
    screening_questions: list[str] = Field(
        description="De 3 a 4 perguntas para qualificar rapidamente um novo nome por telefone."
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


class CandidateScores(BaseModel):
    """Everything needed to re-rank a candidate client-side under different weights."""

    candidate_id: str
    name: str
    scores: dict[str, int]
    grounding_rate: float
    retrieval_score: float
    final_score: float


class RequirementCoverage(BaseModel):
    requirement: str
    kind: Literal["hard", "soft"]
    status: Literal["lider", "outros", "ninguem"]
    covered_by: list[str]


class UploadReport(BaseModel):
    """What happened to a CV added through the interface, shown to the partner."""

    candidate_id: str
    name: str
    current_role: str
    name_detected: bool
    contacts_found: list[str]
    pii_removed: int
    chunks_indexed: int
    gender_cues: list[str]
    indexed_text: str


class RunMetadata(BaseModel):
    run_id: str
    model: str
    elapsed_ms: int
    candidates_screened: int
    pii_redactions: int
    llm_calls: int
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None


class MatchReport(BaseModel):
    job: JobProfile
    executive_summary: str
    next_steps: list[str]
    top_candidates: list[RankedCandidate]
    also_considered: list[dict[str, str | float]]
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    assessed: list[CandidateScores] = Field(default_factory=list)
    coverage: list[RequirementCoverage] = Field(default_factory=list)
    search_plan: SearchPlan | None = None
    metadata: RunMetadata
