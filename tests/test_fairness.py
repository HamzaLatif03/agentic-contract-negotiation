from loan_negotiation.models.workflow import Scores
from loan_negotiation.services.fairness import check_fairness, fairness_gap


def test_fairness_gap_when_equal():
    assert fairness_gap(5, 5) == 0.0


def test_fairness_gap_when_different():
    assert fairness_gap(9, 8) == 1.0


def test_balanced_scores_pass():
    scores = Scores(borrower_score=5, lender_score=5)

    result = check_fairness(scores)

    assert result.passed is True
    assert result.fairness_gap == 0.0


def test_similar_high_scores_pass():
    scores = Scores(borrower_score=9, lender_score=8)

    result = check_fairness(scores)

    assert result.passed is True
    assert result.fairness_gap == 1.0


def test_unbalanced_scores_fail():
    scores = Scores(borrower_score=9, lender_score=2)

    result = check_fairness(scores)

    assert result.passed is False
    assert result.fairness_gap > 2.0


def test_scores_within_two_points_pass():
    scores = Scores(borrower_score=6, lender_score=4)

    result = check_fairness(scores)

    assert result.passed is True
    assert result.fairness_gap == 2.0


def test_scores_more_than_two_points_apart_fail():
    scores = Scores(borrower_score=6, lender_score=3)

    result = check_fairness(scores)

    assert result.passed is False
    assert result.fairness_gap == 3.0
