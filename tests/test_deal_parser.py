from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.workflow.deal_parser import (
    extract_final_deal,
    parse_offer_from_text,
    validate_deal_against_terms,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender

LENDER_MESSAGE = """\
Here is my opening offer.

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

BORROWER_COUNTER = """\
Counteroffer:

```json
{
  "downpayment": 65000,
  "interest_rate_pct": 4.75,
  "loan_length_years": 22,
  "interest_structure": 1,
  "consensus_reached": false
}
```
"""

LENDER_ACCEPT = """\
CONSENSUS_REACHED

```json
{
  "downpayment": 65000,
  "interest_rate_pct": 4.75,
  "loan_length_years": 22,
  "interest_structure": 1,
  "consensus_reached": true
}
```
"""


def test_parse_legacy_interest_type_string():
    deal = parse_offer_from_text(
        '{"downpayment":70000,"interest_rate_pct":5.0,"loan_length_years":25,'
        '"interest_type":"fixed","consensus_reached":false}'
    )

    assert deal is not None
    assert deal.interest_structure == 1


def test_parse_offer_from_json_block():
    deal = parse_offer_from_text(LENDER_MESSAGE)

    assert deal is not None
    assert deal.downpayment == 70000
    assert deal.interest_rate_pct == 5.0
    assert deal.loan_length_years == 25
    assert deal.interest_structure == 1
    assert deal.consensus_reached is False


def test_extract_final_deal_prefers_consensus():
    transcript = f"Lender:\n{LENDER_MESSAGE}\n\nBorrower:\n{BORROWER_COUNTER}\n\nLender:\n{LENDER_ACCEPT}"
    deal = extract_final_deal(transcript)

    assert deal is not None
    assert deal.consensus_reached is True
    assert deal.downpayment == 65000
    assert deal.interest_rate_pct == 4.75


def test_extract_final_deal_falls_back_to_last_offer():
    transcript = f"Lender:\n{LENDER_MESSAGE}\n\nBorrower:\n{BORROWER_COUNTER}"
    deal = extract_final_deal(transcript)

    assert deal is not None
    assert deal.downpayment == 65000
    assert deal.consensus_reached is False


def test_validate_deal_within_ranges():
    deal = DealTerms(
        downpayment=70_000,
        interest_rate_pct=5.0,
        loan_length_years=25,
        interest_structure=1,
    )

    issues = validate_deal_against_terms(deal, sample_borrower(), sample_lender())

    assert issues == []


def test_extract_final_deal_skips_invalid_consensus():
    invalid_consensus = """\
```json
{
  "downpayment": 82500,
  "interest_rate_pct": 4.9,
  "loan_length_years": 20,
  "interest_structure": 1,
  "consensus_reached": true
}
```
"""
    valid_counter = """\
```json
{
  "downpayment": 75000,
  "interest_rate_pct": 5.0,
  "loan_length_years": 20,
  "interest_structure": 1,
  "consensus_reached": false
}
```
"""
    transcript = (
        f"Lender:\n{LENDER_MESSAGE}\n\n"
        f"Borrower:\n{valid_counter}\n\n"
        f"Lender:\n{invalid_consensus}"
    )
    deal = extract_final_deal(transcript, sample_borrower(), sample_lender())

    assert deal is not None
    assert deal.downpayment == 75000
    assert deal.consensus_reached is False


def test_validate_deal_flags_out_of_range_downpayment():
    deal = DealTerms(
        downpayment=40_000,
        interest_rate_pct=5.0,
        loan_length_years=25,
        interest_structure=1,
    )

    issues = validate_deal_against_terms(deal, sample_borrower(), sample_lender())

    assert any("downpayment" in issue.lower() for issue in issues)
