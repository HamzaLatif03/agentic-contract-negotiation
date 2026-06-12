from pydantic import BaseModel, Field


class BorrowerTerms(BaseModel):
    principal_requested: float = Field(gt=0)
    max_interest_rate: float = Field(ge=0)
    min_loan_term_months: int = Field(gt=0)
    max_loan_term_months: int = Field(gt=0)
    collateral_offered: str = ""
    repayment_frequency: str = "monthly"
    prepayment_allowed: bool = True


class LenderTerms(BaseModel):
    max_principal: float = Field(gt=0)
    min_interest_rate: float = Field(ge=0)
    min_loan_term_months: int = Field(gt=0)
    max_loan_term_months: int = Field(gt=0)
    required_collateral: str = ""
    prepayment_penalty_pct: float = Field(ge=0, default=0)
    late_fee_pct: float = Field(ge=0, default=0)


class DealTerms(BaseModel):
    principal: float = Field(gt=0)
    interest_rate: float = Field(ge=0)
    loan_term_months: int = Field(gt=0)
    collateral: str = ""
    repayment_frequency: str = "monthly"
    prepayment_penalty_pct: float = Field(ge=0, default=0)
    late_fee_pct: float = Field(ge=0, default=0)
    consensus_reached: bool = False
