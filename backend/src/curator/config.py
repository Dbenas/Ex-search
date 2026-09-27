from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: Literal["anthropic", "vertex", "gemini"] = "anthropic"
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-opus-5"
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_max_tokens: int = 16_000
    llm_timeout_s: float = 120.0
    # Server-side refusal fallback is only available on the first-party API.
    llm_refusal_fallback: bool = True
    gcp_project_id: str | None = None
    gcp_region: str = "global"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-pro-latest"
    gemini_use_vertex: bool = False
    # List prices in USD per million tokens (input, output), for cost estimates.
    model_prices: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {"claude-opus-5": (5.0, 25.0)}
    )

    # Retrieval
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_cache_dir: Path = BACKEND_ROOT / ".models"
    chroma_dir: Path = BACKEND_ROOT / ".chroma"
    collection_name: str = "executive_profiles"
    candidates_dir: Path = BACKEND_ROOT / "data" / "candidates"
    eval_cases_path: Path = BACKEND_ROOT / "data" / "eval" / "jobs.yaml"
    eval_reports_dir: Path = BACKEND_ROOT / "reports"
    feedback_path: Path = BACKEND_ROOT / ".runtime" / "feedback.jsonl"
    shortlist_size: int = Field(default=6, ge=3, le=20)
    top_k: int = Field(default=3, ge=1, le=5)

    # Scoring weights for the final ranking (must sum to 1).
    weight_hard_skills: float = 0.40
    weight_soft_skills: float = 0.30
    weight_context_fit: float = 0.30
    grounding_threshold: int = Field(default=85, ge=50, le=100)

    # API
    api_keys: list[SecretStr] = Field(default_factory=list)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    rate_limit_per_minute: int = 10
    log_level: str = "INFO"
    environment: Literal["local", "production"] = "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
