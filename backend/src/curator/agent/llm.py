"""LLM clients with structured output.

Every call returns a validated Pydantic object, so the graph never parses free
text. ``build_llm`` picks the provider; the graph only knows ``StructuredLLM``.
Claude runs on the first-party API locally and on Vertex AI in production.
"""

import time
from functools import cached_property
from typing import Any, Protocol, TypeVar

import anthropic
import structlog
from pydantic import BaseModel

from curator.agent.usage import record_usage
from curator.config import Settings

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    """Raised when the model call fails in a way the caller should surface."""


class StructuredLLM(Protocol):
    model: str

    async def generate(self, *, system: str, prompt: str, schema: type[T], task: str) -> T: ...


class ClaudeClient:
    def __init__(self, settings: Settings) -> None:
        self.model = settings.llm_model
        self._effort = settings.llm_effort
        self._max_tokens = settings.llm_max_tokens
        self._settings = settings
        self._fallback = settings.llm_refusal_fallback and settings.llm_provider != "vertex"

    @cached_property
    def _client(self) -> Any:
        """Built on first use so the API can boot (health, candidates) without credentials."""
        settings = self._settings
        if settings.llm_provider == "vertex":
            if not settings.gcp_project_id:
                raise LLMError("GCP_PROJECT_ID is required when LLM_PROVIDER=vertex")
            return anthropic.AsyncAnthropicVertex(
                project_id=settings.gcp_project_id,
                region=settings.gcp_region,
                timeout=settings.llm_timeout_s,
            )
        if not settings.anthropic_api_key or not settings.anthropic_api_key.get_secret_value():
            raise LLMError("ANTHROPIC_API_KEY is not set")
        return anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.llm_timeout_s,
            max_retries=3,
        )

    async def generate(self, *, system: str, prompt: str, schema: type[T], task: str) -> T:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "output_format": schema,
            "output_config": {"effort": self._effort},
        }
        if self._fallback:
            kwargs |= {"betas": [REFUSAL_FALLBACK_BETA], "fallbacks": "default"}

        started = time.perf_counter()
        try:
            response = await self._client.beta.messages.parse(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise LLMError("invalid LLM credentials") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("LLM rate limit reached, try again shortly") from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"LLM rejected the request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"LLM provider error ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("could not reach the LLM provider") from exc

        record_usage(self.model, response.usage.input_tokens, response.usage.output_tokens)
        log.info(
            "llm.call",
            task=task,
            model=response.model,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            request_id=getattr(response, "_request_id", None),
        )

        if response.stop_reason == "refusal":
            raise LLMError(f"model declined the {task} step")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"{task} output was truncated; raise LLM_MAX_TOKENS")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"{task} returned no structured output")
        return parsed  # type: ignore[no-any-return]


def build_llm(settings: Settings, provider: str | None = None) -> StructuredLLM:
    """Client for ``provider`` (defaults to ``LLM_PROVIDER``)."""
    if (provider or settings.llm_provider) == "gemini":
        from curator.agent.gemini import GeminiClient

        return GeminiClient(settings)
    return ClaudeClient(settings)
