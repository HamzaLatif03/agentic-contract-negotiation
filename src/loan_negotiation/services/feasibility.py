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


_RANGE_CHECKS: tuple[tuple[str, str, str, str], ...] = (
    ("min_downpayment", "max_downpayment", "Deposit (£)", ""),
    ("min_interest_rate_pct", "max_interest_rate_pct", "Interest rate", "%"),
    ("min_loan_length_years", "max_loan_length_years", "Loan term", " years"),
    ("min_arrangement_fee", "max_arrangement_fee", "Arrangement fee (£)", ""),
    ("min_cashback", "max_cashback", "Cashback (£)", ""),
    (
        "min_overpayment_allowance_pct",
        "max_overpayment_allowance_pct",
        "Overpayment allowance",
        "%",
    ),
    ("min_erc_pct", "max_erc_pct", "ERC", "%"),
)


def check_feasibility(
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> FeasibilityResult:
    reasons: list[str] = []

    for min_attr, max_attr, label, unit in _RANGE_CHECKS:
        b_min = getattr(borrower, min_attr)
        b_max = getattr(borrower, max_attr)
        l_min = getattr(lender, min_attr)
        l_max = getattr(lender, max_attr)
        if not _ranges_overlap(b_min, b_max, l_min, l_max):
            reasons.append(
                f"{label} ranges do not overlap "
                f"(borrower {b_min}-{b_max}{unit}, lender {l_min}-{l_max}{unit})."
            )

    if reasons:
        return FeasibilityResult(status=FeasibilityStatus.IMPOSSIBLE, reasons=reasons)

    return FeasibilityResult(status=FeasibilityStatus.POSSIBLE)
