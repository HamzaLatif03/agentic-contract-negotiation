from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.workflow.fields import BORROWER_NEGOTIATION_FIELDS, LENDER_NEGOTIATION_FIELDS

BORROWER_REQUIRED_FIELDS: dict[str, str] = {
    "min_downpayment": BORROWER_NEGOTIATION_FIELDS[0],
    "max_downpayment": BORROWER_NEGOTIATION_FIELDS[0],
    "min_interest_rate_pct": BORROWER_NEGOTIATION_FIELDS[1],
    "max_interest_rate_pct": BORROWER_NEGOTIATION_FIELDS[1],
    "min_loan_length_years": BORROWER_NEGOTIATION_FIELDS[2],
    "max_loan_length_years": BORROWER_NEGOTIATION_FIELDS[2],
    "fixed_preference": BORROWER_NEGOTIATION_FIELDS[3],
    "variable_preference": BORROWER_NEGOTIATION_FIELDS[3],
}

LENDER_REQUIRED_FIELDS: dict[str, str] = {
    "min_downpayment": LENDER_NEGOTIATION_FIELDS[0],
    "max_downpayment": LENDER_NEGOTIATION_FIELDS[0],
    "min_interest_rate_pct": LENDER_NEGOTIATION_FIELDS[1],
    "max_interest_rate_pct": LENDER_NEGOTIATION_FIELDS[1],
    "min_loan_length_years": LENDER_NEGOTIATION_FIELDS[2],
    "max_loan_length_years": LENDER_NEGOTIATION_FIELDS[2],
    "fixed_preference": LENDER_NEGOTIATION_FIELDS[3],
    "variable_preference": LENDER_NEGOTIATION_FIELDS[3],
}


def _is_missing(value: object) -> bool:
    return value is None


def borrower_missing_fields(terms: BorrowerTerms) -> list[str]:
    missing: list[str] = []
    seen: set[str] = set()
    for field_name, label in BORROWER_REQUIRED_FIELDS.items():
        if _is_missing(getattr(terms, field_name)) and label not in seen:
            missing.append(label)
            seen.add(label)
    return missing


def lender_missing_fields(terms: LenderTerms) -> list[str]:
    missing: list[str] = []
    seen: set[str] = set()
    for field_name, label in LENDER_REQUIRED_FIELDS.items():
        if _is_missing(getattr(terms, field_name)) and label not in seen:
            missing.append(label)
            seen.add(label)
    return missing


def intake_complete(borrower: BorrowerTerms, lender: LenderTerms) -> bool:
    return not borrower_missing_fields(borrower) and not lender_missing_fields(lender)
