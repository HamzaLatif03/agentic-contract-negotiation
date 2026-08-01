from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.services.limit_compensation import (
    collect_party_breaches,
    split_soft_hard,
)
from loan_negotiation.workflow.deal_parser import problems_against_party_limits
from autogen_core.tools import FunctionTool


def check_offer_against_limits(
    terms: BorrowerTerms | LenderTerms,
    downpayment: float,
    interest_rate_pct: float,
    loan_length_years: int,
    rate_type: str,
    initial_period_years: int,
    arrangement_fee: float,
    cashback: float,
    overpayment_allowance_pct: float,
    erc_pct: float,
    repayment_type: str,
    portable: bool,
    free_valuation: bool,
    free_legal: bool,
) -> list[str]:
    """Return hard violations of a party's limits (empty = OK or only soft bend)."""
    deal = DealTerms(
        downpayment=downpayment,
        interest_rate_pct=interest_rate_pct,
        loan_length_years=loan_length_years,
        rate_type=rate_type,
        initial_period_years=initial_period_years,
        arrangement_fee=arrangement_fee,
        cashback=cashback,
        overpayment_allowance_pct=overpayment_allowance_pct,
        erc_pct=erc_pct,
        repayment_type=repayment_type,
        portable=portable,
        free_valuation=free_valuation,
        free_legal=free_legal,
        consensus_reached=False,
    )
    return problems_against_party_limits(terms, deal)


def format_check_offer_result(terms: BorrowerTerms | LenderTerms, deal: DealTerms) -> str:
    """Tool text: never includes numeric mins/maxes (safe if shared in chat)."""
    party = "borrower" if isinstance(terms, BorrowerTerms) else "lender"
    breaches = collect_party_breaches(terms, deal, party=party)
    if not breaches:
        return "OK: offer fits your private walls."
    soft, hard = split_soft_hard(breaches)
    if hard:
        fields = ", ".join(sorted({b.field.replace("_", " ") for b in hard}))
        return (
            f"PROBLEMS: {fields} is past what you can accept. "
            "In your spoken reply call that term non-negotiable (or 'as far as we will go') — "
            "never say hard/soft limit, range, or min/max. Counter elsewhere in JSON. "
            "(Do not reveal your numeric mins/maxes.)"
        )
    fields = ", ".join(sorted({b.field.replace("_", " ") for b in soft}))
    return (
        f"SOFT: tiny bend on {fields}. Prefer staying tighter; accept only if the rest of "
        "the package clearly compensates. In prose stay commercial — never say 'soft limit'. "
        "(Do not reveal your numeric mins/maxes.)"
    )


def make_offer_checker_tool(terms: BorrowerTerms | LenderTerms) -> FunctionTool:
    """Build a check_offer tool bound to one party's private limits."""

    def check_offer(
        downpayment: float,
        interest_rate_pct: float,
        loan_length_years: int,
        rate_type: str,
        initial_period_years: int,
        arrangement_fee: float,
        cashback: float,
        overpayment_allowance_pct: float,
        erc_pct: float,
        repayment_type: str,
        portable: bool,
        free_valuation: bool,
        free_legal: bool,
    ) -> str:
        """Check whether a proposed UK mortgage offer fits your private limits."""
        deal = DealTerms(
            downpayment=downpayment,
            interest_rate_pct=interest_rate_pct,
            loan_length_years=loan_length_years,
            rate_type=rate_type,
            initial_period_years=initial_period_years,
            arrangement_fee=arrangement_fee,
            cashback=cashback,
            overpayment_allowance_pct=overpayment_allowance_pct,
            erc_pct=erc_pct,
            repayment_type=repayment_type,
            portable=portable,
            free_valuation=free_valuation,
            free_legal=free_legal,
            consensus_reached=False,
        )
        return format_check_offer_result(terms, deal)

    return FunctionTool(
        check_offer,
        description=(
            "Check whether a proposed UK mortgage offer fits your private limits. "
            "Returns OK, SOFT (tiny bend), or PROBLEMS without exposing numeric bounds."
        ),
        name="check_offer",
    )
