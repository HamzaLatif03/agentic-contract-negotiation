"""Tests for API rate-limit retry wrapper."""

from unittest.mock import AsyncMock

import pytest
from openai import RateLimitError

from loan_negotiation.agents.rate_limit_retry import (
    RateLimitRetryClient,
    _is_rate_limit_error,
)


class _FakeRateLimit(RateLimitError):
    def __init__(self) -> None:
        super().__init__(
            message="Rate limit exceeded",
            response=type(
                "R",
                (),
                {
                    "status_code": 429,
                    "headers": {},
                    "request": type("Req", (), {"url": "https://example.com"})(),
                },
            )(),
            body={"message": "Rate limit exceeded", "type": "rate_limited", "code": "1300"},
        )


def test_is_rate_limit_detects_message():
    assert _is_rate_limit_error(RuntimeError("Error code: 429 - rate_limited")) is True
    assert _is_rate_limit_error(RuntimeError("something else")) is False


@pytest.mark.asyncio
async def test_create_retries_then_succeeds(monkeypatch):
    inner = AsyncMock()
    ok = object()
    inner.create = AsyncMock(
        side_effect=[
            _FakeRateLimit(),
            _FakeRateLimit(),
            ok,
        ]
    )
    # Usage/info stubs for abstract surface if touched
    inner.model_info = {"vision": False}
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(
        "loan_negotiation.agents.rate_limit_retry.asyncio.sleep", fake_sleep
    )

    client = RateLimitRetryClient(inner, max_retries=5, base_delay_s=0.01, max_delay_s=1.0)
    result = await client.create([])
    assert result is ok
    assert inner.create.await_count == 3
    assert len(delays) == 2


@pytest.mark.asyncio
async def test_create_gives_up_after_max_retries(monkeypatch):
    inner = AsyncMock()
    inner.create = AsyncMock(side_effect=_FakeRateLimit())

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "loan_negotiation.agents.rate_limit_retry.asyncio.sleep", fake_sleep
    )

    client = RateLimitRetryClient(inner, max_retries=2, base_delay_s=0.01)
    with pytest.raises(RateLimitError):
        await client.create([])
    assert inner.create.await_count == 3  # initial + 2 retries
