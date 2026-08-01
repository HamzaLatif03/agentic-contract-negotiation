from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.services.deal_scoring import score_deal, score_for_borrower, score_for_lender
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def _deal(**overrides) -> DealTerms:
    defaults = {
        "downpayment": 70_000,
        "interest_rate_pct": 5.0,
        "loan_length_years": 22,
        "rate_type": "fixed",
        "initial_period_years": 5,
        "arrangement_fee": 999,
        "cashback": 500,
        "overpayment_allowance_pct": 10,
        "erc_pct": 2,
        "repayment_type": "capital_repayment",
        "portable": True,
        "free_valuation": True,
        "free_legal": False,
        "consensus_reached": True,
    }
    defaults.update(overrides)
    return DealTerms(**defaults)


def test_borrower_scores_higher_on_lower_deposit():
    borrower = sample_borrower()
    low = score_for_borrower(_deal(downpayment=60_000), borrower)
    high = score_for_borrower(_deal(downpayment=80_000), borrower)
    assert low.deposit > high.deposit


def test_lender_scores_higher_on_higher_rate():
    lender = sample_lender()
    low = score_for_lender(_deal(interest_rate_pct=4.5), lender)
    high = score_for_lender(_deal(interest_rate_pct=6.0), lender)
    assert high.interest_rate > low.interest_rate


def test_rate_type_match_helps_borrower():
    borrower = sample_borrower()  # prefers fixed
    fixed = score_for_borrower(_deal(rate_type="fixed"), borrower)
    tracker = score_for_borrower(_deal(rate_type="tracker"), borrower)
    assert fixed.rate_type > tracker.rate_type
    assert fixed.total >= tracker.total


def test_rate_type_match_helps_lender():
    lender = sample_lender()  # prefers tracker
    fixed = score_for_lender(_deal(rate_type="fixed"), lender)
    tracker = score_for_lender(_deal(rate_type="tracker"), lender)
    assert tracker.rate_type > fixed.rate_type


def test_score_deal_returns_balanced_demo_midpoint():
    scores = score_deal(_deal(), sample_borrower(), sample_lender())
    assert 1 <= scores.borrower_score <= 10
    assert 1 <= scores.lender_score <= 10
    assert "Score:" in scores.borrower_rationale
    assert "UK mortgage score" in scores.lender_rationale


def test_feature_preference_strength_affects_score():
    borrower = sample_borrower(portable_preference=10)
    with_portable = score_for_borrower(_deal(portable=True), borrower)
    without = score_for_borrower(_deal(portable=False), borrower)
    assert with_portable.portable == 10.0
    assert without.portable == 1.0
    assert with_portable.portable > without.portable


def test_legacy_bool_preference_coerces():
    from loan_negotiation.models.loan_terms import BorrowerTerms

    terms = BorrowerTerms(
        min_downpayment=1,
        max_downpayment=2,
        prefer_portable=True,
        prefer_free_valuation=False,
        prefer_free_legal=True,
    )
    assert terms.portable_preference == 8
    assert terms.free_valuation_preference == 3
    assert terms.free_legal_preference == 8
