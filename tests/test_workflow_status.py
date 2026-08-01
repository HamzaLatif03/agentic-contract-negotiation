import pytest

from loan_negotiation.models.workflow import WorkflowStatus
from loan_negotiation.workflow.deal_parser import extract_final_deal
from loan_negotiation.workflow.orchestrator import _final_status
from loan_negotiation.workflow.samples import sample_borrower, sample_lender
from deal_fixtures import DEAL_JSON, sample_deal


MATCHING_TRANSCRIPT = f"""\
Lender:
```json
{DEAL_JSON}
```

Borrower:
```json
{DEAL_JSON}
```
"""


def test_matching_offers_without_accept_are_not_consensus():
    """Echo-copy of the lender package must not count as agreement."""
    deal = extract_final_deal(MATCHING_TRANSCRIPT, sample_borrower(), sample_lender())
    assert deal is None or deal.consensus_reached is False


@pytest.mark.parametrize(
    ("consensus", "issues", "fair", "expected"),
    [
        (True, [], True, WorkflowStatus.APPROVED),
        (True, [], False, WorkflowStatus.REJECTED),
        (True, ["bad"], True, WorkflowStatus.REJECTED),
        (False, [], True, WorkflowStatus.NO_DEAL),
        (None, [], True, WorkflowStatus.NO_DEAL),
    ],
)
def test_final_status(consensus, issues, fair, expected):
    deal = None
    if consensus is not None:
        deal = sample_deal(consensus_reached=consensus)
    assert (
        _final_status(final_deal=deal, validation_issues=issues, fairness_passed=fair)
        == expected
    )
