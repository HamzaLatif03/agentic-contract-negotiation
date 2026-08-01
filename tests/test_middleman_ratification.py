"""Tests for middleman package accept/reject parsing (no renegotiation)."""

from loan_negotiation.workflow.orchestrator import (
    _effective_ratification,
    _parse_ratification_decision,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender
from deal_fixtures import sample_deal


def test_parse_decision_accept_line():
    assert (
        _parse_ratification_decision(
            "This package works for us commercially.\nDECISION: ACCEPT"
        )
        is True
    )


def test_parse_decision_reject_line():
    assert (
        _parse_ratification_decision(
            "Rate is still too rich for our book.\nDECISION: REJECT"
        )
        is False
    )


def test_parse_accept_without_reject_fallback():
    assert _parse_ratification_decision("We ACCEPT this middleman package.") is True


def test_parse_reject_without_accept_fallback():
    assert _parse_ratification_decision("We must REJECT these terms.") is False


def test_parse_ambiguous_returns_none():
    assert _parse_ratification_decision("Maybe ACCEPT or REJECT later.") is None


def test_preference_reject_overridden_when_inside_walls():
    """LLM 'comfort zone' / rate-type rejects must not kill an in-wall middleman package."""
    logs: list = []
    deal = sample_deal(
        downpayment=70_000,
        interest_rate_pct=5.0,
        arrangement_fee=999,
        cashback=500,
        overpayment_allowance_pct=10,
        erc_pct=2,
        rate_type="fixed",
        consensus_reached=True,
    )
    ok = _effective_ratification(
        party="lender",
        package=deal,
        terms=sample_lender(),
        llm_decision=False,
        logs=logs,
        on_message=None,
    )
    assert ok is True
    assert any("treating as ACCEPT" in e.output for e in logs)


def test_out_of_wall_package_not_forced_accept():
    logs: list = []
    deal = sample_deal(downpayment=200_000, consensus_reached=True)
    ok = _effective_ratification(
        party="borrower",
        package=deal,
        terms=sample_borrower(),
        llm_decision=True,
        logs=logs,
        on_message=None,
    )
    assert ok is False
