from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.models.workflow import WorkflowResult, WorkflowStatus
from loan_negotiation.services.feasibility import FeasibilityStatus, check_feasibility


async def run_negotiation(
    borrower_terms: BorrowerTerms,
    lender_terms: LenderTerms,
) -> WorkflowResult:
    feasibility = check_feasibility(borrower_terms, lender_terms)
    if feasibility.status == FeasibilityStatus.IMPOSSIBLE:
        return WorkflowResult(
            status=WorkflowStatus.IMPOSSIBLE,
            reasons=feasibility.reasons,
        )

    return WorkflowResult(status=WorkflowStatus.IN_PROGRESS)
