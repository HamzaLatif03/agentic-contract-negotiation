from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.models.workflow import LlmRunMetrics, WorkflowResult, WorkflowStatus
from loan_negotiation.services.run_metrics import RunMetricsCollector, is_model_output_agent
from deal_fixtures import sample_deal


def test_is_model_output_agent():
    assert is_model_output_agent("Borrower")
    assert is_model_output_agent("reviewer_agent")
    assert not is_model_output_agent("system")
    assert not is_model_output_agent("borrower_ranker")


def test_run_metrics_collector_ttft_and_duration():
    collector = RunMetricsCollector(model="llama3.2:latest")
    collector.mark_first_model_output()
    snap = collector.snapshot(None)
    assert snap.model == "llama3.2:latest"
    assert snap.time_to_first_token_ms is not None
    assert snap.duration_ms >= snap.time_to_first_token_ms
    assert snap.total_tokens == 0


def test_serialize_includes_llm_metrics():
    result = WorkflowResult(
        status=WorkflowStatus.NO_DEAL,
        reasons=["No structured deal could be parsed from the negotiation."],
        llm_metrics=LlmRunMetrics(
            model="mistral:latest",
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            time_to_first_token_ms=250.5,
            duration_ms=4200.0,
        ),
        deal=sample_deal(consensus_reached=True),
    )
    payload = result.to_api_dict()
    assert payload["llm_metrics"]["model"] == "mistral:latest"
    assert payload["llm_metrics"]["total_tokens"] == 140
