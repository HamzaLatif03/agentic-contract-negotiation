from pydantic import BaseModel, Field


class BorrowerTermsIn(BaseModel):
    min_downpayment: float = Field(ge=0)
    max_downpayment: float = Field(ge=0)
    min_interest_rate_pct: float = Field(ge=0)
    max_interest_rate_pct: float = Field(ge=0)
    min_loan_length_years: int = Field(gt=0)
    max_loan_length_years: int = Field(gt=0)
    fixed_preference: int = Field(default=8, ge=1, le=10)
    variable_preference: int = Field(default=3, ge=1, le=10)


class LenderTermsIn(BaseModel):
    min_downpayment: float = Field(ge=0)
    max_downpayment: float = Field(ge=0)
    min_interest_rate_pct: float = Field(ge=0)
    max_interest_rate_pct: float = Field(ge=0)
    min_loan_length_years: int = Field(gt=0)
    max_loan_length_years: int = Field(gt=0)
    fixed_preference: int = Field(default=2, ge=1, le=10)
    variable_preference: int = Field(default=9, ge=1, le=10)


class DealTermsIn(BaseModel):
    downpayment: float = Field(ge=0)
    interest_rate_pct: float = Field(ge=0)
    loan_length_years: int = Field(gt=0)
    interest_structure: int = Field(ge=1, le=10)
    consensus_reached: bool = False


class NegotiateRequest(BaseModel):
    borrower: BorrowerTermsIn
    lender: LenderTermsIn
    opening_offer: DealTermsIn | None = None
    llm_model: str | None = Field(
        default=None,
        description="Comparison model id or Ollama tag (from GET /api/models). Defaults to server MODEL.",
    )
