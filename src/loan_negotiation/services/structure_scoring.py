from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms


def preferred_structure(terms: BorrowerTerms | LenderTerms) -> int:
    """Map fixed/variable preferences (1-10 each) to a target structure (1=fixed, 10=variable)."""
    fixed = terms.fixed_preference or 5
    variable = terms.variable_preference or 5
    total = fixed + variable
    if total <= 0:
        return 5
    return max(1, min(10, round(1 + 9 * variable / total)))


def structure_score_penalty(
    deal: DealTerms,
    terms: BorrowerTerms | LenderTerms,
) -> int:
    """Penalty when the agreed structure favours what the party did not want."""
    is_fixed = deal.interest_structure <= 5
    if is_fixed:
        aligned = terms.fixed_preference or 5
        sacrificed = terms.variable_preference or 5
    else:
        aligned = terms.variable_preference or 5
        sacrificed = terms.fixed_preference or 5

    if sacrificed >= 8 and aligned <= 3:
        return -4
    if sacrificed >= 7 and aligned <= 4:
        return -3
    if sacrificed >= 6 and aligned <= 4:
        return -2
    return 0
