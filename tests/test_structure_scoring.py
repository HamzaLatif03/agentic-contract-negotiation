from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.services.structure_scoring import structure_score_penalty
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def test_lender_penalised_for_fixed_when_wanting_variable():
    deal = DealTerms(
        downpayment=65_000,
        interest_rate_pct=4.5,
        loan_length_years=25,
        interest_structure=2,
        consensus_reached=True,
    )
    lender = sample_lender()

    assert structure_score_penalty(deal, lender) == -4


def test_borrower_not_penalised_for_fixed_when_preferring_fixed():
    deal = DealTerms(
        downpayment=65_000,
        interest_rate_pct=4.5,
        loan_length_years=25,
        interest_structure=2,
        consensus_reached=True,
    )
    borrower = sample_borrower()

    assert structure_score_penalty(deal, borrower) == 0
