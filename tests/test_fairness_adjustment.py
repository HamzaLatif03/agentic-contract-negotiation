from loan_negotiation.models.loan_terms import (
    BorrowerTerms,
    DealTerms,
    
    LenderTerms,
)
from loan_negotiation.models.workflow import Scores
from loan_negotiation.services.fairness import check_fairness
from loan_negotiation.services.fairness_adjustment import (
    adjust_deal_for_fairness,
    describe_fairness_adjustment,
    disadvantaged_party,
)


def _demo_terms() -> tuple[BorrowerTerms, LenderTerms]:
    borrower = BorrowerTerms(
        min_downpayment=60_000,
        max_downpayment=80_000,
        min_interest_rate_pct=4.0,
        max_interest_rate_pct=5.5,
        min_loan_length_years=20,
        max_loan_length_years=25,
        fixed_preference=8, variable_preference=3,
    )
    lender = LenderTerms(
        min_downpayment=50_000,
        max_downpayment=100_000,
        min_interest_rate_pct=4.5,
        max_interest_rate_pct=6.0,
        min_loan_length_years=10,
        max_loan_length_years=30,
        fixed_preference=2, variable_preference=9,
    )
    return borrower, lender


def test_scores_within_two_points_pass():
    scores = Scores(borrower_score=1, lender_score=3)

    result = check_fairness(scores)

    assert result.passed is True


def test_scores_more_than_two_points_apart_fail():
    scores = Scores(borrower_score=1, lender_score=4)

    result = check_fairness(scores)

    assert result.passed is False


def test_disadvantaged_party_when_borrower_behind():
    scores = Scores(borrower_score=1, lender_score=4)

    assert disadvantaged_party(scores) == "borrower"


def test_disadvantaged_party_when_lender_behind():
    scores = Scores(borrower_score=6, lender_score=3)

    assert disadvantaged_party(scores) == "lender"


def test_adjust_deal_moves_structure_toward_borrower_preference():
    borrower, lender = _demo_terms()
    deal = DealTerms(
        downpayment=67_500,
        interest_rate_pct=4.7,
        loan_length_years=23,
        interest_structure=10,
        consensus_reached=True,
    )
    scores = Scores(borrower_score=2, lender_score=6)

    adjusted = adjust_deal_for_fairness(deal, scores, borrower, lender)

    assert adjusted.interest_structure < deal.interest_structure
    assert adjusted.downpayment <= deal.downpayment
    assert adjusted.interest_rate_pct <= deal.interest_rate_pct


def test_describe_fairness_includes_opening_terms():
    borrower, lender = _demo_terms()
    deal = DealTerms(
        downpayment=67_500,
        interest_rate_pct=4.7,
        loan_length_years=23,
        interest_structure=10,
        consensus_reached=True,
    )
    scores = Scores(borrower_score=2, lender_score=6)

    note = describe_fairness_adjustment(scores, deal, borrower, lender)

    assert "Borrower opening" in note
    assert "Lender opening" in note
    assert "Favour the borrower" in note
    assert "structure penalty" in note


def test_adjust_deal_favours_borrower_when_behind():
    borrower, lender = _demo_terms()
    deal = DealTerms(
        downpayment=78_000,
        interest_rate_pct=5.4,
        loan_length_years=24,
        interest_structure=1,
        consensus_reached=True,
    )
    scores = Scores(borrower_score=1, lender_score=4)

    adjusted = adjust_deal_for_fairness(deal, scores, borrower, lender)

    assert adjusted.downpayment < deal.downpayment
    assert adjusted.interest_rate_pct < deal.interest_rate_pct
    assert adjusted.loan_length_years <= deal.loan_length_years


def test_adjust_deal_favours_lender_when_behind():
    borrower, lender = _demo_terms()
    deal = DealTerms(
        downpayment=62_000,
        interest_rate_pct=4.6,
        loan_length_years=25,
        interest_structure=1,
        consensus_reached=True,
    )
    scores = Scores(borrower_score=6, lender_score=3)

    adjusted = adjust_deal_for_fairness(deal, scores, borrower, lender)

    assert adjusted.downpayment > deal.downpayment
    assert adjusted.interest_rate_pct > deal.interest_rate_pct
