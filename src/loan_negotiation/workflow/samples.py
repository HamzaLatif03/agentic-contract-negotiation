from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.workflow.personas import demo_persona


def sample_borrower(**overrides) -> BorrowerTerms:
    base = demo_persona().borrower.model_dump()
    base.update(overrides)
    return BorrowerTerms(**base)


def sample_lender(**overrides) -> LenderTerms:
    base = demo_persona().lender.model_dump()
    base.update(overrides)
    return LenderTerms(**base)
