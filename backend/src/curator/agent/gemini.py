"""Structured-output client for Gemini.

Same contract as ``ClaudeClient``: the graph is provider-agnostic, so both
models can be benchmarked on identical prompts, retrieval and verification.
Uses the Gemini API with a key; ``GEMINI_USE_VERTEX=true`` switches to Vertex
AI with Application Default Credentials, which is the production path on GCP.
"""

import asyncio
import time
from functools import cached_property
from typing import TypeVar

import structlog
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from curator.agent.llm import LLMError
from curator.agent.usage import record_usage
from curator.config import Settings

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_BLOCKED = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
}


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self.model = settings.gemini_model
        self._settings = settings
        # Caps parallel calls so the per-minute quota is respected instead of retried against.
        self._slots = asyncio.Semaphore(settings.llm_max_concurrency)

    @cached_property
    def _client(self) -> genai.Client:
        s = self._settings
        http = types.HttpOptions(
            timeout=int(s.llm_timeout_s * 1000),
            # Same policy as the Anthropic SDK: back off on rate limits and overload.
            retry_options=types.HttpRetryOptions(
                attempts=6,
                initial_delay=2.0,
                max_delay=60.0,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            ),
        )
        if s.gemini_use_vertex:
            if not s.gcp_project_id:
                raise LLMError("GCP_PROJECT_ID is required when GEMINI_USE_VERTEX=true")
            return genai.Client(
                vertexai=True, project=s.gcp_project_id, location=s.gcp_region, http_options=http
            )
        if not s.gemini_api_key or not s.gemini_api_key.get_secret_value():
            raise LLMError("GEMINI_API_KEY is not set")
        return genai.Client(api_key=s.gemini_api_key.get_secret_value(), http_options=http)

    async def generate(self, *, system: str, prompt: str, schema: type[T], task: str) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            max_output_tokens=self._settings.llm_max_tokens,
        )
        started = time.perf_counter()
        try:
            async with self._slots:
                response = await self._client.aio.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
        except errors.ClientError as exc:
            if exc.code in (401, 403):
                raise LLMError("invalid LLM credentials") from exc
            if exc.code == 429:
                raise LLMError("LLM rate limit reached, try again shortly") from exc
            raise LLMError(f"LLM rejected the request: {exc.message}") from exc
        except errors.ServerError as exc:
            raise LLMError(f"LLM provider error ({exc.code})") from exc

        usage = response.usage_metadata
        input_tokens = (usage.prompt_token_count or 0) if usage else 0
        # Thinking tokens are billed as output.
        output_tokens = (
            ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
            if usage
            else 0
        )
        record_usage(self.model, input_tokens, output_tokens)

        candidate = response.candidates[0] if response.candidates else None
        finish = candidate.finish_reason if candidate else None
        log.info(
            "llm.call",
            task=task,
            model=response.model_version or self.model,
            stop_reason=str(finish),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            raise LLMError(f"model declined the {task} step")
        if finish in _BLOCKED:
            raise LLMError(f"model declined the {task} step")
        if finish == types.FinishReason.MAX_TOKENS:
            raise LLMError(f"{task} output was truncated; raise LLM_MAX_TOKENS")
        if not response.text:
            raise LLMError(f"{task} returned no structured output")
        try:
            return schema.model_validate_json(response.text)
        except ValidationError as exc:
            raise LLMError(f"{task} returned output that does not match the schema") from exc
