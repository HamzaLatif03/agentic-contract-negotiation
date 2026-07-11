from loan_negotiation.models.workflow import WorkflowResult
from loan_negotiation.workflow.orchestrator import WorkflowRun


def _deal_to_dict(deal) -> dict:
    return {
        "downpayment": deal.downpayment,
        "interest_rate_pct": deal.interest_rate_pct,
        "loan_length_years": deal.loan_length_years,
        "interest_structure": deal.interest_structure,
        "consensus_reached": deal.consensus_reached,
    }


def workflow_result_to_dict(result: WorkflowResult) -> dict:
    payload: dict = {
        "status": result.status.value,
        "reasons": result.reasons,
    }

    if result.deal is not None:
        payload["deal"] = _deal_to_dict(result.deal)

    if result.negotiated_deal is not None:
        payload["negotiated_deal"] = _deal_to_dict(result.negotiated_deal)
        payload["fairness_adjusted"] = (
            result.deal is not None
            and result.negotiated_deal.model_dump() != result.deal.model_dump()
        )

    if result.scores is not None:
        payload["scores"] = {
            "borrower_score": result.scores.borrower_score,
            "lender_score": result.scores.lender_score,
            "borrower_rationale": result.scores.borrower_rationale,
            "lender_rationale": result.scores.lender_rationale,
        }

    if result.review is not None:
        payload["review"] = {
            "approved": result.review.approved,
            "issues": result.review.issues,
        }

    if result.llm_metrics is not None:
        payload["llm_metrics"] = {
            "model": result.llm_metrics.model,
            "prompt_tokens": result.llm_metrics.prompt_tokens,
            "completion_tokens": result.llm_metrics.completion_tokens,
            "total_tokens": result.llm_metrics.total_tokens,
            "time_to_first_token_ms": result.llm_metrics.time_to_first_token_ms,
            "duration_ms": result.llm_metrics.duration_ms,
        }

    return payload


def workflow_run_to_dict(run: WorkflowRun) -> dict:
    return workflow_result_to_dict(run.result)
