from __future__ import annotations

import time
from dataclasses import dataclass, field

from autogen_core.models import ChatCompletionClient

from loan_negotiation.models.workflow import LlmRunMetrics


@dataclass
class RunMetricsCollector:
    """Wall-clock + token usage for a negotiation run."""

    model: str
    _started: float = field(default_factory=time.perf_counter)
    _first_output_at: float | None = None

    def mark_first_model_output(self) -> None:
        if self._first_output_at is None:
            self._first_output_at = time.perf_counter()

    def snapshot(self, model_client: ChatCompletionClient | None = None) -> LlmRunMetrics:
        ended = time.perf_counter()
        prompt_tokens = 0
        completion_tokens = 0
        if model_client is not None:
            usage = getattr(model_client, "total_usage", None)
            if callable(usage):
                tallied = usage()
                prompt_tokens = int(getattr(tallied, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(tallied, "completion_tokens", 0) or 0)
            else:
                tallied = getattr(model_client, "_total_usage", None)
                if tallied is not None:
                    prompt_tokens = int(getattr(tallied, "prompt_tokens", 0) or 0)
                    completion_tokens = int(getattr(tallied, "completion_tokens", 0) or 0)

        ttft_ms = None
        if self._first_output_at is not None:
            ttft_ms = round((self._first_output_at - self._started) * 1000.0, 1)

        return LlmRunMetrics(
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            time_to_first_token_ms=ttft_ms,
            duration_ms=round((ended - self._started) * 1000.0, 1),
        )


def is_model_output_agent(agent: str) -> bool:
    """True for emits that come from LLM-backed agents (not control-plane system lines)."""
    return agent in {
        "intake_agent",
        "reviewer_agent",
        "Borrower",
        "Lender",
        "offer_extractor",
    }
