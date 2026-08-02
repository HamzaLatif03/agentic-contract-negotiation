from typing import Literal

from pydantic import BaseModel, Field


class PartyTermsIn(BaseModel):
    min_downpayment: float = Field(ge=0)
    max_downpayment: float = Field(ge=0)
    min_interest_rate_pct: float = Field(ge=0)
    max_interest_rate_pct: float = Field(ge=0)
    min_loan_length_years: int = Field(gt=0)
    max_loan_length_years: int = Field(gt=0)
    min_arrangement_fee: float = Field(ge=0)
    max_arrangement_fee: float = Field(ge=0)
    min_cashback: float = Field(ge=0)
    max_cashback: float = Field(ge=0)
    min_overpayment_allowance_pct: float = Field(ge=0, le=100)
    max_overpayment_allowance_pct: float = Field(ge=0, le=100)
    min_erc_pct: float = Field(ge=0, le=100)
    max_erc_pct: float = Field(ge=0, le=100)
    preferred_rate_type: Literal["fixed", "tracker", "discount"]
    preferred_initial_period_years: Literal[2, 5, 10]
    preferred_repayment_type: Literal["capital_repayment", "interest_only"]
    portable_preference: int = Field(ge=1, le=10)
    free_valuation_preference: int = Field(ge=1, le=10)
    free_legal_preference: int = Field(ge=1, le=10)


class NegotiateRequest(BaseModel):
    borrower: PartyTermsIn
    lender: PartyTermsIn
    contract_text: str | None = Field(
        default=None,
        description="Optional lender contract text; local Llama 3.2 extracts the opening offer.",
    )
    llm_model: str | None = Field(
        default=None,
        description="Comparison model id or Ollama tag (from GET /api/models). Defaults to server MODEL.",
    )
    persona_id: str | None = Field(
        default=None,
        description="Optional persona id for results/interactions.json logging.",
    )
    persona_name: str | None = Field(
        default=None,
        description="Optional persona display name for interaction logs.",
    )
    attempt: int | None = Field(
        default=None,
        ge=1,
        description="Optional attempt number (e.g. 1–3) for repeated eval runs.",
    )
