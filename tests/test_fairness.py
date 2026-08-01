from loan_negotiation.models.workflow import Scores
from loan_negotiation.services.fairness_adjustment import check_fairness, fairness_gap
import pytest


@pytest.mark.parametrize(
    ("borrower", "lender", "gap"),
    [(5, 5, 0.0), (9, 8, 1.0), (6, 4, 2.0), (6, 3, 3.0)],
)
def test_fairness_gap(borrower: int, lender: int, gap: float):
    assert fairness_gap(borrower, lender) == gap


@pytest.mark.parametrize(
    ("borrower", "lender", "passed"),
    [(5, 5, True), (9, 8, True), (6, 4, True), (9, 2, False), (6, 3, False)],
)
def test_check_fairness(borrower: int, lender: int, passed: bool):
    result = check_fairness(Scores(borrower_score=borrower, lender_score=lender))
    assert result.passed is passed
    assert result.fairness_gap == fairness_gap(borrower, lender)
