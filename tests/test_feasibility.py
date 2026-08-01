from loan_negotiation.services.feasibility import FeasibilityStatus, check_feasibility
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def test_feasible_deal():
    result = check_feasibility(sample_borrower(), sample_lender())

    assert result.status == FeasibilityStatus.POSSIBLE
    assert result.reasons == []


def test_impossible_interest_rate():
    borrower = sample_borrower(min_interest_rate_pct=3.0, max_interest_rate_pct=4.0)
    lender = sample_lender(min_interest_rate_pct=6.0, max_interest_rate_pct=7.0)

    result = check_feasibility(borrower, lender)

    assert result.status == FeasibilityStatus.IMPOSSIBLE
    assert any("rate" in reason.lower() for reason in result.reasons)


def test_impossible_downpayment():
    borrower = sample_borrower(min_downpayment=20_000, max_downpayment=30_000)
    lender = sample_lender(min_downpayment=50_000, max_downpayment=60_000)

    result = check_feasibility(borrower, lender)

    assert result.status == FeasibilityStatus.IMPOSSIBLE
    assert any("deposit" in reason.lower() for reason in result.reasons)
