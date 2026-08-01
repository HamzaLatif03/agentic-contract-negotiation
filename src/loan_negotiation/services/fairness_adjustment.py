from pydantic import BaseModel

from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms, wants_feature
from loan_negotiation.models.workflow import Scores
from loan_negotiation.services.deal_scoring import score_deal
from loan_negotiation.services.limit_compensation import evaluate_deal_limits
from loan_negotiation.services.limit_repair import project_deal_into_overlap
from loan_negotiation.workflow.negotiation_messages import format_deal_line


class FairnessResult(BaseModel):
    passed: bool
    fairness_gap: float
    feedback: str = ""


def fairness_gap(borrower_score: float, lender_score: float) -> float:
    return round(abs(float(borrower_score) - float(lender_score)), 1)


def check_fairness(scores: Scores, *, max_gap: float = 2.0) -> FairnessResult:
    gap = fairness_gap(scores.borrower_score, scores.lender_score)
    passed = gap <= max_gap
    feedback = ""
    if not passed:
        feedback = (
            f"Scores ({scores.borrower_score:.1f}, {scores.lender_score:.1f}) differ by "
            f"{gap:.1f} (max allowed gap is {max_gap:.1f})."
        )
    return FairnessResult(passed=passed, fairness_gap=gap, feedback=feedback)


def _overlap_min(a_min: float | int | None, b_min: float | int | None) -> float | int | None:
    values = [v for v in (a_min, b_min) if v is not None]
    return max(values) if values else None


def _overlap_max(a_max: float | int | None, b_max: float | int | None) -> float | int | None:
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


def disadvantaged_party(scores: Scores, *, max_gap: float = 2.0) -> str | None:
    if fairness_gap(scores.borrower_score, scores.lender_score) <= max_gap:
        return None
    if scores.borrower_score < scores.lender_score:
        return "borrower"
    return "lender"


