from loan_negotiation.config import get_settings
from loan_negotiation.services.model_catalog import (
    api_credentials_configured,
    catalog_with_availability,
    default_comparison_model,
    find_comparison_model,
    provider_api_key,
    resolve_installed_name,
)


def test_find_api_and_ollama_entries():
    gemini = find_comparison_model("gemini-3.1-flash-lite")
    assert gemini is not None and gemini.runtime == "api" and gemini.provider == "gemini"
    assert find_comparison_model("kimi-k2.6") is None
    assert find_comparison_model("qwen-3.6-27b") is None
    assert find_comparison_model("groq") is None
    assert find_comparison_model("groq-llama-3.3-70b") is None
    mistral = find_comparison_model("mistral-small")
    assert mistral is not None and mistral.provider == "mistral"
    assert mistral.model_id == "mistral-small-latest"
    assert find_comparison_model("mistral") is mistral
    assert find_comparison_model("openrouter-large") is None
    assert find_comparison_model("ollama-local") is not None


def test_resolve_installed_name_fuzzy():
    assert resolve_installed_name("llama3.2:latest", ["llama3.2:latest"]) == "llama3.2:latest"


def test_catalog_per_provider_keys(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr(
        "loan_negotiation.services.model_catalog._settings_key_for",
        lambda _entry: None,
    )
    for name in (
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
        "LLM_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    rows = catalog_with_availability([])
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {
        "gemini-3.1-flash-lite",
        "mistral-small",
        "ollama-local",
    }
    assert by_id["gemini-3.1-flash-lite"]["available"] is False
    assert by_id["mistral-small"]["available"] is False

    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test")
    assert provider_api_key(find_comparison_model("mistral-small")) == "mistral-test"
    rows_mistral = catalog_with_availability(["llama3.2:latest"])
    by_id = {row["id"]: row for row in rows_mistral}
    assert by_id["mistral-small"]["available"] is True
    assert by_id["gemini-3.1-flash-lite"]["available"] is False
    assert by_id["ollama-local"]["available"] is True
    assert by_id["ollama-local"]["resolved_name"] == "llama3.2:latest"
    assert api_credentials_configured() is True


def test_default_prefers_first_available(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr(
        "loan_negotiation.services.model_catalog._settings_key_for",
        lambda _entry: None,
    )
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY", "LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert default_comparison_model(["llama3.2:latest"], "x") == "llama3.2:latest"
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    assert default_comparison_model(["llama3.2:latest"], "x") == "llama3.2:latest"
    assert default_comparison_model([], "x") == "gemini-3.1-flash-lite"


def test_gemini_disables_autogen_tools():
    from loan_negotiation.services.model_catalog import provider_supports_autogen_tools

    assert provider_supports_autogen_tools(find_comparison_model("gemini-3.1-flash-lite")) is False
    assert provider_supports_autogen_tools(find_comparison_model("mistral-small")) is False
    assert provider_supports_autogen_tools(find_comparison_model("ollama-local")) is True
