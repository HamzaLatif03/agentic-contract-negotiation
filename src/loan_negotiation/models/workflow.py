from enum import Enum

from pydantic import BaseModel, Field

from loan_negotiation.models.loan_terms import DealTerms


class WorkflowStatus(str, Enum):
    IMPOSSIBLE = "impossible"
    APPROVED = "approved"
    REJECTED = "rejected"
    NO_DEAL = "no_deal"


class Scores(BaseModel):
    borrower_score: int = Field(ge=1, le=10)
    lender_score: int = Field(ge=1, le=10)
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
    llm_metrics: LlmRunMetrics | None = None
