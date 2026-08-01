"""Retry wrapper for provider rate limits (HTTP 429)."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import Any

from autogen_core import CancellationToken
from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    LLMMessage,
    ModelCapabilities,  # type: ignore[attr-defined]
    ModelInfo,
    RequestUsage,
)
from autogen_core.tools import Tool, ToolSchema
from openai import APIStatusError, RateLimitError

logger = logging.getLogger(__name__)

# Free-tier Mistral often needs a longer cool-down than Gemini.
_DEFAULT_MAX_RETRIES = 5
_DEFAULT_BASE_DELAY_S = 3.0
_DEFAULT_MAX_DELAY_S = 60.0


def _is_rate_limit_error(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and getattr(exc, "status_code", None) == 429:
        return True
    message = str(exc).lower()
    return "rate limit" in message or "rate_limited" in message or "429" in message


def _retry_delay_seconds(attempt: int, *, base_delay: float, max_delay: float) -> float:
    # attempt 0 → base, then exponential with small jitter
    delay = min(max_delay, base_delay * (2**attempt))
    return delay + random.uniform(0.0, min(1.0, delay * 0.1))


class RateLimitRetryClient(ChatCompletionClient):
    """
    Delegate to an inner ChatCompletionClient; on 429 / RateLimitError sleep and retry.
    """

    def __init__(
        self,
        inner: ChatCompletionClient,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay_s: float = _DEFAULT_BASE_DELAY_S,
        max_delay_s: float = _DEFAULT_MAX_DELAY_S,
    ) -> None:
        self._inner = inner
        self._max_retries = max(0, max_retries)
        self._base_delay_s = base_delay_s
        self._max_delay_s = max_delay_s

    @property
    def model_info(self) -> ModelInfo:
        return self._inner.model_info

    @property
    def capabilities(self) -> ModelCapabilities:  # type: ignore[override]
        return self._inner.capabilities

    def count_tokens(
        self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = ()
    ) -> int:
        return self._inner.count_tokens(messages, tools=tools)

    def remaining_tokens(
        self, messages: Sequence[LLMMessage], *, tools: Sequence[Tool | ToolSchema] = ()
    ) -> int:
        return self._inner.remaining_tokens(messages, tools=tools)

    def total_usage(self) -> RequestUsage:
        return self._inner.total_usage()

    def actual_usage(self) -> RequestUsage:
        return self._inner.actual_usage()

    async def close(self) -> None:
        await self._inner.close()

    async def create(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
        tool_choice: Tool | str = "auto",
        json_output: bool | type | None = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: CancellationToken | None = None,
    ) -> CreateResult:
        last_exc: BaseException | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._inner.create(
                    messages,
                    tools=tools,
                    tool_choice=tool_choice,  # type: ignore[arg-type]
                    json_output=json_output,  # type: ignore[arg-type]
                    extra_create_args=extra_create_args,
                    cancellation_token=cancellation_token,
                )
            except Exception as exc:  # noqa: BLE001 — narrow via _is_rate_limit_error
                if not _is_rate_limit_error(exc) or attempt >= self._max_retries:
                    raise
                last_exc = exc
                delay = _retry_delay_seconds(
                    attempt,
                    base_delay=self._base_delay_s,
                    max_delay=self._max_delay_s,
                )
                logger.warning(
                    "Rate limit on model create (attempt %s/%s); sleeping %.1fs then retrying. %s",
                    attempt + 1,
                    self._max_retries + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    async def create_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[Tool | ToolSchema] = [],
        tool_choice: Tool | str = "auto",
        json_output: bool | type | None = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncGenerator[str | CreateResult, None]:
        last_exc: BaseException | None = None
        for attempt in range(self._max_retries + 1):
            yielded_any = False
            try:
                stream = self._inner.create_stream(
                    messages,
                    tools=tools,
                    tool_choice=tool_choice,  # type: ignore[arg-type]
                    json_output=json_output,  # type: ignore[arg-type]
                    extra_create_args=extra_create_args,
                    cancellation_token=cancellation_token,
                )
                async for item in stream:
                    yielded_any = True
                    yield item
                return
            except Exception as exc:  # noqa: BLE001
                # Don't retry mid-stream (would duplicate chunks); only before first yield.
                if (
                    yielded_any
                    or not _is_rate_limit_error(exc)
                    or attempt >= self._max_retries
                ):
                    raise
                last_exc = exc
                delay = _retry_delay_seconds(
                    attempt,
                    base_delay=self._base_delay_s,
                    max_delay=self._max_delay_s,
                )
                logger.warning(
                    "Rate limit on model stream (attempt %s/%s); sleeping %.1fs then retrying. %s",
                    attempt + 1,
                    self._max_retries + 1,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc
