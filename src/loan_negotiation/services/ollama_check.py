import httpx

from loan_negotiation.config import Settings
from loan_negotiation.services.model_catalog import (
    find_comparison_model,
    preferred_ollama_name,
    provider_api_key,
)


class OllamaModelNotFoundError(RuntimeError):
    def __init__(self, model: str, available: list[str]) -> None:
        self.model = model
        self.available = available
        available_text = ", ".join(available) if available else "none"
        super().__init__(
            f"Ollama model '{model}' is not installed. "
            f"Run: ollama pull {model}\n"
            f"Installed models: {available_text}"
        )


def list_ollama_models(base_url: str) -> list[str]:
    response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5.0)
    response.raise_for_status()
    data = response.json()
    return [item["name"] for item in data.get("models", [])]


def ensure_model_ready(settings: Settings) -> None:
    """Fail fast if the selected catalog/API/Ollama model cannot run."""
    entry = find_comparison_model(settings.model)

    if entry is not None and entry.runtime == "api":
        by_provider = {
            "gemini": settings.google_api_key,
            "groq": settings.groq_api_key,
            "openrouter": settings.openrouter_api_key,
        }
        has_key = bool(
            provider_api_key(entry)
            or by_provider.get(entry.provider)
            or settings.llm_api_key
        )
        if not has_key:
            needed = entry.key_env[0] if entry.key_env else "API key"
            raise RuntimeError(
                f"Cannot use '{entry.label}' without {needed} "
                "(add it to your local .env and restart the API)."
            )
        return

    if entry is not None and entry.runtime == "ollama":
        installed = list_ollama_models(settings.ollama_base_url)
        matched = preferred_ollama_name(installed, entry.model_id)
        if not matched:
            raise OllamaModelNotFoundError(entry.model_id, installed)
        return

    ensure_ollama_model(settings)


def ensure_ollama_model(settings: Settings) -> None:
    """Fail fast with a clear message if the configured Ollama model is not pulled."""
    try:
        installed = list_ollama_models(settings.ollama_base_url)
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {settings.ollama_base_url}. "
            "Start Ollama and try again."
        ) from exc

    model = settings.model
    if model in installed:
        return

    if any(name.startswith(model.split(":")[0]) and model in name for name in installed):
        return
    if any(model in name for name in installed):
        return

    raise OllamaModelNotFoundError(model, installed)
