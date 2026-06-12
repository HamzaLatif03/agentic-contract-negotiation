from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.services.feasibility import FeasibilityStatus, check_feasibility


def test_feasible_deal():
    borrower = BorrowerTerms(
        principal_requested=100_000,
        max_interest_rate=8.0,
        min_loan_term_months=12,
        max_loan_term_months=60,
    )
    lender = LenderTerms(
        max_principal=150_000,
        min_interest_rate=5.0,
        min_loan_term_months=12,
        max_loan_term_months=84,
    )

    result = check_feasibility(borrower, lender)

    assert result.status == FeasibilityStatus.POSSIBLE
    assert result.reasons == []


def test_impossible_interest_rate():
    borrower = BorrowerTerms(
        principal_requested=100_000,
        max_interest_rate=4.0,
        min_loan_term_months=12,
        max_loan_term_months=60,
    )
    lender = LenderTerms(
        max_principal=150_000,
        min_interest_rate=6.0,
        min_loan_term_months=12,
        max_loan_term_months=84,
    )

    result = check_feasibility(borrower, lender)

    assert result.status == FeasibilityStatus.IMPOSSIBLE
    assert len(result.reasons) == 1
