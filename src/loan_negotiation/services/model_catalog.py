"""Comparison models: Gemini, Groq, OpenRouter free routes + local Ollama."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Literal


RuntimeKind = Literal["api", "ollama"]
Provider = Literal["gemini", "groq", "openrouter", "ollama"]

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_OPENROUTER_KEYS = ("OPENROUTER_API_KEY", "LLAMA_API_KEY")
_OPENROUTER_BASE_ENV = ("OPENROUTER_API_BASE_URL", "LLAMA_API_BASE_URL")


@dataclass(frozen=True)
class ComparisonModel:
    id: str
    label: str
    runtime: RuntimeKind
    provider: Provider
    model_id: str
    description: str
    default_base_url: str | None = None
    key_env: tuple[str, ...] = ()
    base_url_env: tuple[str, ...] = ()


def _openrouter_free(
    *,
    id: str,
    label: str,
    model_id: str,
    description: str,
) -> ComparisonModel:
    if not model_id.endswith(":free"):
        raise ValueError(f"OpenRouter comparison models must use a :free id, got {model_id!r}")
    return ComparisonModel(
        id=id,
        label=label,
        runtime="api",
        provider="openrouter",
        model_id=model_id,
        description=description,
        default_base_url=_OPENROUTER_BASE,
        key_env=_OPENROUTER_KEYS,
        base_url_env=_OPENROUTER_BASE_ENV,
    )


COMPARISON_MODELS: tuple[ComparisonModel, ...] = (
    # Ordered smallest → largest by approximate parameter count.
    ComparisonModel(
        id="ollama-local",
        label="Llama 3.2",
        runtime="ollama",
        provider="ollama",
        model_id="llama3.2:latest",
        description="~3B",
    ),
    _openrouter_free(
        id="openrouter-small",
        label="GPT-OSS 20B",
        model_id="openai/gpt-oss-20b:free",
        description="~20B",
    ),
    ComparisonModel(
        id="gemini-3.1-flash-lite",
        label="Gemini 3.1 Flash Lite",
        runtime="api",
        provider="gemini",
        model_id="gemini-3.1-flash-lite",
        description="~Lite",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_env=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        base_url_env=("GEMINI_API_BASE_URL", "GOOGLE_API_BASE_URL"),
    ),
    _openrouter_free(
        id="openrouter-medium",
        label="Nemotron 3 Nano 30B",
        model_id="nvidia/nemotron-3-nano-30b-a3b:free",
        description="~30B",
    ),
    ComparisonModel(
        id="groq-llama-3.3-70b",
        label="Llama 3.3 70B",
        runtime="api",
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        description="~70B",
        default_base_url="https://api.groq.com/openai/v1",
        key_env=("GROQ_API_KEY",),
        base_url_env=("GROQ_API_BASE_URL",),
    ),
    _openrouter_free(
        id="openrouter-large",
        label="Nemotron 3 Super 120B",
        model_id="nvidia/nemotron-3-super-120b-a12b:free",
        description="~120B",
    ),
)


def find_comparison_model(name: str | None) -> ComparisonModel | None:
    if not name:
        return None
    key = name.strip().lower()
    for entry in COMPARISON_MODELS:
        if key in {
            entry.id.lower(),
            entry.label.lower(),
            entry.model_id.lower(),
        }:
            return entry
        if entry.runtime == "ollama" and key in {
            "ollama",
            "local",
            "loan-neg-gpu",
            "loan-neg-gpu:latest",
        }:
            return entry
        if entry.provider == "groq" and key in {"groq", "groq-llama"}:
            return entry
    return None


def _env_first(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def provider_supports_autogen_tools(entry: ComparisonModel | None) -> bool:
    """Gemini 3.x requires thought_signature round-trips that AutoGen drops."""
    if entry is None:
        return True
    return entry.provider != "gemini"


def _settings_key_for(entry: ComparisonModel) -> str | None:
    """Keys loaded from .env via Settings may not be mirrored into os.environ."""
    try:
        from loan_negotiation.config import get_settings

        settings = get_settings()
    except Exception:  # noqa: BLE001
        return None
    by_provider = {
        "gemini": settings.google_api_key,
        "groq": settings.groq_api_key,
        "openrouter": settings.openrouter_api_key,
    }
    return by_provider.get(entry.provider) or settings.llm_api_key


def _settings_base_url_for(entry: ComparisonModel) -> str | None:
    try:
        from loan_negotiation.config import get_settings

        settings = get_settings()
    except Exception:  # noqa: BLE001
        return None
    by_provider = {
        "gemini": settings.gemini_api_base_url,
        "groq": settings.groq_api_base_url,
        "openrouter": settings.openrouter_api_base_url,
    }
    return by_provider.get(entry.provider) or settings.llm_api_base_url


def provider_api_key(entry: ComparisonModel) -> str | None:
    if entry.runtime != "api":
        return None
    return _env_first(entry.key_env) or _settings_key_for(entry)


def provider_base_url(entry: ComparisonModel) -> str:
    if entry.runtime != "api":
        return ""
    return (
        _env_first(entry.base_url_env)
        or _settings_base_url_for(entry)
        or entry.default_base_url
        or ""
    ).rstrip("/")


def _name_matches(candidate: str, installed_name: str) -> bool:
    cand = candidate.strip().lower()
    have = installed_name.strip().lower()
    if cand == have:
        return True
    cand_base = cand.split(":", 1)[0]
    have_base = have.split(":", 1)[0]
    if cand_base == have_base:
        return True
    return cand_base in have or have_base in cand


def resolve_installed_name(ollama_name: str, installed: list[str]) -> str | None:
    for name in installed:
        if _name_matches(ollama_name, name):
            return name
    return None


def preferred_ollama_name(installed: list[str], fallback: str = "llama3.2:latest") -> str | None:
    """Prefer a small local tag; avoid heavy 8B+/70B models when lighter ones exist."""
    if not installed:
        return None
    preferred_order = (
        fallback,
        "llama3.2:latest",
        "llama3.2",
        "llama3.2:1b",
        "llama3.2:3b",
        "loan-neg-gpu",
        "loan-neg-gpu:latest",
    )
    for preferred in preferred_order:
        matched = resolve_installed_name(preferred, installed)
        if matched:
            return matched
    # Prefer smallest-looking tag among remaining (heuristic: avoid :70b / :8b when possible)
    light = [
        name
        for name in installed
        if not any(heavy in name.lower() for heavy in (":70b", "70b", ":8b", "8b", ":13b", "13b"))
    ]
    return (light or installed)[0]


def api_credentials_configured() -> bool:
    """True if any comparison API key is present."""
    return any(provider_api_key(entry) for entry in COMPARISON_MODELS if entry.runtime == "api")


def catalog_with_availability(installed: list[str] | None = None) -> list[dict]:
    installed = installed or []
    rows: list[dict] = []
    for entry in COMPARISON_MODELS:
        row = asdict(entry)
        row.pop("key_env", None)
        row.pop("base_url_env", None)
        row.pop("default_base_url", None)

        if entry.runtime == "api":
            ready = provider_api_key(entry) is not None
            row["available"] = ready
            row["resolved_name"] = entry.id
        else:
            matched = preferred_ollama_name(installed, entry.model_id)
            row["available"] = matched is not None
            row["resolved_name"] = matched or entry.model_id
            row["ollama_name"] = matched or entry.model_id
        rows.append(row)
    return rows


def default_comparison_model(installed: list[str] | None, fallback: str) -> str:
    installed = installed or []
    rows = catalog_with_availability(installed)
    for row in rows:
        if row["available"]:
            return row["resolved_name"]
    return fallback
