from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms

_REQUIRED: tuple[tuple[tuple[str, ...], str], ...] = (
    (("min_downpayment", "max_downpayment"), "deposit range"),
    (("min_interest_rate_pct", "max_interest_rate_pct"), "interest rate range"),
    (("min_loan_length_years", "max_loan_length_years"), "loan term range"),
    (("min_arrangement_fee", "max_arrangement_fee"), "arrangement fee range"),
    (("min_cashback", "max_cashback"), "cashback range"),
    (
        ("min_overpayment_allowance_pct", "max_overpayment_allowance_pct"),
        "overpayment allowance range",
    ),
    (("min_erc_pct", "max_erc_pct"), "ERC range"),
    (("preferred_rate_type",), "preferred rate type"),
    (("preferred_initial_period_years",), "preferred initial deal period"),
    (("preferred_repayment_type",), "preferred repayment type"),
    (("portable_preference",), "portability preference (1-10)"),
    (("free_valuation_preference",), "free valuation preference (1-10)"),
    (("free_legal_preference",), "free legal preference (1-10)"),
)


def missing_fields(terms: BorrowerTerms | LenderTerms) -> list[str]:
    missing: list[str] = []
    for attrs, label in _REQUIRED:
        if any(getattr(terms, attr) is None for attr in attrs):
            missing.append(label)
    return missing


def borrower_missing_fields(terms: BorrowerTerms) -> list[str]:
    return missing_fields(terms)


def lender_missing_fields(terms: LenderTerms) -> list[str]:
    return missing_fields(terms)


def intake_complete(borrower: BorrowerTerms, lender: LenderTerms) -> bool:
    return not missing_fields(borrower) and not missing_fields(lender)
