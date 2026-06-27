from loan_negotiation.agents.factory import create_model_client
from loan_negotiation.config import Settings


def test_create_model_client_passes_num_gpu():
    settings = Settings(ollama_num_gpu=999, model="llama3.2:latest")
    client = create_model_client(settings)
    assert client._raw_config["options"]["num_gpu"] == 999
    assert client._create_args["options"]["num_gpu"] == 999


def test_settings_reads_ollama_num_gpu_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_GPU", "77")
    settings = Settings(_env_file=None)
    assert settings.ollama_num_gpu == 77
