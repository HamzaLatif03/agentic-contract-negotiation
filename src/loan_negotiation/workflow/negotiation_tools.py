from autogen_core.tools import FunctionTool

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms, clamp_interest_structure


def check_offer_against_limits(
    terms: BorrowerTerms | LenderTerms,
    downpayment: float,
    interest_rate_pct: float,
    loan_length_years: int,
    interest_structure: int,
) -> list[str]:
    """Return a list of ways a proposed offer violates a party's own limits (empty = OK)."""
    problems: list[str] = []

    if terms.min_downpayment is not None and downpayment < terms.min_downpayment:
        problems.append(
            f"downpayment {downpayment} is below your minimum {terms.min_downpayment}"
        )
    if terms.max_downpayment is not None and downpayment > terms.max_downpayment:
        problems.append(
            f"downpayment {downpayment} is above your maximum {terms.max_downpayment}"
        )

    if terms.min_interest_rate_pct is not None and interest_rate_pct < terms.min_interest_rate_pct:
        problems.append(
            f"interest rate {interest_rate_pct}% is below your minimum {terms.min_interest_rate_pct}%"
        )
    if terms.max_interest_rate_pct is not None and interest_rate_pct > terms.max_interest_rate_pct:
        problems.append(
            f"interest rate {interest_rate_pct}% is above your maximum {terms.max_interest_rate_pct}%"
        )

    if terms.min_loan_length_years is not None and loan_length_years < terms.min_loan_length_years:
        problems.append(
            f"loan length {loan_length_years} years is below your minimum {terms.min_loan_length_years}"
        )
    if terms.max_loan_length_years is not None and loan_length_years > terms.max_loan_length_years:
        problems.append(
            f"loan length {loan_length_years} years is above your maximum {terms.max_loan_length_years}"
        )

    clamp_interest_structure(interest_structure)

    return problems


def make_offer_checker_tool(terms: BorrowerTerms | LenderTerms) -> FunctionTool:
    """Build a check_offer tool bound to one party's private limits."""

    def check_offer(
        downpayment: float,
        interest_rate_pct: float,
        loan_length_years: int,
        interest_structure: int,
    ) -> str:
        """Check whether a proposed loan offer is within YOUR OWN acceptable limits.

        Pass the four values you are about to offer or accept. interest_structure is 1-10
        where 1 means fixed and 10 means variable. Returns "OK" if every value is inside
        your private limits, otherwise returns the list of problems.
        Always call this before you send an offer or set consensus_reached to true.
        """
        problems = check_offer_against_limits(
            terms, downpayment, interest_rate_pct, loan_length_years, interest_structure
        )
        if problems:
            return "PROBLEMS: " + "; ".join(problems)
        return "OK: all four values are within your limits."

    return FunctionTool(
        check_offer,
        description=(
            "Check whether a proposed loan offer (downpayment, interest_rate_pct, "
            "loan_length_years, interest_structure 1-10) is within your own private limits. "
            "Call before making or accepting an offer."
        ),
        name="check_offer",
    )
