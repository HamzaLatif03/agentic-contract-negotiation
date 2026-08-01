"""Hard wall clamp so each party cannot publish offers outside their own min/max."""

from loan_negotiation.services.limit_compensation import clamp_deal_to_party_limits
from loan_negotiation.workflow.personas import get_persona
from loan_negotiation.workflow.wall_enforcement import enforce_party_walls_in_message
from deal_fixtures import sample_deal


def test_clamp_borrower_deposit_above_max():
    persona = get_persona("knife-edge-borrower")
    deal = sample_deal(downpayment=105_000, consensus_reached=False)
    clamped, notes = clamp_deal_to_party_limits(deal, persona.borrower)
    assert clamped.downpayment == persona.borrower.max_downpayment
    assert any("downpayment" in n for n in notes)


def test_clamp_clears_accept_when_out_of_walls():
    persona = get_persona("knife-edge-borrower")
    deal = sample_deal(downpayment=105_000, consensus_reached=True)
    clamped, notes = clamp_deal_to_party_limits(deal, persona.borrower)
    assert clamped.consensus_reached is False
    assert any("accept" in n.lower() for n in notes)


def test_enforce_rewrites_message_json():
    persona = get_persona("knife-edge-borrower")
    text = (
        "We will move on overpay only.\n"
        "```json\n"
        "{\n"
        '  "downpayment": 105000,\n'
        '  "interest_rate_pct": 6.5,\n'
        '  "loan_length_years": 15,\n'
        '  "rate_type": "fixed",\n'
        '  "initial_period_years": 2,\n'
        '  "arrangement_fee": 1999,\n'
        '  "cashback": 750,\n'
        '  "overpayment_allowance_pct": 12.5,\n'
        '  "erc_pct": 5,\n'
        '  "repayment_type": "capital_repayment",\n'
        '  "portable": true,\n'
        '  "free_valuation": true,\n'
        '  "free_legal": false,\n'
        '  "consensus_reached": false\n'
        "}\n"
        "```"
    )
    rewritten, notes = enforce_party_walls_in_message(text, persona.borrower)
    assert notes
    assert '"downpayment": 65000' in rewritten or '"downpayment": 65000.0' in rewritten
    assert "105000" not in rewritten


def test_in_range_offer_unchanged():
    persona = get_persona("knife-edge-borrower")
    deal = sample_deal(
        downpayment=65_000,
        interest_rate_pct=4.5,
        arrangement_fee=0,
        cashback=1_500,
        overpayment_allowance_pct=10,
        erc_pct=1,
    )
    clamped, notes = clamp_deal_to_party_limits(deal, persona.borrower)
    assert notes == []
    assert clamped.downpayment == 65_000
