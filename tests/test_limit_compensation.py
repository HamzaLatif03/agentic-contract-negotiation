"""Subtle soft leeway (~±2%) vs hard blocking limits."""

from loan_negotiation.services.limit_compensation import (
    breach_is_soft,
    evaluate_deal_limits,
    soft_slack,
)
from loan_negotiation.workflow.deal_parser import validate_deal_against_terms
from loan_negotiation.workflow.negotiation_tools import format_check_offer_result
from loan_negotiation.workflow.personas import get_persona
from loan_negotiation.workflow.samples import sample_borrower, sample_lender
from deal_fixtures import sample_deal


def test_in_range_deal_passes():
    deal = sample_deal(downpayment=70_000, consensus_reached=True)
    result = evaluate_deal_limits(deal, sample_borrower(), sample_lender())
    assert result.blocking_issues == []
    assert result.soft_pass_notes == []


def test_subtle_deposit_bend_is_soft_not_blocking():
    """£81k vs borrower max £80k — within ~±2% / abs floor."""
    deal = sample_deal(downpayment=81_000, consensus_reached=True)
    result = evaluate_deal_limits(deal, sample_borrower(), sample_lender())
    assert result.blocking_issues == []
    assert result.soft_pass_notes
    assert validate_deal_against_terms(deal, sample_borrower(), sample_lender()) == []


def test_large_deposit_breach_still_blocks():
    """£100k vs borrower max £80k must still block — not a subtle bend."""
    deal = sample_deal(downpayment=100_000, consensus_reached=True)
    issues = validate_deal_against_terms(deal, sample_borrower(), sample_lender())
    assert issues
    assert any("borrower" in i.lower() for i in issues)


def test_zero_fee_max_uses_absolute_soft_floor():
    """Borrower max fee £0: 2% of zero is useless; abs floor must allow tiny fee."""
    persona = get_persona("knife-edge-borrower")
    assert persona.borrower.max_arrangement_fee == 0
    slack = soft_slack("arrangement_fee", 0.0, 80.0)
    assert slack >= 100.0
    deal = sample_deal(
        downpayment=65_000,
        interest_rate_pct=4.5,
        arrangement_fee=80,
        cashback=1_500,
        overpayment_allowance_pct=10,
        erc_pct=1,
        consensus_reached=True,
    )
    result = evaluate_deal_limits(deal, persona.borrower, persona.lender)
    assert result.blocking_issues == []
    assert any("arrangement fee" in n.lower() for n in result.soft_pass_notes)


def test_large_zero_fee_breach_still_blocks():
    persona = get_persona("knife-edge-borrower")
    deal = sample_deal(arrangement_fee=800, consensus_reached=True)
    result = evaluate_deal_limits(deal, persona.borrower, persona.lender)
    assert any("arrangement fee" in i.lower() for i in result.blocking_issues)


def test_check_offer_soft_vs_problems():
    soft_msg = format_check_offer_result(
        sample_borrower(), sample_deal(downpayment=81_000)
    )
    assert soft_msg.startswith("SOFT:")
    hard_msg = format_check_offer_result(
        sample_borrower(), sample_deal(downpayment=100_000)
    )
    assert hard_msg.startswith("PROBLEMS:")


def test_breach_is_soft_helper():
    from loan_negotiation.services.limit_compensation import LimitBreach

    soft = LimitBreach("borrower", "downpayment", 81_000, 80_000, "max", "")
    hard = LimitBreach("borrower", "downpayment", 100_000, 80_000, "max", "")
    assert breach_is_soft(soft)
    assert not breach_is_soft(hard)
