import httpx
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ModelInfo, UserMessage
from autogen_ext.models.ollama import OllamaChatCompletionClient

from loan_negotiation.config import Settings, get_settings


def create_model_client(settings: Settings | None = None) -> OllamaChatCompletionClient:
    """Ollama model client for agents"""
    settings = settings or get_settings()

    return OllamaChatCompletionClient(
        model=settings.model,
        host=settings.ollama_base_url,
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family="unknown",
            structured_output=True,
        ),
    )


def create_assistant_agent(
    name: str,
    system_message: str,
    *,
    description: str | None = None,
    model_client: OllamaChatCompletionClient | None = None,
    settings: Settings | None = None,
) -> AssistantAgent:
    client = model_client or create_model_client(settings or get_settings())

    return AssistantAgent(
        name=name,
        model_client=client,
        system_message=system_message,
        description=description or system_message,
    )


async def check_ollama_connection(settings: Settings | None = None) -> dict:
    """Verify the remote Ollama server is reachable and list available models."""
    settings = settings or get_settings()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.ollama_tags_url)
        response.raise_for_status()
        payload = response.json()

    models = [entry["name"] for entry in payload.get("models", [])]
    model_available = settings.model in models or any(
        name.startswith(f"{settings.model}:") for name in models
    )

    return {
        "host": settings.ollama_base_url,
        "model": settings.model,
        "models": models,
        "model_available": model_available,
    }


async def ping_model(settings: Settings | None = None) -> str:
    """Test prompt through AutoGen's Ollama client."""
    settings = settings or get_settings()
    client = create_model_client(settings)

    try:
        result = await client.create(
            [UserMessage(content="Reply with exactly: pong", source="user")]
        )
        return str(result.content)
    finally:
        await client.close()
