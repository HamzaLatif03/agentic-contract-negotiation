from collections.abc import Awaitable, Callable
from typing import Any

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
from autogen_core.models import ChatCompletionClient, ModelInfo
from autogen_core.tools import BaseTool
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient

from loan_negotiation.agents.rate_limit_retry import RateLimitRetryClient
from loan_negotiation.config import Settings, get_settings
from loan_negotiation.services.model_catalog import (
    find_comparison_model,
    preferred_ollama_name,
    provider_api_key,
    provider_base_url,
)
from loan_negotiation.services.ollama_check import list_ollama_models

Tool = BaseTool[Any, Any] | Callable[..., Any] | Callable[..., Awaitable[Any]]

_MODEL_INFO = ModelInfo(
    vision=False,
    function_calling=True,
    json_output=True,
    family="unknown",
    structured_output=True,
)


async def ask_agent(agent: AssistantAgent, prompt: str) -> str:
    response = await agent.on_messages(
        [TextMessage(content=prompt, source="user")],
        cancellation_token=CancellationToken(),
    )
    return response.chat_message.to_text()


def create_model_client(settings: Settings | None = None) -> ChatCompletionClient:
    """Build an AutoGen model client (provider API or local Ollama)."""
    settings = settings or get_settings()
    entry = find_comparison_model(settings.model)

    if entry is not None and entry.runtime == "api":
        api_key = provider_api_key(entry)
        base_url = provider_base_url(entry)
        if not api_key:
            needed = entry.key_env[0] if entry.key_env else "API key"
            raise RuntimeError(
                f"Model '{entry.label}' needs {needed} in your local .env "
                f"(or the process environment)."
            )
        if not base_url:
            raise RuntimeError(f"Model '{entry.label}' has no API base URL configured.")
        inner = OpenAIChatCompletionClient(
            model=entry.model_id,
            api_key=api_key,
            base_url=base_url,
            model_info=_MODEL_INFO,
        )
        # Mistral free tier (and other APIs) can 429 mid-run; retry with backoff.
        return RateLimitRetryClient(inner)

    # Ollama path: catalog local entry, or raw OLLAMA_MODEL / installed tag.
    ollama_model = settings.model
    if entry is not None and entry.runtime == "ollama":
        try:
            installed = list_ollama_models(settings.ollama_base_url)
        except Exception:  # noqa: BLE001
            installed = []
        ollama_model = preferred_ollama_name(installed, entry.model_id) or entry.model_id

    options: dict[str, Any] = {}
    num_gpu = settings.resolved_ollama_num_gpu()
    if num_gpu is not None:
        options["num_gpu"] = num_gpu

    return OllamaChatCompletionClient(
        model=ollama_model,
        host=settings.ollama_base_url,
        model_info=_MODEL_INFO,
        options=options or None,
    )


def create_assistant_agent(
    name: str,
    system_message: str,
    *,
    description: str | None = None,
    model_client: ChatCompletionClient | None = None,
    settings: Settings | None = None,
    tools: list[Tool] | None = None,
    reflect_on_tool_use: bool | None = None,
) -> AssistantAgent:
    client = model_client or create_model_client(settings or get_settings())

    extra: dict[str, Any] = {}
    if tools is not None:
        extra["tools"] = tools
    if reflect_on_tool_use is not None:
        extra["reflect_on_tool_use"] = reflect_on_tool_use

    return AssistantAgent(
        name=name,
        model_client=client,
        system_message=system_message,
        description=description or system_message,
        **extra,
    )
