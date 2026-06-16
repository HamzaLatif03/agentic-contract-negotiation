from enum import Enum

from pydantic import BaseModel, Field

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms


class FeasibilityStatus(str, Enum):
    POSSIBLE = "possible"
    IMPOSSIBLE = "impossible"


class FeasibilityResult(BaseModel):
    status: FeasibilityStatus
    reasons: list[str] = Field(default_factory=list)


def _ranges_overlap(
    min_a: float | int | None,
    max_a: float | int | None,
    min_b: float | int | None,
    max_b: float | int | None,
) -> bool:
    if min_a is not None and max_b is not None and min_a > max_b:
        return False
    if max_a is not None and min_b is not None and max_a < min_b:
        return False
    return True


def check_feasibility(
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> FeasibilityResult:
    reasons: list[str] = []

    if not _ranges_overlap(
        borrower.min_downpayment,
        borrower.max_downpayment,
        lender.min_downpayment,
        lender.max_downpayment,
    ):
        reasons.append(
            f"Downpayment ranges do not overlap "
            f"(borrower {borrower.min_downpayment}-{borrower.max_downpayment}, "
            f"lender {lender.min_downpayment}-{lender.max_downpayment})."
        )

    if not _ranges_overlap(
        borrower.min_interest_rate_pct,
        borrower.max_interest_rate_pct,
        lender.min_interest_rate_pct,
        lender.max_interest_rate_pct,
    ):
        reasons.append(
            f"Interest rate ranges do not overlap "
            f"(borrower {borrower.min_interest_rate_pct}-{borrower.max_interest_rate_pct}%, "
            f"lender {lender.min_interest_rate_pct}-{lender.max_interest_rate_pct}%)."
        )

    if not _ranges_overlap(
        borrower.min_loan_length_years,
        borrower.max_loan_length_years,
        lender.min_loan_length_years,
        lender.max_loan_length_years,
    ):
        reasons.append(
            f"Loan length ranges do not overlap "
            f"(borrower {borrower.min_loan_length_years}-{borrower.max_loan_length_years} years, "
            f"lender {lender.min_loan_length_years}-{lender.max_loan_length_years} years)."
        )

    if reasons:
        return FeasibilityResult(status=FeasibilityStatus.IMPOSSIBLE, reasons=reasons)

    return FeasibilityResult(status=FeasibilityStatus.POSSIBLE)
