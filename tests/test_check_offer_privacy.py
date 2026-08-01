"""Tests that check_offer never leaks numeric private limits into shared chat."""

from loan_negotiation.workflow.negotiation_tools import format_check_offer_result
from loan_negotiation.workflow.samples import sample_borrower, sample_lender
from deal_fixtures import sample_deal


def test_check_offer_ok_has_no_limit_numbers():
    msg = format_check_offer_result(sample_borrower(), sample_deal(downpayment=70_000))
    assert msg.startswith("OK:")
    assert "60000" not in msg
    assert "80000" not in msg


def test_check_offer_problems_lists_fields_not_bounds():
    msg = format_check_offer_result(sample_borrower(), sample_deal(downpayment=200_000))
    assert msg.startswith("PROBLEMS:")
    assert "downpayment" in msg
    assert "minimum" not in msg.lower()
    assert "maximum" not in msg.lower()
    assert "60000" not in msg
    assert "80000" not in msg
    assert "SOFT" not in msg


def test_check_offer_soft_has_no_bound_numbers():
    msg = format_check_offer_result(sample_borrower(), sample_deal(downpayment=81_000))
    assert msg.startswith("SOFT:")
    assert "80000" not in msg
    assert "minimum" not in msg.lower()
    assert "maximum" not in msg.lower()
