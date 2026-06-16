from loan_negotiation.workflow.negotiation_tools import (
    check_offer_against_limits,
    make_offer_checker_tool,
)
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def test_valid_offer_has_no_problems():
    problems = check_offer_against_limits(
        sample_borrower(),
        downpayment=70_000,
        interest_rate_pct=5.0,
        loan_length_years=22,
        interest_structure=1,
    )

    assert problems == []


def test_offer_above_borrower_downpayment_max_flagged():
    problems = check_offer_against_limits(
        sample_borrower(),
        downpayment=82_500,
        interest_rate_pct=5.0,
        loan_length_years=22,
        interest_structure=1,
    )

    assert any("downpayment" in problem for problem in problems)


def test_offer_with_any_structure_is_allowed():
    problems = check_offer_against_limits(
        sample_borrower(),
        downpayment=70_000,
        interest_rate_pct=5.0,
        loan_length_years=22,
        interest_structure=10,
    )

    assert problems == []


def test_lender_ranges_used_for_lender_terms():
    problems = check_offer_against_limits(
        sample_lender(),
        downpayment=120_000,
        interest_rate_pct=5.0,
        loan_length_years=22,
        interest_structure=1,
    )

    assert any("downpayment" in problem for problem in problems)


def test_tool_builds_with_expected_name():
    tool = make_offer_checker_tool(sample_borrower())

    assert tool.name == "check_offer"
