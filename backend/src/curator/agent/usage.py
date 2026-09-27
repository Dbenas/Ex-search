"""Per-run token accounting, shared across the concurrent nodes of one graph run.

The meter lives in a context variable: LangGraph runs nodes as asyncio tasks,
which inherit the context of the run that created them, so every LLM call in
a run records into the same meter without threading it through the graph.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class UsageMeter:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    models: set[str] = field(default_factory=set)

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1
        self.models.add(model)

    def cost_usd(self, prices: dict[str, tuple[float, float]], model: str) -> float | None:
        """Estimated cost from list prices per million tokens; None if the model is unpriced."""
        if model not in prices:
            return None
        input_price, output_price = prices[model]
        return round(
            (self.input_tokens * input_price + self.output_tokens * output_price) / 1_000_000, 4
        )


current_meter: ContextVar[UsageMeter | None] = ContextVar("current_meter", default=None)


def record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    meter = current_meter.get()
    if meter is not None:
        meter.record(model, input_tokens, output_tokens)
