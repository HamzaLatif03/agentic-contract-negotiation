from pydantic import BaseModel

from loan_negotiation.models.workflow import Scores


class FairnessResult(BaseModel):
    passed: bool
    fairness_gap: float
    feedback: str = ""


def fairness_gap(borrower_score: int, lender_score: int) -> float:
    return abs(borrower_score - 5) + abs(lender_score - 5)


def check_fairness(
    scores: Scores,
    *,
    min_score: int = 3,
    max_score: int = 7,
    max_gap: float = 4.0,
) -> FairnessResult:
    gap = fairness_gap(scores.borrower_score, scores.lender_score)
    in_range = (
        min_score <= scores.borrower_score <= max_score
        and min_score <= scores.lender_score <= max_score
    )
    passed = in_range and gap <= max_gap

    feedback = ""
    if not passed:
        feedback = (
            f"Scores ({scores.borrower_score}, {scores.lender_score}) are not balanced "
            f"around 5 (gap={gap:.1f})."
        )

    return FairnessResult(passed=passed, fairness_gap=gap, feedback=feedback)
