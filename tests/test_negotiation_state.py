from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.workflow.deal_parser import (
    extract_final_deal,
    parse_labeled_offers,
    parse_offer_from_text,
)
from loan_negotiation.workflow.negotiation_state import (
    deals_match,
    resolve_consensus_deal,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender

LENDER_OPEN = """\
```json
{
  "downpayment": 70000,
  "interest_rate_pct": 5.0,
  "loan_length_years": 25,
  "interest_structure": 1,
  "consensus_reached": false
}
```
"""

BORROWER_ACCEPT = """\
```json
{
  "downpayment": 70000,
  "interest_rate_pct": 5.0,
  "loan_length_years": 25,
  "interest_structure": 1,
  "consensus_reached": true
}
```
"""

LENDER_COUNTER_AFTER = """\
```json
{
  "downpayment": 75000,
  "interest_rate_pct": 5.0,
  "loan_length_years": 25,
  "interest_structure": 1,
  "consensus_reached": false
}
```
"""


def test_parse_offer_ignores_tool_call_json():
    text = '{"name":"check_offer","parameters":{"downpayment":70000,"interest_rate_pct":5.0}}'

    assert parse_offer_from_text(text) is None


def test_deals_match_ignores_consensus_flag():
    left = DealTerms(
        downpayment=70_000,
        interest_rate_pct=5.0,
        loan_length_years=25,
        interest_structure=1,
        consensus_reached=False,
    )
    right = left.model_copy(update={"consensus_reached": True})

    assert deals_match(left, right)


def test_resolve_consensus_when_one_party_accepts():
    offers = parse_labeled_offers(
        f"Lender:\n{LENDER_OPEN}\n\nBorrower:\n{BORROWER_ACCEPT}"
    )
    deal = resolve_consensus_deal(offers)

    assert deal is not None
    assert deal.downpayment == 70_000
    assert deal.consensus_reached is True


def test_extract_final_deal_single_acceptance():
    transcript = f"Lender:\n{LENDER_OPEN}\n\nBorrower:\n{BORROWER_ACCEPT}"
    deal = extract_final_deal(transcript, sample_borrower(), sample_lender())

    assert deal is not None
    assert deal.consensus_reached is True
    assert deal.downpayment == 70_000


def test_extract_final_deal_prefers_first_mutual_consensus():
    transcript = (
        f"Lender:\n{LENDER_OPEN}\n\n"
        f"Borrower:\n{BORROWER_ACCEPT}\n\n"
        f"Lender:\n{BORROWER_ACCEPT}\n\n"
        f"Lender:\n{LENDER_COUNTER_AFTER}"
    )

    deal = extract_final_deal(transcript, sample_borrower(), sample_lender())

    assert deal is not None
    assert deal.downpayment == 70_000
    assert deal.consensus_reached is True


def test_lenient_parse_fills_missing_interest_type():
    from loan_negotiation.workflow.deal_parser import parse_offer_from_text_lenient

    prior = DealTerms(
        downpayment=60_000,
        interest_rate_pct=4.5,
        loan_length_years=20,
        interest_structure=1,
        consensus_reached=False,
    )
    raw = (
        '{"downpayment":60000,"interest_rate_pct":4.5,'
        '"loan_length_years":20,"consensus_reached":true}'
    )

    deal = parse_offer_from_text_lenient(raw, fallback=prior)

    assert deal is not None
    assert deal.interest_structure == 1
    assert deal.consensus_reached is True
