from loan_negotiation.workflow.deal_parser import (
    extract_final_deal,
    parse_offer_from_text,
    validate_deal_against_terms,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender
from deal_fixtures import sample_deal

LENDER_MESSAGE = """\
Here is my opening offer.

```json
{
  "downpayment": 70000,
  "interest_rate_pct": 5.0,
  "loan_length_years": 25,
  "rate_type": "fixed",
  "initial_period_years": 5,
  "arrangement_fee": 999,
  "cashback": 500,
  "overpayment_allowance_pct": 10,
  "erc_pct": 2,
  "repayment_type": "capital_repayment",
  "portable": true,
  "free_valuation": true,
  "free_legal": false,
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
  "rate_type": "fixed",
  "initial_period_years": 5,
  "arrangement_fee": 0,
  "cashback": 1500,
  "overpayment_allowance_pct": 15,
  "erc_pct": 1,
  "repayment_type": "capital_repayment",
  "portable": true,
  "free_valuation": true,
  "free_legal": true,
  "consensus_reached": false
}
```
"""

LENDER_ACCEPT = """\
Accepted.

```json
{
  "downpayment": 65000,
  "interest_rate_pct": 4.75,
  "loan_length_years": 22,
  "rate_type": "fixed",
  "initial_period_years": 5,
  "arrangement_fee": 0,
  "cashback": 1500,
  "overpayment_allowance_pct": 15,
  "erc_pct": 1,
  "repayment_type": "capital_repayment",
  "portable": true,
  "free_valuation": true,
  "free_legal": true,
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
    assert deal.rate_type == "fixed"


def test_parse_offer_from_json_block():
    deal = parse_offer_from_text(LENDER_MESSAGE)
    assert deal is not None
    assert deal.downpayment == 70000
    assert deal.rate_type == "fixed"
    assert deal.initial_period_years == 5
    assert deal.arrangement_fee == 999
    assert deal.consensus_reached is False


def test_extract_final_deal_prefers_consensus():
    transcript = f"Lender:\n{LENDER_MESSAGE}\n\nBorrower:\n{BORROWER_COUNTER}\n\nLender:\n{LENDER_ACCEPT}"
    deal = extract_final_deal(transcript)
    assert deal is not None
    assert deal.consensus_reached is True
    assert deal.downpayment == 65000
    assert deal.free_legal is True


def test_extract_final_deal_falls_back_to_last_offer():
    transcript = f"Lender:\n{LENDER_MESSAGE}\n\nBorrower:\n{BORROWER_COUNTER}"
    deal = extract_final_deal(transcript)
    assert deal is not None
    assert deal.downpayment == 65000
    assert deal.consensus_reached is False


def test_validate_deal_within_ranges():
    issues = validate_deal_against_terms(sample_deal(downpayment=70_000), sample_borrower(), sample_lender())
    assert issues == []


def test_extract_final_deal_locks_acceptance_to_counterparty_package():
    invalid_consensus = """\
```json
{
  "downpayment": 82500,
  "interest_rate_pct": 4.9,
  "loan_length_years": 20,
  "rate_type": "fixed",
  "initial_period_years": 5,
  "arrangement_fee": 0,
  "cashback": 500,
  "overpayment_allowance_pct": 10,
  "erc_pct": 2,
  "repayment_type": "capital_repayment",
  "portable": true,
  "free_valuation": true,
  "free_legal": false,
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
  "rate_type": "fixed",
  "initial_period_years": 5,
  "arrangement_fee": 999,
  "cashback": 500,
  "overpayment_allowance_pct": 10,
  "erc_pct": 2,
  "repayment_type": "capital_repayment",
  "portable": true,
  "free_valuation": true,
  "free_legal": false,
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
    # Acceptance with drifted numbers locks to the borrower's latest package.
    assert deal.downpayment == 75000
    assert deal.consensus_reached is True


def test_extract_final_deal_keeps_consensus_even_if_slightly_out_of_limits():
    """Do not replace an agreed package with an earlier counter — repair handles limits."""
    transcript = """\
Lender:
```json
{
  "downpayment": 60000,
  "interest_rate_pct": 5.25,
  "loan_length_years": 20,
  "rate_type": "tracker",
  "initial_period_years": 10,
  "arrangement_fee": 1000,
  "cashback": 0,
  "overpayment_allowance_pct": 7,
  "erc_pct": 2,
  "repayment_type": "capital_repayment",
  "portable": false,
  "free_valuation": true,
  "free_legal": false,
  "consensus_reached": false
}
```

Borrower:
```json
{
  "downpayment": 60000,
  "interest_rate_pct": 5.25,
  "loan_length_years": 20,
  "rate_type": "tracker",
  "initial_period_years": 10,
  "arrangement_fee": 900,
  "cashback": 2000,
  "overpayment_allowance_pct": 10,
  "erc_pct": 2,
  "repayment_type": "capital_repayment",
  "portable": false,
  "free_valuation": true,
  "free_legal": false,
  "consensus_reached": false
}
```

Lender:
```json
{
  "downpayment": 65000,
  "interest_rate_pct": 5.25,
  "loan_length_years": 20,
  "rate_type": "tracker",
  "initial_period_years": 10,
  "arrangement_fee": 900,
  "cashback": 1500,
  "overpayment_allowance_pct": 11,
  "erc_pct": 3,
  "repayment_type": "capital_repayment",
  "portable": false,
  "free_valuation": true,
  "free_legal": false,
  "consensus_reached": false
}
```

Borrower:
I accept.
```json
{
  "downpayment": 65000,
  "interest_rate_pct": 5.25,
  "loan_length_years": 20,
  "rate_type": "tracker",
  "initial_period_years": 10,
  "arrangement_fee": 900,
  "cashback": 1500,
  "overpayment_allowance_pct": 11,
  "erc_pct": 3,
  "repayment_type": "capital_repayment",
  "portable": false,
  "free_valuation": true,
  "free_legal": false,
  "consensus_reached": true
}
```
"""
    deal = extract_final_deal(transcript, sample_borrower(), sample_lender())
    assert deal is not None
    assert deal.consensus_reached is True
    assert deal.downpayment == 65_000
    assert deal.overpayment_allowance_pct == 11
    # Consensus package is kept even when a field sits past a hard max; repair/middleman
    # may clear validation afterward (large breaches are not soft-accepted).
    assert deal.overpayment_allowance_pct > sample_lender().max_overpayment_allowance_pct

    issues = validate_deal_against_terms(
        sample_deal(downpayment=40_000), sample_borrower(), sample_lender()
    )
    assert any("downpayment" in issue.lower() or "deposit" in issue.lower() for issue in issues)


def test_parse_offer_from_nemotron_xml_tool_call():
    raw = """
<tool_call>
<function=check_offer>
<parameter=downpayment>90000</parameter>
<parameter=interest_rate_pct>5.0</parameter>
<parameter=loan_length_years>15</parameter>
<parameter=rate_type>fixed</parameter>
</function>
</tool_call>
"""
    deal = parse_offer_from_text(raw)
    assert deal is not None
    assert deal.downpayment == 90000
    assert deal.rate_type == "fixed"
