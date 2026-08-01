from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.models.workflow import Scores
from loan_negotiation.services.fairness_adjustment import (
    adjust_deal_for_fairness,
    check_fairness,
    describe_fairness_adjustment,
    disadvantaged_party,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def _demo_terms() -> tuple[BorrowerTerms, LenderTerms]:
    return sample_borrower(), sample_lender()


def _deal(**overrides) -> DealTerms:
    defaults = {
        "downpayment": 70_000,
        "interest_rate_pct": 5.0,
        "loan_length_years": 25,
        "rate_type": "fixed",
        "initial_period_years": 5,
        "arrangement_fee": 999,
        "cashback": 500,
        "overpayment_allowance_pct": 10,
        "erc_pct": 2,
        "repayment_type": "capital_repayment",
        "portable": True,
        "free_valuation": False,
        "free_legal": False,
        "consensus_reached": True,
    }
    defaults.update(overrides)
    return DealTerms(**defaults)


def test_scores_within_two_points_pass():
    scores = Scores(borrower_score=1, lender_score=3)
    assert check_fairness(scores).passed is True


def test_disadvantaged_party_when_gap_large():
    scores = Scores(borrower_score=2, lender_score=9)
    assert disadvantaged_party(scores) == "borrower"


def test_adjust_moves_toward_borrower_when_borrower_behind():
    borrower, lender = _demo_terms()
    deal = _deal(rate_type="tracker", cashback=0, overpayment_allowance_pct=5, erc_pct=5)
    scores = Scores(borrower_score=2, lender_score=9)
    adjusted = adjust_deal_for_fairness(deal, scores, borrower, lender)
    assert adjusted.rate_type == "fixed"
    assert adjusted.cashback >= deal.cashback
    assert adjusted.erc_pct <= deal.erc_pct


def test_adjust_moves_toward_lender_when_lender_behind():
    borrower, lender = _demo_terms()
    deal = _deal(rate_type="fixed", cashback=2000, arrangement_fee=0)
    scores = Scores(borrower_score=9, lender_score=2)
    adjusted = adjust_deal_for_fairness(deal, scores, borrower, lender)
    assert adjusted.rate_type == "tracker"
    assert adjusted.cashback <= deal.cashback


def test_describe_fairness_mentions_party():
    borrower, lender = _demo_terms()
    deal = _deal()
    scores = Scores(borrower_score=2, lender_score=9)
    note = describe_fairness_adjustment(scores, deal, borrower, lender)
    assert "Favour the borrower" in note


def test_propose_fair_deal_clamps_out_of_range_deposit():
    from loan_negotiation.services.fairness_adjustment import propose_fair_deal

    borrower, lender = _demo_terms()
    deal = _deal(downpayment=100_000)  # above borrower max 80k
    proposal, notes = propose_fair_deal(deal, borrower, lender)
    assert proposal.downpayment <= borrower.max_downpayment
    assert proposal.downpayment >= max(borrower.min_downpayment, lender.min_downpayment)
    assert proposal.consensus_reached is False
    assert notes


def test_close_deal_via_fairness_locks_consensus_from_stalemate():
    from loan_negotiation.services.fairness_adjustment import close_deal_via_fairness
    from loan_negotiation.services.limit_compensation import evaluate_deal_limits

    borrower, lender = _demo_terms()
    stalled = _deal(downpayment=70_000, consensus_reached=False)
    closed, notes = close_deal_via_fairness(stalled, borrower, lender)
    assert closed is not None
    assert closed.consensus_reached is True
    assert evaluate_deal_limits(closed, borrower, lender).blocking_issues == []
    assert any("exhausted" in n.lower() or "mediator" in n.lower() or "fairness" in n.lower() for n in notes)


def test_close_deal_fixes_invalid_consensus_like_rejected_run():
    """Mirrors the rejected interaction: rate 4.0 / ERC 0 vs lender mins."""
    from loan_negotiation.services.fairness_adjustment import close_deal_via_fairness
    from loan_negotiation.services.limit_compensation import evaluate_deal_limits

    borrower, lender = _demo_terms()
    bad = _deal(
        downpayment=80_000,
        interest_rate_pct=4.0,
        erc_pct=0.0,
        cashback=2_000,
        consensus_reached=True,
    )
    assert evaluate_deal_limits(bad, borrower, lender).blocking_issues
    closed, notes = close_deal_via_fairness(
        bad,
        borrower,
        lender,
        reason="Consensus package still outside hard limits — fairness agent locking.",
    )
    assert closed is not None
    assert closed.consensus_reached is True
    assert closed.interest_rate_pct >= lender.min_interest_rate_pct
    assert closed.erc_pct >= lender.min_erc_pct
    assert evaluate_deal_limits(closed, borrower, lender).blocking_issues == []
    assert any("outside hard limits" in n.lower() or "locking" in n.lower() for n in notes)


def test_silent_style_tweaks_bring_unfair_deal_into_gap():
    """After issues: middleman irons package inside ranges until score gap ≤ 2."""
    from loan_negotiation.services.deal_scoring import score_deal
    from loan_negotiation.services.fairness_adjustment import (
        balance_deal_within_ranges,
        check_fairness,
        close_deal_via_fairness,
    )
    from loan_negotiation.services.limit_compensation import evaluate_deal_limits

    borrower, lender = _demo_terms()
    deal = _deal(
        downpayment=60_000,
        interest_rate_pct=4.5,
        arrangement_fee=0,
        cashback=2_000,
        overpayment_allowance_pct=15,
        erc_pct=1,
        rate_type="fixed",
        portable=True,
        free_valuation=True,
        free_legal=True,
        consensus_reached=True,
    )
    assert not check_fairness(score_deal(deal, borrower, lender)).passed

    closed, notes = close_deal_via_fairness(
        deal, borrower, lender, scores=score_deal(deal, borrower, lender)
    )
    assert closed is not None
    assert closed.consensus_reached is True
    assert evaluate_deal_limits(closed, borrower, lender).blocking_issues == []
    scores = score_deal(closed, borrower, lender)
    assert check_fairness(scores).passed
    assert any("balanced" in n.lower() or "gap" in n.lower() for n in notes)

    balanced, balance_notes = balance_deal_within_ranges(deal, borrower, lender)
    assert evaluate_deal_limits(balanced, borrower, lender).blocking_issues == []
    assert check_fairness(score_deal(balanced, borrower, lender)).passed
    assert any("gap" in n.lower() or "balanced" in n.lower() for n in balance_notes)

def test_close_deal_via_fairness_seeds_overlap_when_no_offer():
    from loan_negotiation.services.fairness_adjustment import close_deal_via_fairness
    from loan_negotiation.services.limit_compensation import evaluate_deal_limits

    borrower, lender = _demo_terms()
    closed, notes = close_deal_via_fairness(None, borrower, lender)
    assert closed is not None
    assert closed.consensus_reached is True
    assert evaluate_deal_limits(closed, borrower, lender).blocking_issues == []
    assert any("midpoint" in n.lower() or "seeded" in n.lower() for n in notes)
