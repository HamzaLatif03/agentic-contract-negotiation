from enum import Enum

from pydantic import BaseModel, Field

from loan_negotiation.models.loan_terms import DealTerms


class WorkflowStatus(str, Enum):
    IMPOSSIBLE = "impossible"
    APPROVED = "approved"
    REJECTED = "rejected"
    NO_DEAL = "no_deal"


class Scores(BaseModel):
    borrower_score: float = Field(ge=1, le=10)
    lender_score: float = Field(ge=1, le=10)
    borrower_rationale: str = ""
    lender_rationale: str = ""


class ReviewFeedback(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list)


class LlmRunMetrics(BaseModel):
    """Per-run LLM metadata for model comparison."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Wall time until the first non-system agent message (workflow-level TTFT proxy).
    time_to_first_token_ms: float | None = None
    duration_ms: float = 0


class WorkflowResult(BaseModel):
    status: WorkflowStatus
    deal: DealTerms | None = None
    negotiated_deal: DealTerms | None = None
    scores: Scores | None = None
    review: ReviewFeedback | None = None
    reasons: list[str] = Field(default_factory=list)
    # Negotiator exchange rounds completed before consensus / termination.
    rounds: int | None = None
    llm_metrics: LlmRunMetrics | None = None

    def to_api_dict(self) -> dict:
        payload: dict = {
            "status": self.status.value,
            "deal_status": self.status.value,
            "reasons": self.reasons,
        }
        if self.rounds is not None:
            payload["rounds"] = self.rounds
        if self.deal is not None:
            payload["deal"] = self.deal.model_dump()
        if self.negotiated_deal is not None:
            payload["negotiated_deal"] = self.negotiated_deal.model_dump()
            payload["fairness_adjusted"] = (
                self.deal is not None
                and self.negotiated_deal.model_dump() != self.deal.model_dump()
            )
        if self.scores is not None:
            payload["scores"] = self.scores.model_dump()
        if self.review is not None:
            payload["review"] = self.review.model_dump()
        if self.llm_metrics is not None:
            payload["llm_metrics"] = self.llm_metrics.model_dump()
        return payload
