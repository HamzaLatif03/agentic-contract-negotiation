from enum import Enum

from pydantic import BaseModel, Field

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms


class FeasibilityStatus(str, Enum):
    POSSIBLE = "possible"
    IMPOSSIBLE = "impossible"


class FeasibilityResult(BaseModel):
    status: FeasibilityStatus
    reasons: list[str] = Field(default_factory=list)


def check_feasibility(
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> FeasibilityResult:
    reasons: list[str] = []

    if borrower.max_interest_rate < lender.min_interest_rate:
        reasons.append(
            f"Borrower max rate ({borrower.max_interest_rate}%) is below "
            f"lender min rate ({lender.min_interest_rate}%)."
        )

    if borrower.principal_requested > lender.max_principal:
        reasons.append(
            f"Borrower requested principal ({borrower.principal_requested}) exceeds "
            f"lender max principal ({lender.max_principal})."
        )

    if borrower.min_loan_term_months > lender.max_loan_term_months:
        reasons.append("Borrower minimum loan term exceeds lender maximum loan term.")

    if borrower.max_loan_term_months < lender.min_loan_term_months:
        reasons.append("Borrower maximum loan term is below lender minimum loan term.")

    if reasons:
        return FeasibilityResult(status=FeasibilityStatus.IMPOSSIBLE, reasons=reasons)

    return FeasibilityResult(status=FeasibilityStatus.POSSIBLE)
