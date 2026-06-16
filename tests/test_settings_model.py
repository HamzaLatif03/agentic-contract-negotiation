from loan_negotiation.config import Settings, settings_with_model


def test_settings_with_model_override():
    base = Settings(model="llama3.2:latest")
    overridden = settings_with_model("mistral:latest", base)
    assert overridden.model == "mistral:latest"
    assert base.model == "llama3.2:latest"


def test_settings_with_model_blank_keeps_base():
    base = Settings(model="llama3.2:latest")
    assert settings_with_model(None, base).model == "llama3.2:latest"
    assert settings_with_model("  ", base).model == "llama3.2:latest"
