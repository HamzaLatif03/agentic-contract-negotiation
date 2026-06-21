from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.services.deal_scoring import score_deal, score_for_borrower, score_for_lender
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def _deal(**overrides) -> DealTerms:
    defaults = {
        "downpayment": 70_000,
        "interest_rate_pct": 5.0,
        "loan_length_years": 22,
        "interest_structure": 5,
        "consensus_reached": True,
    }
    defaults.update(overrides)
    return DealTerms(**defaults)


def test_borrower_scores_higher_on_lower_downpayment():
    borrower = sample_borrower()
    low = score_for_borrower(_deal(downpayment=60_000), borrower)
    high = score_for_borrower(_deal(downpayment=80_000), borrower)

    assert low.downpayment > high.downpayment


def test_lender_scores_higher_on_higher_rate():
    lender = sample_lender()
    low = score_for_lender(_deal(interest_rate_pct=4.5), lender)
    high = score_for_lender(_deal(interest_rate_pct=6.0), lender)

    assert high.interest_rate > low.interest_rate


def test_structure_mismatch_hurts_borrower_on_variable_deal():
    borrower = sample_borrower()  # fixed 8, variable 3
    fixed = score_for_borrower(_deal(interest_structure=2), borrower)
    variable = score_for_borrower(_deal(interest_structure=10), borrower)

    assert fixed.interest_structure > variable.interest_structure
    assert fixed.total >= variable.total


def test_structure_mismatch_hurts_lender_on_fixed_deal():
    lender = sample_lender()  # fixed 2, variable 9
    fixed = score_for_lender(_deal(interest_structure=1), lender)
    variable = score_for_lender(_deal(interest_structure=10), lender)

    assert variable.interest_structure > fixed.interest_structure


def test_score_deal_returns_balanced_demo_midpoint():
    scores = score_deal(
        _deal(downpayment=70_000, interest_rate_pct=5.0, loan_length_years=22, interest_structure=5),
        sample_borrower(),
        sample_lender(),
    )

    assert 1 <= scores.borrower_score <= 10
    assert 1 <= scores.lender_score <= 10
    assert "Score:" in scores.borrower_rationale
    assert "Deterministic score" in scores.lender_rationale
