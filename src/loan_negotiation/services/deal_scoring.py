"""Deterministic deal scoring from opening ranges and rate preferences."""

from dataclasses import dataclass

from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.models.workflow import Scores
from loan_negotiation.services.structure_scoring import preferred_structure
from loan_negotiation.workflow.negotiation_messages import structure_kind


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _range_score(
    value: float,
    low: float | None,
    high: float | None,
    *,
    prefer_low: bool,
) -> float:
    """Score 1-10 from where value sits in [low, high]."""
    if low is None or high is None:
        return 5.5
    span = float(high) - float(low)
    if span <= 0:
        return 5.5
    t = _clamp((float(value) - float(low)) / span, 0.0, 1.0)
    quality = (1.0 - t) if prefer_low else t
    return 1.0 + 9.0 * quality


def _structure_score(deal: DealTerms, terms: BorrowerTerms | LenderTerms) -> float:
    preferred = float(preferred_structure(terms))
    distance = abs(float(deal.interest_structure) - preferred)
    quality = 1.0 - _clamp(distance / 9.0, 0.0, 1.0)
    return 1.0 + 9.0 * quality


def _round_score(raw: float) -> int:
    return max(1, min(10, int(round(raw))))


@dataclass(frozen=True)
class TermBreakdown:
    downpayment: float
    interest_rate: float
    loan_length: float
    interest_structure: float
    total: int


def score_for_borrower(deal: DealTerms, terms: BorrowerTerms) -> TermBreakdown:
    dp = _range_score(
        deal.downpayment, terms.min_downpayment, terms.max_downpayment, prefer_low=True
    )
    rate = _range_score(
        deal.interest_rate_pct,
        terms.min_interest_rate_pct,
        terms.max_interest_rate_pct,
        prefer_low=True,
    )
    length = _range_score(
        float(deal.loan_length_years),
        terms.min_loan_length_years,
        terms.max_loan_length_years,
        prefer_low=True,
    )
    structure = _structure_score(deal, terms)
    total = _round_score((dp + rate + length + structure) / 4.0)
    return TermBreakdown(dp, rate, length, structure, total)


def score_for_lender(deal: DealTerms, terms: LenderTerms) -> TermBreakdown:
    dp = _range_score(
        deal.downpayment, terms.min_downpayment, terms.max_downpayment, prefer_low=False
    )
    rate = _range_score(
        deal.interest_rate_pct,
        terms.min_interest_rate_pct,
        terms.max_interest_rate_pct,
        prefer_low=False,
    )
    length = _range_score(
        float(deal.loan_length_years),
        terms.min_loan_length_years,
        terms.max_loan_length_years,
        prefer_low=True,
    )
    structure = _structure_score(deal, terms)
    total = _round_score((dp + rate + length + structure) / 4.0)
    return TermBreakdown(dp, rate, length, structure, total)


def format_score_rationale(
    deal: DealTerms,
    breakdown: TermBreakdown,
    terms: BorrowerTerms | LenderTerms,
    *,
    party: str,
) -> str:
    kind = structure_kind(deal.interest_structure)
    preferred = preferred_structure(terms)
    preferred_kind = structure_kind(preferred)
    lines = [
        f"Score: {breakdown.total}/10",
        "",
        f"Deterministic score for the {party}:",
        f"- downpayment: {breakdown.downpayment:.1f}/10",
        f"- interest rate: {breakdown.interest_rate:.1f}/10",
        f"- loan length: {breakdown.loan_length:.1f}/10",
        f"- interest structure: {breakdown.interest_structure:.1f}/10 "
        f"(deal={kind}/{deal.interest_structure}, preferred≈{preferred_kind}/{preferred})",
    ]
    return "\n".join(lines)


def score_deal(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> Scores:
    borrower_bd = score_for_borrower(deal, borrower)
    lender_bd = score_for_lender(deal, lender)
    return Scores(
        borrower_score=borrower_bd.total,
        lender_score=lender_bd.total,
        borrower_rationale=format_score_rationale(
            deal, borrower_bd, borrower, party="borrower"
        ),
        lender_rationale=format_score_rationale(
            deal, lender_bd, lender, party="lender"
        ),
    )
