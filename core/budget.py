from __future__ import annotations

import logging
from dataclasses import dataclass

from core.usage import UsageStats

logger = logging.getLogger("model-chat.budget")

# Cost per 1M tokens (input, output) — approximations for common models
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3.5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
}
_DEFAULT_PRICING = (2.00, 8.00)  # conservative fallback


@dataclass
class Budget:
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    warn_at_tokens: int | None = None
    warn_at_cost_usd: float | None = None


class BudgetTracker:
    def __init__(self, budget: Budget):
        self.budget = budget
        self._total_prompt = 0
        self._total_completion = 0
        self._total_cost = 0.0
        self._warned_tokens = False
        self._warned_cost = False

    def record(self, usage: UsageStats, model: str) -> None:
        self._total_prompt += usage.prompt_tokens
        self._total_completion += usage.completion_tokens
        self._total_cost += self._estimate_cost(usage.prompt_tokens, usage.completion_tokens, model)

    def check(self) -> str:
        if self.budget.max_tokens and self.total_tokens >= self.budget.max_tokens:
            return "exceeded"
        if self.budget.max_cost_usd and self._total_cost >= self.budget.max_cost_usd:
            return "exceeded"
        if (
            not self._warned_tokens
            and self.budget.warn_at_tokens
            and self.total_tokens >= self.budget.warn_at_tokens
        ):
            self._warned_tokens = True
            return "warning"
        if (
            not self._warned_cost
            and self.budget.warn_at_cost_usd
            and self._total_cost >= self.budget.warn_at_cost_usd
        ):
            self._warned_cost = True
            return "warning"
        return "ok"

    @property
    def total_tokens(self) -> int:
        return self._total_prompt + self._total_completion

    @property
    def estimated_cost_usd(self) -> float:
        return self._total_cost

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        short = model.split("/")[-1] if "/" in model else model
        best_key = ""
        best_rates = _DEFAULT_PRICING
        for key, rates in _MODEL_PRICING.items():
            if key in short and len(key) > len(best_key):
                best_key = key
                best_rates = rates
        input_rate, output_rate = best_rates
        return (prompt_tokens / 1_000_000 * input_rate) + (
            completion_tokens / 1_000_000 * output_rate
        )