def _party_targets(
    party: str,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> dict:
    terms = borrower if party == "borrower" else lender
    dp_min = _overlap_min(borrower.min_downpayment, lender.min_downpayment)
    dp_max = _overlap_max(borrower.max_downpayment, lender.max_downpayment)
    rate_min = _overlap_min(borrower.min_interest_rate_pct, lender.min_interest_rate_pct)
    rate_max = _overlap_max(borrower.max_interest_rate_pct, lender.max_interest_rate_pct)
    len_min = _overlap_min(borrower.min_loan_length_years, lender.min_loan_length_years)
    fee_min = _overlap_min(borrower.min_arrangement_fee, lender.min_arrangement_fee)
    fee_max = _overlap_max(borrower.max_arrangement_fee, lender.max_arrangement_fee)
    cash_min = _overlap_min(borrower.min_cashback, lender.min_cashback)
    cash_max = _overlap_max(borrower.max_cashback, lender.max_cashback)
    over_min = _overlap_min(
        borrower.min_overpayment_allowance_pct, lender.min_overpayment_allowance_pct
    )
    over_max = _overlap_max(
        borrower.max_overpayment_allowance_pct, lender.max_overpayment_allowance_pct
    )
    erc_min = _overlap_min(borrower.min_erc_pct, lender.min_erc_pct)
    erc_max = _overlap_max(borrower.max_erc_pct, lender.max_erc_pct)

    if party == "borrower":
        return {
            "downpayment": float(dp_min if dp_min is not None else terms.min_downpayment or 0),
            "interest_rate_pct": float(
                rate_min if rate_min is not None else terms.min_interest_rate_pct or 0
            ),
            "loan_length_years": int(
                len_min if len_min is not None else terms.min_loan_length_years or 1
            ),
            "arrangement_fee": float(fee_min if fee_min is not None else 0),
            "cashback": float(cash_max if cash_max is not None else terms.max_cashback or 0),
            "overpayment_allowance_pct": float(
                over_max if over_max is not None else terms.max_overpayment_allowance_pct or 10
            ),
            "erc_pct": float(erc_min if erc_min is not None else 0),
            "rate_type": terms.preferred_rate_type or "fixed",
            "initial_period_years": terms.preferred_initial_period_years or 5,
            "repayment_type": terms.preferred_repayment_type or "capital_repayment",
            "portable": wants_feature(terms.portable_preference, default=True),
            "free_valuation": wants_feature(terms.free_valuation_preference, default=True),
            "free_legal": wants_feature(terms.free_legal_preference, default=True),
        }

    return {
        "downpayment": float(dp_max if dp_max is not None else terms.max_downpayment or 0),
        "interest_rate_pct": float(
            rate_max if rate_max is not None else terms.max_interest_rate_pct or 0
        ),
        "loan_length_years": int(
            len_min if len_min is not None else terms.min_loan_length_years or 1
        ),
        "arrangement_fee": float(fee_max if fee_max is not None else terms.max_arrangement_fee or 0),
        "cashback": float(cash_min if cash_min is not None else 0),
        "overpayment_allowance_pct": float(
            over_min if over_min is not None else terms.min_overpayment_allowance_pct or 5
        ),
        "erc_pct": float(erc_max if erc_max is not None else terms.max_erc_pct or 0),
        "rate_type": terms.preferred_rate_type or "tracker",
        "initial_period_years": terms.preferred_initial_period_years or 2,
        "repayment_type": terms.preferred_repayment_type or "capital_repayment",
        "portable": wants_feature(terms.portable_preference, default=False),
        "free_valuation": wants_feature(terms.free_valuation_preference, default=False),
        "free_legal": wants_feature(terms.free_legal_preference, default=False),
    }


def adjust_deal_for_fairness(
    deal: DealTerms,
    scores: Scores,
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    max_gap: float = 2.0,
    nudge_fraction: float | None = None,
) -> DealTerms:
    party = disadvantaged_party(scores, max_gap=max_gap)
    if party is None:
        return deal.model_copy()

    gap = fairness_gap(scores.borrower_score, scores.lender_score)
    # Larger gaps get stronger moves so the silent fallback can reach ≤2.
    fraction = nudge_fraction if nudge_fraction is not None else min(0.85, 0.4 + gap * 0.12)
    targets = _party_targets(party, borrower, lender)
    # Categorical flips easily overshoot and oscillate — only when gap is wide.
    change_categoricals = gap > 3.0

    def nudge_num(attr: str, low, high) -> float:
        return _clamp(
            _nudge_toward(float(getattr(deal, attr)), float(targets[attr]), fraction=fraction),
            float(low) if low is not None else None,
            float(high) if high is not None else None,
        )

    new_dp = nudge_num(
        "downpayment",
        _overlap_min(borrower.min_downpayment, lender.min_downpayment),
        _overlap_max(borrower.max_downpayment, lender.max_downpayment),
    )
    new_rate = nudge_num(
        "interest_rate_pct",
        _overlap_min(borrower.min_interest_rate_pct, lender.min_interest_rate_pct),
        _overlap_max(borrower.max_interest_rate_pct, lender.max_interest_rate_pct),
    )
    new_len = nudge_num(
        "loan_length_years",
        _overlap_min(borrower.min_loan_length_years, lender.min_loan_length_years),
        _overlap_max(borrower.max_loan_length_years, lender.max_loan_length_years),
    )
    new_fee = nudge_num(
        "arrangement_fee",
        _overlap_min(borrower.min_arrangement_fee, lender.min_arrangement_fee),
        _overlap_max(borrower.max_arrangement_fee, lender.max_arrangement_fee),
    )
    new_cash = nudge_num(
        "cashback",
        _overlap_min(borrower.min_cashback, lender.min_cashback),
        _overlap_max(borrower.max_cashback, lender.max_cashback),
    )
    new_over = nudge_num(
        "overpayment_allowance_pct",
        _overlap_min(borrower.min_overpayment_allowance_pct, lender.min_overpayment_allowance_pct),
        _overlap_max(borrower.max_overpayment_allowance_pct, lender.max_overpayment_allowance_pct),
    )
    new_erc = nudge_num(
        "erc_pct",
        _overlap_min(borrower.min_erc_pct, lender.min_erc_pct),
        _overlap_max(borrower.max_erc_pct, lender.max_erc_pct),
    )

    rate_type = deal.rate_type
    initial_period_years = deal.initial_period_years
    repayment_type = deal.repayment_type
    portable = deal.portable
    free_valuation = deal.free_valuation
    free_legal = deal.free_legal
    if change_categoricals:
        rate_type = targets["rate_type"]
        initial_period_years = int(targets["initial_period_years"])
        repayment_type = targets["repayment_type"]
        terms = borrower if party == "borrower" else lender
        if terms.portable_preference is not None and abs(terms.portable_preference - 5) >= 2:
            portable = bool(targets["portable"])
        if terms.free_valuation_preference is not None and abs(terms.free_valuation_preference - 5) >= 2:
            free_valuation = bool(targets["free_valuation"])
        if terms.free_legal_preference is not None and abs(terms.free_legal_preference - 5) >= 2:
            free_legal = bool(targets["free_legal"])

    return DealTerms(
        downpayment=round(new_dp, 2),
        interest_rate_pct=round(new_rate, 2),
        loan_length_years=int(round(new_len)),
        arrangement_fee=round(new_fee, 2),
        cashback=round(new_cash, 2),
        overpayment_allowance_pct=round(new_over, 2),
        erc_pct=round(new_erc, 2),
        rate_type=rate_type,
        initial_period_years=int(initial_period_years),
        repayment_type=repayment_type,
        portable=portable,
        free_valuation=free_valuation,
        free_legal=free_legal,
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
    return (
        f"Scores (borrower {scores.borrower_score:.1f}, lender {scores.lender_score:.1f}) are "
        f"{gap:.1f} apart (max {max_gap:.1f}).\n"
        f"Current deal: {format_deal_line(deal)}\n"
        f"Favour the {party}: nudge numeric terms within overlapping ranges and "
        f"align product features toward their preferences."
    )


def propose_fair_deal(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    scores: Scores | None = None,
    max_gap: float = 2.0,
) -> tuple[DealTerms, list[str]]:
    """
    Build one mediator proposal inside both parties' overlapping hard limits.

    Projects out-of-range fields fully into overlap, then nudges once toward the
    disadvantaged party when scores (or re-scored projection) are unfair.
    """
    notes: list[str] = []
    projected, project_notes = project_deal_into_overlap(deal, borrower, lender)
    notes.extend(project_notes)

    working = projected.model_copy(update={"consensus_reached": False})
    if evaluate_deal_limits(working, borrower, lender).blocking_issues:
        notes.append("Could not fully project into overlapping ranges")
        return working, notes

    active_scores = scores
    if active_scores is None or evaluate_deal_limits(deal, borrower, lender).blocking_issues:
        active_scores = score_deal(working, borrower, lender)

    fairness = check_fairness(active_scores, max_gap=max_gap)
    if not fairness.passed:
        adjusted = adjust_deal_for_fairness(
            working, active_scores, borrower, lender, max_gap=max_gap
        )
        if evaluate_deal_limits(adjusted, borrower, lender).blocking_issues:
            notes.append("Fairness nudge would leave hard limits — keeping overlap projection")
        else:
            notes.append(describe_fairness_adjustment(active_scores, working, borrower, lender))
            working = adjusted.model_copy(update={"consensus_reached": False})

    return working, notes


def _mid(a: float | int | None, b: float | int | None) -> float | None:
    if a is None and b is None:
        return None
    if a is None:
        return float(b)  # type: ignore[arg-type]
    if b is None:
        return float(a)
    return (float(a) + float(b)) / 2.0


def seed_overlap_deal(borrower: BorrowerTerms, lender: LenderTerms) -> DealTerms:
    """Neutral package at the midpoint of overlapping continuous ranges."""
    dp_lo = _overlap_min(borrower.min_downpayment, lender.min_downpayment)
    dp_hi = _overlap_max(borrower.max_downpayment, lender.max_downpayment)
    rate_lo = _overlap_min(borrower.min_interest_rate_pct, lender.min_interest_rate_pct)
    rate_hi = _overlap_max(borrower.max_interest_rate_pct, lender.max_interest_rate_pct)
    len_lo = _overlap_min(borrower.min_loan_length_years, lender.min_loan_length_years)
    len_hi = _overlap_max(borrower.max_loan_length_years, lender.max_loan_length_years)
    fee_lo = _overlap_min(borrower.min_arrangement_fee, lender.min_arrangement_fee)
    fee_hi = _overlap_max(borrower.max_arrangement_fee, lender.max_arrangement_fee)
    cash_lo = _overlap_min(borrower.min_cashback, lender.min_cashback)
    cash_hi = _overlap_max(borrower.max_cashback, lender.max_cashback)
    over_lo = _overlap_min(
        borrower.min_overpayment_allowance_pct, lender.min_overpayment_allowance_pct
    )
    over_hi = _overlap_max(
        borrower.max_overpayment_allowance_pct, lender.max_overpayment_allowance_pct
    )
    erc_lo = _overlap_min(borrower.min_erc_pct, lender.min_erc_pct)
    erc_hi = _overlap_max(borrower.max_erc_pct, lender.max_erc_pct)

    def band_mid(lo: float | None, hi: float | None, fallback: float) -> float:
        if lo is not None and hi is not None and lo <= hi:
            return (lo + hi) / 2.0
        if lo is not None:
            return lo
        if hi is not None:
            return hi
        return fallback

    period = int(
        round(
            _mid(
                borrower.preferred_initial_period_years,
                lender.preferred_initial_period_years,
            )
            or 5
        )
    )
    if period not in (2, 5, 10):
        period = min((2, 5, 10), key=lambda p: abs(p - period))

    return DealTerms(
        downpayment=round(band_mid(dp_lo, dp_hi, 70_000), 2),
        interest_rate_pct=round(band_mid(rate_lo, rate_hi, 5.0), 2),
        loan_length_years=int(round(band_mid(len_lo, len_hi, 25))),
        arrangement_fee=round(band_mid(fee_lo, fee_hi, 999), 2),
        cashback=round(band_mid(cash_lo, cash_hi, 500), 2),
        overpayment_allowance_pct=round(band_mid(over_lo, over_hi, 10), 2),
        erc_pct=round(band_mid(erc_lo, erc_hi, 2), 2),
        rate_type=borrower.preferred_rate_type or lender.preferred_rate_type or "fixed",
        initial_period_years=period,
        repayment_type=(
            borrower.preferred_repayment_type
            or lender.preferred_repayment_type
            or "capital_repayment"
        ),
        portable=wants_feature(
            int(
                round(
                    _mid(borrower.portable_preference, lender.portable_preference) or 5
                )
            ),
            default=False,
        ),
        free_valuation=wants_feature(
            int(
                round(
                    _mid(
                        borrower.free_valuation_preference,
                        lender.free_valuation_preference,
                    )
                    or 5
                )
            ),
            default=False,
        ),
        free_legal=wants_feature(
            int(
                round(
                    _mid(borrower.free_legal_preference, lender.free_legal_preference)
                    or 5
                )
            ),
            default=False,
        ),
        consensus_reached=False,
    )


def _blend_targets(
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    borrower_weight: float,
) -> dict:
    """Blend borrower/lender ideals. weight 1.0 = full borrower ideal, 0.0 = lender."""
    t = max(0.0, min(1.0, borrower_weight))
    b = _party_targets("borrower", borrower, lender)
    l = _party_targets("lender", borrower, lender)
    blended: dict = {}
    for key in (
        "downpayment",
        "interest_rate_pct",
        "loan_length_years",
        "arrangement_fee",
        "cashback",
        "overpayment_allowance_pct",
        "erc_pct",
    ):
        blended[key] = float(l[key]) + (float(b[key]) - float(l[key])) * t
    # Categoricals: prefer borrower side when weight ≥ 0.5
    src = b if t >= 0.5 else l
    blended["rate_type"] = src["rate_type"]
    blended["initial_period_years"] = src["initial_period_years"]
    blended["repayment_type"] = src["repayment_type"]
    blended["portable"] = src["portable"]
    blended["free_valuation"] = src["free_valuation"]
    blended["free_legal"] = src["free_legal"]
    return blended


def _deal_from_targets(targets: dict, *, consensus_reached: bool) -> DealTerms:
    return DealTerms(
        downpayment=round(float(targets["downpayment"]), 2),
        interest_rate_pct=round(float(targets["interest_rate_pct"]), 2),
        loan_length_years=int(round(float(targets["loan_length_years"]))),
        arrangement_fee=round(float(targets["arrangement_fee"]), 2),
        cashback=round(float(targets["cashback"]), 2),
        overpayment_allowance_pct=round(float(targets["overpayment_allowance_pct"]), 2),
        erc_pct=round(float(targets["erc_pct"]), 2),
        rate_type=targets["rate_type"],
        initial_period_years=int(targets["initial_period_years"]),
        repayment_type=targets["repayment_type"],
        portable=bool(targets["portable"]),
        free_valuation=bool(targets["free_valuation"]),
        free_legal=bool(targets["free_legal"]),
        consensus_reached=consensus_reached,
    )


def balance_deal_within_ranges(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    max_gap: float = 2.0,
) -> tuple[DealTerms, list[str]]:
    """
    Old silent method: keep the package inside both sides' overlapping ranges and
    narrow the score gap to ≤ max_gap (default 2).

    1) Project into overlap
    2) Pick the best in-range borrower/lender blend as a start
    3) Nudge toward the disadvantaged party until gap ≤ max_gap
    """
    notes: list[str] = []
    projected, project_notes = project_deal_into_overlap(deal, borrower, lender)
    notes.extend(project_notes)
    working = projected.model_copy(update={"consensus_reached": True})
    if evaluate_deal_limits(working, borrower, lender).blocking_issues:
        notes.append("Could not project into overlapping ranges for score balance")
        return working, notes

    best = working
    best_gap = check_fairness(score_deal(best, borrower, lender), max_gap=max_gap).fairness_gap
    if best_gap <= max_gap:
        notes.append(f"Projected package already fair (score gap {best_gap:.1f}).")
        return best, notes

    # Sweep borrower-weight from lender-favouring (0) to borrower-favouring (1).
    for i in range(11):
        targets = _blend_targets(borrower, lender, borrower_weight=i / 10)
        candidate = _deal_from_targets(targets, consensus_reached=True)
        if evaluate_deal_limits(candidate, borrower, lender).blocking_issues:
            continue
        gap = check_fairness(
            score_deal(candidate, borrower, lender), max_gap=max_gap
        ).fairness_gap
        if gap < best_gap - 1e-9:
            best = candidate
            best_gap = gap
        if gap <= max_gap:
            notes.append(
                f"Balanced package at borrower-weight {i / 10:.1f} "
                f"(score gap {gap:.1f} ≤ {max_gap:.1f})."
            )
            return best, notes

    # Score-directed nudges from the best blend (classic silent tweak loop).
    working = best
    prev_gap: float | None = None
    for _ in range(12):
        scored = score_deal(working, borrower, lender)
        gap = check_fairness(scored, max_gap=max_gap).fairness_gap
        if gap <= max_gap:
            notes.append(
                f"Score tweaks brought gap to {gap:.1f} (≤ {max_gap:.1f}) "
                "while staying inside both sides' ranges."
            )
            return working, notes
        if prev_gap is not None and gap >= prev_gap - 1e-9:
            break
        prev_gap = gap
        adjusted = adjust_deal_for_fairness(
            working, scored, borrower, lender, max_gap=max_gap
        )
        if evaluate_deal_limits(adjusted, borrower, lender).blocking_issues:
            notes.append("Fairness nudge would leave hard limits — stopping balance loop")
            break
        if (
            adjusted.downpayment == working.downpayment
            and adjusted.interest_rate_pct == working.interest_rate_pct
            and adjusted.arrangement_fee == working.arrangement_fee
            and adjusted.cashback == working.cashback
            and adjusted.overpayment_allowance_pct == working.overpayment_allowance_pct
            and adjusted.erc_pct == working.erc_pct
            and adjusted.loan_length_years == working.loan_length_years
            and adjusted.rate_type == working.rate_type
            and adjusted.portable == working.portable
            and adjusted.free_valuation == working.free_valuation
            and adjusted.free_legal == working.free_legal
        ):
            break
        notes.append(describe_fairness_adjustment(scored, working, borrower, lender))
        working = adjusted

    final_gap = check_fairness(
        score_deal(working, borrower, lender), max_gap=max_gap
    ).fairness_gap
    notes.append(
        f"Best balanced package still has score gap {final_gap:.1f} "
        f"(target ≤ {max_gap:.1f}); keeping closest in-range tweak."
    )
    return working, notes


def close_deal_via_fairness(
    seed: DealTerms | None,
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    scores: Scores | None = None,
    max_gap: float = 2.0,
    reason: str = "Rounds exhausted without mutual accept — fairness mediator closing the deal.",
) -> tuple[DealTerms | None, list[str]]:
    """
    Lock a mediator package when negotiation stalls or consensus is still invalid.

    Projects into overlap, then searches blended in-range packages to bring the
    score gap within max_gap (default 2).
    """
    notes: list[str] = [reason]
    base = seed if seed is not None else seed_overlap_deal(borrower, lender)
    if seed is None:
        notes.append("No partial offer available — seeded from overlapping midpoints.")

    proposal, proposal_notes = propose_fair_deal(
        base, borrower, lender, scores=scores, max_gap=max_gap
    )
    notes.extend(proposal_notes)

    balanced, balance_notes = balance_deal_within_ranges(
        proposal, borrower, lender, max_gap=max_gap
    )
    notes.extend(balance_notes)
    proposal = balanced

    if evaluate_deal_limits(proposal, borrower, lender).blocking_issues:
        notes.append("Fairness mediator could not produce a package inside hard limits.")
        return None, notes

    closed = proposal.model_copy(update={"consensus_reached": True})
    notes.append(f"Mediator locked package: {format_deal_line(closed)}")
    return closed, notes
