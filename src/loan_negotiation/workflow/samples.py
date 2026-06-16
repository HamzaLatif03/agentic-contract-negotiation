from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms


def sample_borrower(**overrides) -> BorrowerTerms:
    defaults = {
        "min_downpayment": 60_000,
        "max_downpayment": 80_000,
        "min_interest_rate_pct": 4.0,
        "max_interest_rate_pct": 5.5,
        "min_loan_length_years": 20,
        "max_loan_length_years": 25,
        "fixed_preference": 8,
        "variable_preference": 3,
    }
    defaults.update(overrides)
    return BorrowerTerms(**defaults)


def sample_lender(**overrides) -> LenderTerms:
    defaults = {
        "min_downpayment": 50_000,
        "max_downpayment": 100_000,
        "min_interest_rate_pct": 4.5,
        "max_interest_rate_pct": 6.0,
        "min_loan_length_years": 10,
        "max_loan_length_years": 30,
        "fixed_preference": 2,
        "variable_preference": 9,
    }
    defaults.update(overrides)
    return LenderTerms(**defaults)
