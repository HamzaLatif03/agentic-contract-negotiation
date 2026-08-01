from loan_negotiation.workflow.negotiation_tools import (
    check_offer_against_limits,
    make_offer_checker_tool,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def _args(**overrides):
    defaults = dict(
        downpayment=70_000,
        interest_rate_pct=5.0,
        loan_length_years=22,
        rate_type="fixed",
        initial_period_years=5,
        arrangement_fee=999,
        cashback=500,
        overpayment_allowance_pct=10,
        erc_pct=2,
        repayment_type="capital_repayment",
        portable=True,
        free_valuation=True,
        free_legal=False,
    )
    defaults.update(overrides)
    return defaults


def test_valid_offer_has_no_problems():
    assert check_offer_against_limits(sample_borrower(), **_args()) == []


def test_offer_above_borrower_downpayment_max_flagged():
    problems = check_offer_against_limits(sample_borrower(), **_args(downpayment=82_500))
    assert any("downpayment" in problem for problem in problems)


def test_offer_with_tracker_rate_type_is_allowed_for_ranges():
    assert check_offer_against_limits(sample_borrower(), **_args(rate_type="tracker")) == []


def test_lender_ranges_used_for_lender_terms():
    problems = check_offer_against_limits(sample_lender(), **_args(downpayment=120_000))
    assert any("downpayment" in problem for problem in problems)


def test_tool_builds_with_expected_name():
    tool = make_offer_checker_tool(sample_borrower())
    assert tool.name == "check_offer"
