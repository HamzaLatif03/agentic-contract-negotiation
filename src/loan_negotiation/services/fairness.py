from pydantic import BaseModel

from loan_negotiation.models.workflow import Scores


class FairnessResult(BaseModel):
    passed: bool
    fairness_gap: float
    feedback: str = ""


def fairness_gap(borrower_score: int, lender_score: int) -> float:
    """How far apart the two party scores are (0 = perfectly balanced)."""
    return float(abs(borrower_score - lender_score))


def check_fairness(
    scores: Scores,
    *,
    max_gap: float = 2.0,
) -> FairnessResult:
    gap = fairness_gap(scores.borrower_score, scores.lender_score)
    passed = gap <= max_gap

    feedback = ""
    if not passed:
        feedback = (
            f"Scores ({scores.borrower_score}, {scores.lender_score}) differ by {gap:.0f} "
            f"(max allowed gap is {max_gap:.0f})."
        )

    return FairnessResult(passed=passed, fairness_gap=gap, feedback=feedback)
