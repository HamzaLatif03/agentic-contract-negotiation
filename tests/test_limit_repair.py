"""Tests for small touch-up limit repair after invalid consensus."""

from loan_negotiation.services.limit_repair import (
    repair_clears_limit_issues,
    repair_deal_to_limits,
)
from loan_negotiation.workflow.orchestrator import _neutral_validation_hints
from loan_negotiation.workflow.prompts import NEGOTIATOR_SHARED_RULES
from loan_negotiation.workflow.samples import sample_borrower, sample_lender
from deal_fixtures import sample_deal


def test_small_touchup_clamps_into_overlap():
    # £1.5k under overlap min (£60k) — within £2k touch-up cap.
    deal = sample_deal(
        downpayment=58_500,
        interest_rate_pct=5.0,
        loan_length_years=25,
        arrangement_fee=999,
        cashback=500,
        overpayment_allowance_pct=10,
        erc_pct=2,
        consensus_reached=True,
    )
    repaired, notes = repair_deal_to_limits(deal, sample_borrower(), sample_lender())
    assert repaired.downpayment == 60_000
    assert notes
    cleared, _ = repair_clears_limit_issues(deal, sample_borrower(), sample_lender())
    assert cleared is not None
    assert cleared.downpayment == 60_000


def test_large_breach_is_not_auto_repaired():
    """£100k deposit vs borrower max £80k must not be silently clamped."""
    deal = sample_deal(downpayment=100_000, consensus_reached=True)
    cleared, notes = repair_clears_limit_issues(deal, sample_borrower(), sample_lender())
    assert cleared is None
    assert any("touch-up" in n.lower() or "exceeds" in n.lower() for n in notes)


def test_project_into_overlap_clamps_large_breach():
    from loan_negotiation.services.limit_repair import project_deal_into_overlap

    deal = sample_deal(downpayment=100_000, consensus_reached=True)
    projected, notes = project_deal_into_overlap(deal, sample_borrower(), sample_lender())
    assert projected.downpayment == 80_000
    assert notes


def test_neutral_hints_omit_party_names():
    hints = _neutral_validation_hints(
        [
            "Downpayment 50000.0 is below borrower minimum 60000.0.",
            "Arrangement fee 1499.0 exceeds borrower maximum 999.0.",
        ]
    )
    joined = " ".join(hints).lower()
    assert "borrower" not in joined
    assert "lender" not in joined
    assert "deposit" in joined
    assert "arrangement fee" in joined


def test_negotiator_prompt_forbids_revealing_preference_scores():
    assert "NEVER reveal your private numbers" in NEGOTIATOR_SHARED_RULES or (
        "NEVER reveal your own private numbers" in NEGOTIATOR_SHARED_RULES
    )
    assert "preference score" in NEGOTIATOR_SHARED_RULES.lower()
    assert "non-negotiable" in NEGOTIATOR_SHARED_RULES.lower()
    assert "READ the other party's latest prose" in NEGOTIATOR_SHARED_RULES
    assert "hard limit" in NEGOTIATOR_SHARED_RULES.lower()  # forbidden phrase listed
    assert "NEVER say \"hard limit\"" in NEGOTIATOR_SHARED_RULES or (
        'NEVER say "hard limit"' in NEGOTIATOR_SHARED_RULES
    )


def test_range_summary_enforces_hard_walls():
    from loan_negotiation.workflow.orchestrator import _range_summary
    from loan_negotiation.workflow.samples import sample_borrower

    text = _range_summary(sample_borrower())
    assert "HARD PRIVATE WALLS" in text
    assert "NEVER above" in text
    assert "non-negotiable" in text.lower()
    assert "latest reasons" in text.lower() or "stated reason" in text.lower()
    assert "do NOT copy those numbers" in text
