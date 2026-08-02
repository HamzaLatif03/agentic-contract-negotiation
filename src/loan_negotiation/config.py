from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from loan_negotiation.services.gpu_runtime import resolve_ollama_num_gpu


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Local Ollama server base URL (no /v1 suffix)",
    )
    model: str = Field(
        default="gemini-3.1-flash-lite",
        validation_alias=AliasChoices("OLLAMA_MODEL", "model"),
        description="Default model id/tag (catalog id or Ollama tag)",
    )
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    )
    mistral_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MISTRAL_API_KEY"),
    )
    gemini_api_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        validation_alias=AliasChoices("GEMINI_API_BASE_URL", "GOOGLE_API_BASE_URL"),
    )
    mistral_api_base_url: str = Field(
        default="https://api.mistral.ai/v1",
        validation_alias=AliasChoices("MISTRAL_API_BASE_URL"),
    )
    llm_api_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_BASE_URL"),
    )
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY"),
    )
    ollama_num_gpu: int | None = Field(
        default=None,
        validation_alias=AliasChoices("OLLAMA_NUM_GPU", "ollama_num_gpu"),
        description=(
            "Ollama options.num_gpu (layers on GPU). "
            "Unset: let Ollama decide. Set -1 for Ollama auto-estimate."
        ),
    )
    max_rounds: int = Field(
        default=10,
        validation_alias=AliasChoices("MAX_NEGOTIATION_ROUNDS", "max_rounds"),
    )
    max_fairness_adjustments: int = Field(
        default=3,
        validation_alias=AliasChoices("MAX_FAIRNESS_ADJUSTMENTS", "max_fairness_adjustments"),
        description=(
            "Silent fairness nudges when party scores differ by more than 2 "
            "(0 disables). Also used as a gate for mediator close recovery."
        ),
    )
    max_validation_recoveries: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "MAX_VALIDATION_RECOVERIES", "max_validation_recoveries"
        ),
        description=(
            "Legacy setting (kept for env compatibility). Invalid consensus is now "
            "ironed by the middleman fairness path, then ratified once by each side "
            "(no renegotiation)."
        ),
    )

    @field_validator(
        "ollama_num_gpu",
        "google_api_key",
        "mistral_api_key",
        "llm_api_key",
        "llm_api_base_url",
        mode="before",
    )
    @classmethod
    def _empty_as_none(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return value

    def resolved_ollama_num_gpu(self) -> int | None:
        """Effective GPU layer offload for the Ollama client."""
        return resolve_ollama_num_gpu(self.ollama_num_gpu)

    def resolved_api_key(self) -> str | None:
        """Any configured comparison API key."""
        return self.google_api_key or self.mistral_api_key or self.llm_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


def settings_with_model(model: str | None, base: Settings | None = None) -> Settings:
    """Return settings using an optional per-run model override."""
    settings = base or get_settings()
    chosen = (model or "").strip()
    if not chosen or chosen == settings.model:
        return settings
    return settings.model_copy(update={"model": chosen})
