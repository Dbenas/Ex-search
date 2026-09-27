from typing import Literal

from pydantic import BaseModel, Field

from curator.domain.models import ScoreWeights


class MatchRequest(BaseModel):
    job_description: str = Field(min_length=80, max_length=8_000)
    weights: ScoreWeights | None = None


class CandidateSummary(BaseModel):
    candidate_id: str
    name: str
    current_role: str
    profile_text: str
    source: Literal["base", "upload"]


class FeedbackRequest(BaseModel):
    run_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    candidate_id: str = Field(max_length=80)
    verdict: Literal["agree", "disagree"]
    comment: str | None = Field(default=None, max_length=1_000)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    candidates: int
    model: str
