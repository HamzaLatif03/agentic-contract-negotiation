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
    assert data["borrower"]["preferred_rate_type"] == "fixed"
    assert data["borrower"]["portable_preference"] == 8
    assert data["lender"]["preferred_rate_type"] == "tracker"
    assert data["lender"]["portable_preference"] == 3


def test_list_and_get_personas():
    listed = client.get("/api/personas")
    assert listed.status_code == 200
    personas = listed.json()["personas"]
    assert len(personas) == 10
    assert personas[0]["id"] == "demo"

    detail = client.get("/api/personas/features-duel")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == "features-duel"
    assert body["borrower"]["portable_preference"] == 10
    assert body["lender"]["portable_preference"] == 1

    missing = client.get("/api/personas/nope")
    assert missing.status_code == 404


def test_list_models(monkeypatch):
    from loan_negotiation.api import main as api_main
    from loan_negotiation.config import get_settings

    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test")
    get_settings.cache_clear()
    monkeypatch.setattr(
        api_main,
        "list_ollama_models",
        lambda _base: ["llama3.2:latest"],
    )
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert data["default"]
    assert data["api_configured"] is True
    labels = {row["label"] for row in data["catalog"]}
    assert labels == {
        "Llama 3.2",
        "Gemini 3.1 Flash Lite",
        "Mistral Small",
    }
    assert [row["id"] for row in data["catalog"]] == [
        "ollama-local",
        "gemini-3.1-flash-lite",
        "mistral-small",
    ]
    by_id = {row["id"]: row for row in data["catalog"]}
    assert by_id["gemini-3.1-flash-lite"]["runtime"] == "api"
    assert by_id["gemini-3.1-flash-lite"]["available"] is True
    assert by_id["mistral-small"]["available"] is True
    assert by_id["mistral-small"]["provider"] == "mistral"
    assert by_id["mistral-small"]["model_id"] == "mistral-small-latest"
    assert by_id["ollama-local"]["available"] is True
    assert data["keys"]["mistral"] is True
    assert "groq" not in data["keys"]
