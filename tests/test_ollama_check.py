from unittest.mock import patch

import httpx
import pytest

from loan_negotiation.config import Settings
from loan_negotiation.services.ollama_check import (
    OllamaModelNotFoundError,
    ensure_ollama_model,
)


def test_ensure_ollama_model_passes_when_installed():
    settings = Settings(model="llama3.1:8b")
    with patch(
        "loan_negotiation.services.ollama_check.list_ollama_models",
        return_value=["llama3.1:8b", "llama3.2:latest"],
    ):
        ensure_ollama_model(settings)


def test_ensure_ollama_model_raises_when_missing():
    settings = Settings(model="llama3.1:8b")
    with patch(
        "loan_negotiation.services.ollama_check.list_ollama_models",
        return_value=["llama3.2:latest"],
    ):
        with pytest.raises(OllamaModelNotFoundError) as exc:
            ensure_ollama_model(settings)
        assert "ollama pull llama3.1:8b" in str(exc.value)


def test_ensure_ollama_model_raises_when_server_down():
    settings = Settings()
    with patch(
        "loan_negotiation.services.ollama_check.list_ollama_models",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        with pytest.raises(RuntimeError, match="Cannot reach Ollama"):
            ensure_ollama_model(settings)
