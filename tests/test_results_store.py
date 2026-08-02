import json
from pathlib import Path

from loan_negotiation.models.workflow import (
    LlmRunMetrics,
    Scores,
    WorkflowResult,
    WorkflowStatus,
)
from loan_negotiation.services.results_store import (
    append_interaction,
    build_record,
    ensure_results_json,
    results_json_path,
)
from deal_fixtures import sample_deal


def test_build_record_includes_model_and_persona():
    result = WorkflowResult(
        status=WorkflowStatus.APPROVED,
        deal=sample_deal(consensus_reached=True),
        scores=Scores(borrower_score=6.7, lender_score=5.5),
        rounds=4,
        llm_metrics=LlmRunMetrics(
            model="mistral-small",
            prompt_tokens=1000,
            completion_tokens=400,
            total_tokens=1400,
            time_to_first_token_ms=1200.0,
            duration_ms=15000.0,
        ),
        reasons=[],
    )
    row = build_record(
        result,
        model_id="mistral-small",
        persona_id="demo",
        persona_name="Demo",
        attempt=2,
    )
    assert row["model_id"] == "mistral-small"
    assert row["persona_id"] == "demo"
    assert row["status"] == "approved"
    assert row["rounds"] == 4
    assert row["deal"]["downpayment"] == 65_000


def test_append_interaction_writes_json(tmp_path: Path):
    path = tmp_path / "interactions.json"
    result = WorkflowResult(
        status=WorkflowStatus.NO_DEAL,
        reasons=["No deal"],
        llm_metrics=LlmRunMetrics(model="gemini-3.1-flash-lite", duration_ms=100.0),
    )
    append_interaction(
        result,
        model_id="gemini-3.1-flash-lite",
        persona_id="features-duel",
        persona_name="Features duel",
        attempt=1,
        path=path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["interactions"]) == 1
    assert data["interactions"][0]["persona_id"] == "features-duel"


def test_append_recovers_from_empty_file(tmp_path: Path):
    path = tmp_path / "interactions.json"
    path.write_text("", encoding="utf-8")
    append_interaction(
        WorkflowResult(
            status=WorkflowStatus.APPROVED,
            deal=sample_deal(consensus_reached=True),
            reasons=[],
        ),
        model_id="mistral-small",
        path=path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["interactions"]) == 1


def test_ensure_results_json_seeds(tmp_path: Path):
    path = tmp_path / "results" / "interactions.json"
    ensure_results_json(path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"interactions": []}


def test_results_json_path_is_under_repo_results():
    path = results_json_path()
    assert path.name == "interactions.json"
    assert path.parent.name == "results"
    assert (path.parent.parent / "pyproject.toml").is_file()
