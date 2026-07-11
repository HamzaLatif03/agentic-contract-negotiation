from fastapi.testclient import TestClient

from loan_negotiation.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data
    assert "ollama_num_gpu" in data
    assert "gpu_visible" in data


def test_demo_terms():
    response = client.get("/api/demo")
    assert response.status_code == 200
    data = response.json()
    assert "borrower" in data
    assert "lender" in data
    assert data["borrower"]["min_downpayment"] == 60000
    assert data["borrower"]["fixed_preference"] == 8
    assert data["lender"]["variable_preference"] == 9


def test_list_models(monkeypatch):
    from loan_negotiation.api import main as api_main
    from loan_negotiation.config import get_settings

    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    get_settings.cache_clear()
    monkeypatch.setattr(
        api_main,
        "list_ollama_models",
        lambda _base: ["loan-neg-gpu:latest"],
    )
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert data["default"]
    assert data["api_configured"] is True
    labels = {row["label"] for row in data["catalog"]}
    assert labels == {
        "Llama 3.2",
        "GPT-OSS 20B",
        "Nemotron 3 Nano 30B",
        "Gemini 3.1 Flash Lite",
        "Llama 3.3 70B",
        "Nemotron 3 Super 120B",
    }
    # Catalog is ordered by approximate size (smallest first).
    assert [row["id"] for row in data["catalog"]] == [
        "ollama-local",
        "openrouter-small",
        "gemini-3.1-flash-lite",
        "openrouter-medium",
        "groq-llama-3.3-70b",
        "openrouter-large",
    ]
    by_id = {row["id"]: row for row in data["catalog"]}
    assert by_id["gemini-3.1-flash-lite"]["runtime"] == "api"
    assert by_id["gemini-3.1-flash-lite"]["available"] is True
    assert by_id["gemini-3.1-flash-lite"]["description"] == "~Lite"
    assert by_id["openrouter-small"]["available"] is True
    assert by_id["openrouter-medium"]["model_id"].endswith(":free")
    assert by_id["openrouter-large"]["model_id"].endswith(":free")
    assert by_id["groq-llama-3.3-70b"]["available"] is True
    assert by_id["ollama-local"]["available"] is True
