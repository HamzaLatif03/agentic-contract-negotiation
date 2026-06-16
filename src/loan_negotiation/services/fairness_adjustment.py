from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.models.workflow import Scores
from loan_negotiation.services.fairness import fairness_gap
from loan_negotiation.services.structure_scoring import (
    preferred_structure,
    structure_score_penalty,
)
from loan_negotiation.workflow.negotiation_messages import structure_kind


def _overlap_min(
    a_min: float | int | None,
    b_min: float | int | None,
) -> float | int | None:
    values = [v for v in (a_min, b_min) if v is not None]
    return max(values) if values else None


def _overlap_max(
    a_max: float | int | None,
    b_max: float | int | None,
) -> float | int | None:
    values = [v for v in (a_max, b_max) if v is not None]
    return min(values) if values else None


def _clamp(value: float, low: float | None, high: float | None) -> float:
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def _nudge_toward(current: float, target: float, *, fraction: float) -> float:
    return current + (target - current) * fraction


def _party_targets(
    party: str,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> dict[str, float | int]:
    dp_min = _overlap_min(borrower.min_downpayment, lender.min_downpayment)
    dp_max = _overlap_max(borrower.max_downpayment, lender.max_downpayment)
    rate_min = _overlap_min(borrower.min_interest_rate_pct, lender.min_interest_rate_pct)
    rate_max = _overlap_max(borrower.max_interest_rate_pct, lender.max_interest_rate_pct)
    len_min = _overlap_min(borrower.min_loan_length_years, lender.min_loan_length_years)
    len_max = _overlap_max(borrower.max_loan_length_years, lender.max_loan_length_years)

    terms = borrower if party == "borrower" else lender

    if party == "borrower":
        return {
            "downpayment": float(dp_min if dp_min is not None else terms.min_downpayment or 0),
            "interest_rate_pct": float(
                rate_min if rate_min is not None else terms.min_interest_rate_pct or 0
            ),
            "loan_length_years": int(
                len_min if len_min is not None else terms.min_loan_length_years or 1
            ),
            "interest_structure": preferred_structure(borrower),
        }

    return {
        "downpayment": float(dp_max if dp_max is not None else terms.max_downpayment or 0),
        "interest_rate_pct": float(
            rate_max if rate_max is not None else terms.max_interest_rate_pct or 0
        ),
        "loan_length_years": int(
            len_min if len_min is not None else terms.min_loan_length_years or 1
        ),
        "interest_structure": preferred_structure(lender),
    }


def _format_opening_terms(borrower: BorrowerTerms, lender: LenderTerms) -> str:
    return (
        "Borrower opening:\n"
        f"  downpayment £{borrower.min_downpayment:,.0f}-£{borrower.max_downpayment:,.0f}, "
        f"rate {borrower.min_interest_rate_pct}-{borrower.max_interest_rate_pct}%, "
        f"length {borrower.min_loan_length_years}-{borrower.max_loan_length_years}yr, "
        f"fixed {borrower.fixed_preference}/10, variable {borrower.variable_preference}/10\n"
        "Lender opening:\n"
        f"  downpayment £{lender.min_downpayment:,.0f}-£{lender.max_downpayment:,.0f}, "
        f"rate {lender.min_interest_rate_pct}-{lender.max_interest_rate_pct}%, "
        f"length {lender.min_loan_length_years}-{lender.max_loan_length_years}yr, "
        f"fixed {lender.fixed_preference}/10, variable {lender.variable_preference}/10"
    )


def _format_deal_snapshot(deal: DealTerms) -> str:
    kind = structure_kind(deal.interest_structure)
    return (
        f"Current deal: £{deal.downpayment:,.0f} down, {deal.interest_rate_pct}% rate, "
        f"{deal.loan_length_years}yr, {kind} (structure {deal.interest_structure}/10)"
    )


def disadvantaged_party(scores: Scores, *, max_gap: float = 2.0) -> str | None:
    """Return 'borrower' or 'lender' when scores are more than max_gap apart."""
    if fairness_gap(scores.borrower_score, scores.lender_score) <= max_gap:
        return None
    if scores.borrower_score < scores.lender_score:
        return "borrower"
    return "lender"


def adjust_deal_for_fairness(
    deal: DealTerms,
    scores: Scores,
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    max_gap: float = 2.0,
    nudge_fraction: float | None = None,
) -> DealTerms:
    """Nudge deal terms toward the disadvantaged party using both parties' opening terms."""
    party = disadvantaged_party(scores, max_gap=max_gap)
    if party is None:
        return deal.model_copy()

    gap = fairness_gap(scores.borrower_score, scores.lender_score)
    fraction = nudge_fraction if nudge_fraction is not None else min(0.55, 0.3 + gap * 0.08)
    targets = _party_targets(party, borrower, lender)
    party_terms = borrower if party == "borrower" else lender
    structure_penalty = structure_score_penalty(deal, party_terms)
    # When structure mismatch dominates, move structure more aggressively.
    structure_fraction = min(0.85, fraction + 0.25) if structure_penalty <= -3 else fraction

    dp_min = _overlap_min(borrower.min_downpayment, lender.min_downpayment)
    dp_max = _overlap_max(borrower.max_downpayment, lender.max_downpayment)
    rate_min = _overlap_min(borrower.min_interest_rate_pct, lender.min_interest_rate_pct)
    rate_max = _overlap_max(borrower.max_interest_rate_pct, lender.max_interest_rate_pct)
    len_min = _overlap_min(borrower.min_loan_length_years, lender.min_loan_length_years)
    len_max = _overlap_max(borrower.max_loan_length_years, lender.max_loan_length_years)

    new_dp = _clamp(
        _nudge_toward(deal.downpayment, float(targets["downpayment"]), fraction=fraction),
        float(dp_min) if dp_min is not None else None,
        float(dp_max) if dp_max is not None else None,
    )
    new_rate = _clamp(
        _nudge_toward(deal.interest_rate_pct, float(targets["interest_rate_pct"]), fraction=fraction),
        float(rate_min) if rate_min is not None else None,
        float(rate_max) if rate_max is not None else None,
    )
    new_len = _clamp(
        _nudge_toward(float(deal.loan_length_years), float(targets["loan_length_years"]), fraction=fraction),
        float(len_min) if len_min is not None else None,
        float(len_max) if len_max is not None else None,
    )
    new_structure = max(
        1,
        min(
            10,
            round(
                _nudge_toward(
                    float(deal.interest_structure),
                    float(targets["interest_structure"]),
                    fraction=structure_fraction,
                )
            ),
        ),
    )

    return DealTerms(
        downpayment=round(new_dp, 2),
        interest_rate_pct=round(new_rate, 2),
        loan_length_years=int(round(new_len)),
        interest_structure=new_structure,
        consensus_reached=deal.consensus_reached,
    )


def describe_fairness_adjustment(
    scores: Scores,
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    max_gap: float = 2.0,
) -> str:
    party = disadvantaged_party(scores, max_gap=max_gap)
    gap = fairness_gap(scores.borrower_score, scores.lender_score)
    if party is None:
        return ""

    targets = _party_targets(party, borrower, lender)
    target_kind = structure_kind(int(targets["interest_structure"]))
    party_terms = borrower if party == "borrower" else lender
    structure_penalty = structure_score_penalty(deal, party_terms)

    direction = (
        f"lower downpayment, lower rate, shorter term, more {target_kind}"
        if party == "borrower"
        else f"higher downpayment, higher rate, shorter term, more {target_kind}"
    )

    penalty_note = ""
    if structure_penalty < 0:
        penalty_note = (
            f"\nThe {party} has a {abs(structure_penalty)}-point structure penalty on the "
            f"current {structure_kind(deal.interest_structure)} deal — nudging structure toward "
            f"{target_kind} ({targets['interest_structure']}/10)."
        )

    return (
        f"Scores (borrower {scores.borrower_score}, lender {scores.lender_score}) are "
        f"{gap:.0f} apart (max {max_gap:.0f}).\n"
        f"{_format_opening_terms(borrower, lender)}\n"
        f"{_format_deal_snapshot(deal)}\n"
        f"Favour the {party}: move {direction} within overlapping ranges.{penalty_note}"
    )
