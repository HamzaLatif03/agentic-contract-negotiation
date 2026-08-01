from loan_negotiation.workflow.deal_parser import (
    extract_final_deal,
    parse_labeled_offers,
    parse_offer_from_text,
    parse_offer_from_text_lenient,
)
from loan_negotiation.workflow.negotiation_state import (
    deals_match,
    resolve_consensus_deal,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender
from deal_fixtures import DEAL_JSON, sample_deal


LENDER_OPEN = f"""\
```json
{DEAL_JSON}
```
"""

BORROWER_ACCEPT = f"""\
```json
{DEAL_JSON.replace('"consensus_reached": false', '"consensus_reached": true')}
```
"""

LENDER_COUNTER_AFTER = f"""\
```json
{DEAL_JSON.replace('"downpayment": 65000', '"downpayment": 75000')}
```
"""


def test_parse_offer_ignores_tool_call_json():
    text = '{"name":"check_offer","parameters":{"downpayment":70000,"interest_rate_pct":5.0}}'
    assert parse_offer_from_text(text) is None


def test_deals_match_ignores_consensus_flag():
    left = sample_deal(consensus_reached=False)
    right = left.model_copy(update={"consensus_reached": True})
    assert deals_match(left, right)


def test_resolve_consensus_when_one_party_accepts():
    offers = parse_labeled_offers(
        f"Lender:\n{LENDER_OPEN}\n\nBorrower:\n{BORROWER_ACCEPT}"
    )
    deal = resolve_consensus_deal(offers)
    assert deal is not None
    assert deal.downpayment == 65_000
    assert deal.consensus_reached is True


def test_extract_final_deal_single_acceptance():
    transcript = f"Lender:\n{LENDER_OPEN}\n\nBorrower:\n{BORROWER_ACCEPT}"
    deal = extract_final_deal(transcript, sample_borrower(), sample_lender())
    assert deal is not None
    assert deal.consensus_reached is True
    assert deal.downpayment == 65_000


def test_extract_final_deal_prefers_first_mutual_consensus():
    transcript = (
        f"Lender:\n{LENDER_OPEN}\n\n"
        f"Borrower:\n{BORROWER_ACCEPT}\n\n"
        f"Lender:\n{BORROWER_ACCEPT}\n\n"
        f"Lender:\n{LENDER_COUNTER_AFTER}"
    )
    deal = extract_final_deal(transcript, sample_borrower(), sample_lender())
    assert deal is not None
    assert deal.downpayment == 65_000
    assert deal.consensus_reached is True


def test_lenient_parse_fills_missing_rate_type():
    prior = sample_deal(rate_type="fixed", consensus_reached=False)
    raw = (
        '{"downpayment":65000,"interest_rate_pct":4.8,'
        '"loan_length_years":25,"consensus_reached":true}'
    )
    deal = parse_offer_from_text_lenient(raw, fallback=prior)
    assert deal is not None
    assert deal.rate_type == "fixed"
    assert deal.consensus_reached is True


def test_extract_final_deal_accept_phrase_locks_to_lender_offer():
    borrower_drift = DEAL_JSON.replace("4.8", "5.0").replace("500", "2500")
    transcript = (
        f"Lender:\n```json\n{DEAL_JSON}\n```\n\n"
        f"Borrower:\nLet's accept the offer.\n```json\n{borrower_drift}\n```"
    )
    deal = extract_final_deal(transcript, sample_borrower(), sample_lender())
    assert deal is not None
    assert deal.consensus_reached is True
    assert deal.interest_rate_pct == 4.8
    assert deal.cashback == 500


def test_echo_copy_without_accept_is_not_consensus():
    transcript = (
        f"Lender:\n```json\n{DEAL_JSON}\n```\n\n"
        f"Borrower:\nWe want a lower deposit.\n```json\n{DEAL_JSON}\n```"
    )
    deal = resolve_consensus_deal(parse_labeled_offers(transcript))
    assert deal is None
    final = extract_final_deal(transcript, sample_borrower(), sample_lender())
    assert final is None or final.consensus_reached is False
