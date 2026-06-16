from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.models.workflow import WorkflowStatus
from loan_negotiation.workflow.deal_parser import extract_final_deal
from loan_negotiation.workflow.orchestrator import _final_status
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


MATCHING_TRANSCRIPT = """\
Lender:
```json
{"downpayment":65000,"interest_rate_pct":4.8,"loan_length_years":25,"interest_structure":2,"consensus_reached":false}
```

Borrower:
```json
{"downpayment":65000,"interest_rate_pct":4.8,"loan_length_years":25,"interest_structure":2,"consensus_reached":false}
```
"""


def test_matching_offers_resolve_to_consensus_deal():
    deal = extract_final_deal(MATCHING_TRANSCRIPT, sample_borrower(), sample_lender())

    assert deal is not None
    assert deal.consensus_reached is True
    assert deal.downpayment == 65_000
    assert deal.interest_rate_pct == 4.8


def test_final_status_approved_when_fair():
    deal = DealTerms(
        downpayment=65_000,
        interest_rate_pct=4.8,
        loan_length_years=25,
        interest_structure=5,
        consensus_reached=True,
    )
    assert (
        _final_status(final_deal=deal, validation_issues=[], fairness_passed=True)
        == WorkflowStatus.APPROVED
    )


def test_final_status_rejected_when_unfair():
    deal = DealTerms(
        downpayment=65_000,
        interest_rate_pct=4.8,
        loan_length_years=25,
        interest_structure=5,
        consensus_reached=True,
    )
    assert (
        _final_status(final_deal=deal, validation_issues=[], fairness_passed=False)
        == WorkflowStatus.REJECTED
    )


def test_final_status_no_deal_without_consensus():
    deal = DealTerms(
        downpayment=65_000,
        interest_rate_pct=4.8,
        loan_length_years=25,
        interest_structure=5,
        consensus_reached=False,
    )
    assert (
        _final_status(final_deal=deal, validation_issues=[], fairness_passed=True)
        == WorkflowStatus.NO_DEAL
    )


def test_final_status_no_deal_when_missing():
    assert (
        _final_status(final_deal=None, validation_issues=[], fairness_passed=True)
        == WorkflowStatus.NO_DEAL
    )
