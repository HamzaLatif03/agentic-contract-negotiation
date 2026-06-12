from enum import Enum

from pydantic import BaseModel, Field

from loan_negotiation.models.loan_terms import DealTerms


class WorkflowStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    IMPOSSIBLE = "impossible"
    APPROVED = "approved"


class Scores(BaseModel):
    borrower_score: int = Field(ge=1, le=10)
    lender_score: int = Field(ge=1, le=10)
    borrower_rationale: str = ""
    lender_rationale: str = ""


class ReviewFeedback(BaseModel):
    approved: bool
    missing_fields: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class WorkflowResult(BaseModel):
    status: WorkflowStatus
    deal: DealTerms | None = None
    scores: Scores | None = None
    review: ReviewFeedback | None = None
    reasons: list[str] = Field(default_factory=list)
