import pytest
from pydantic import SecretStr

from curator.agent.gemini import GeminiClient
from curator.agent.llm import ClaudeClient, LLMError, build_llm
from curator.agent.usage import UsageMeter
from curator.config import Settings


def test_factory_selects_provider(settings: Settings) -> None:
    assert isinstance(build_llm(settings, "anthropic"), ClaudeClient)
    assert isinstance(build_llm(settings, "gemini"), GeminiClient)
    gemini = settings.model_copy(update={"llm_provider": "gemini"})
    assert isinstance(build_llm(gemini), GeminiClient)


async def test_missing_credentials_fail_on_first_call_not_at_boot(settings: Settings) -> None:
    client = build_llm(settings.model_copy(update={"gemini_api_key": SecretStr("")}), "gemini")
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        await client.generate(system="s", prompt="p", schema=Settings, task="t")


def test_unpriced_model_has_no_cost() -> None:
    meter = UsageMeter()
    meter.record("m", 1_000_000, 0)
    assert meter.cost_usd({"m": (2.0, 10.0)}, "m") == 2.0
    assert meter.cost_usd({}, "m") is None
