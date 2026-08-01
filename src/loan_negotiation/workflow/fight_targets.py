"""Private opening / fight targets derived from a party's hard ranges."""

from __future__ import annotations

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms


def fight_targets_summary(terms: BorrowerTerms | LenderTerms) -> str:
    """Tell the agent where to open and what to push toward (never reveal aloud)."""
    if isinstance(terms, BorrowerTerms):
        return (
            "\nYour aggressive targets (use these in JSON; never quote aloud as scores/limits):\n"
            f"- Opening deposit near YOUR MIN (£{terms.min_downpayment:g}) — never open at their high ask\n"
            f"- Opening rate near YOUR MIN ({terms.min_interest_rate_pct:g}%)\n"
            f"- Opening fee near YOUR MIN (£{terms.min_arrangement_fee:g}); cashback near YOUR MAX (£{terms.max_cashback:g})\n"
            f"- Overpay near YOUR MAX ({terms.max_overpayment_allowance_pct:g}%); ERC near YOUR MIN ({terms.min_erc_pct:g}%)\n"
            f"- Term toward YOUR preferred end of {terms.min_loan_length_years}–{terms.max_loan_length_years} years\n"
            f"- rate_type={terms.preferred_rate_type}; initial_period={terms.preferred_initial_period_years}; "
            f"repayment={terms.preferred_repayment_type}\n"
            "- Freebies: push ON when your preference ≥7; leave off / flexible when ≤4\n"
            "- First counter MUST change at least 2 fields toward these targets vs their offer "
            "(deposit/rate/fee/cashback are highest priority). Never paste their package unchanged "
            "unless consensus_reached true (accept).\n"
            "- If their deposit (or any field) is above YOUR MAX or below YOUR MIN, move that "
            "field onto YOUR wall immediately — never echo an illegal number.\n"
            "- Each later counter: address their latest stated reason in prose, then move JSON "
            "fields accordingly (or hold a term as commercially non-negotiable and trade elsewhere)."
        )

    return (
        "\nYour aggressive targets (use these in JSON; never quote aloud as scores/limits):\n"
        f"- Opening deposit near YOUR MAX (£{terms.max_downpayment:g})\n"
        f"- Opening rate near YOUR MAX ({terms.max_interest_rate_pct:g}%)\n"
        f"- Opening fee near YOUR MAX (£{terms.max_arrangement_fee:g}); cashback near YOUR MIN (£{terms.min_cashback:g})\n"
        f"- Overpay near YOUR MIN ({terms.min_overpayment_allowance_pct:g}%); ERC near YOUR MAX ({terms.max_erc_pct:g}%)\n"
        f"- Term toward YOUR preferred end of {terms.min_loan_length_years}–{terms.max_loan_length_years} years\n"
        f"- rate_type={terms.preferred_rate_type}; initial_period={terms.preferred_initial_period_years}; "
        f"repayment={terms.preferred_repayment_type}\n"
        "- Freebies: grant only when preference ≥7 or needed to close a better rate/fee; "
        "refuse when preference ≤4\n"
        "- Counters MUST move at least one field toward these targets. Never paste their package "
        "unchanged unless consensus_reached true (accept).\n"
        "- If their offer breaks YOUR walls on any field, clamp that field onto YOUR wall in "
        "your JSON — never publish an illegal number.\n"
        "- Each later counter: address their latest stated reason in prose, then move JSON "
        "fields accordingly (or hold a term as commercially non-negotiable and trade elsewhere)."
    )
