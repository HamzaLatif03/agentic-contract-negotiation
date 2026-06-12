from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Remote Ollama server base URL (no /v1 suffix)",
    )
    model: str = Field(
        default="llama3.1:8b",
        validation_alias="OLLAMA_MODEL",
        description="Model name as listed by `ollama list`",
    )

    max_rounds: int = Field(default=10, validation_alias="MAX_NEGOTIATION_ROUNDS")
    max_intake_followups: int = 5

    @property
    def ollama_tags_url(self) -> str:
        return f"{self.ollama_base_url.rstrip('/')}/api/tags"


@lru_cache
def get_settings() -> Settings:
    return Settings()
