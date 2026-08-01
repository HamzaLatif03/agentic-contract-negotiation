"""Deterministic UK mortgage deal scoring from opening ranges and preferences."""

from __future__ import annotations

from dataclasses import dataclass

from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.models.workflow import Scores


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _range_score(
    value: float,
    low: float | None,
    high: float | None,
    *,
    prefer_low: bool,
) -> float:
    if low is None or high is None:
        return 5.5
    span = float(high) - float(low)
    if span <= 0:
        return 5.5
    t = _clamp((float(value) - float(low)) / span, 0.0, 1.0)
    quality = (1.0 - t) if prefer_low else t
    return 1.0 + 9.0 * quality


def _pref_match(deal_value: object, preferred: object | None) -> float:
    if preferred is None:
        return 5.5
    return 10.0 if deal_value == preferred else 2.0


def _feature_pref_score(deal_value: bool, preference: int | None) -> float:
    """Score a yes/no feature against a 1–10 desire (10 = strongly want ON)."""
    if preference is None:
        return 5.5
    pref = float(preference)
    return pref if deal_value else (11.0 - pref)


@dataclass(frozen=True)
class TermBreakdown:
    deposit: float
    interest_rate: float
    loan_term: float
    arrangement_fee: float
    cashback: float
    overpayment: float
    erc: float
    rate_type: float
    initial_period: float
    repayment_type: float
    portable: float
    free_valuation: float
    free_legal: float
    total: float

    @property
    def parts(self) -> tuple[float, ...]:
        return (
            self.deposit,
            self.interest_rate,
            self.loan_term,
            self.arrangement_fee,
            self.cashback,
            self.overpayment,
            self.erc,
            self.rate_type,
            self.initial_period,
            self.repayment_type,
            self.portable,
            self.free_valuation,
            self.free_legal,
        )


def _score_party(
    deal: DealTerms,
    terms: BorrowerTerms | LenderTerms,
    *,
    party: str,
) -> TermBreakdown:
    borrower = party == "borrower"
    deposit = _range_score(
        deal.downpayment,
        terms.min_downpayment,
        terms.max_downpayment,
        prefer_low=borrower,
    )
    rate = _range_score(
        deal.interest_rate_pct,
        terms.min_interest_rate_pct,
        terms.max_interest_rate_pct,
        prefer_low=borrower,
    )
    length = _range_score(
        float(deal.loan_length_years),
        terms.min_loan_length_years,
        terms.max_loan_length_years,
        prefer_low=True,
    )
    fee = _range_score(
        deal.arrangement_fee,
        terms.min_arrangement_fee,
        terms.max_arrangement_fee,
        prefer_low=borrower,
    )
    cashback = _range_score(
        deal.cashback,
        terms.min_cashback,
        terms.max_cashback,
        prefer_low=not borrower,
    )
    overpay = _range_score(
        deal.overpayment_allowance_pct,
        terms.min_overpayment_allowance_pct,
        terms.max_overpayment_allowance_pct,
        prefer_low=not borrower,
    )
    erc = _range_score(
        deal.erc_pct,
        terms.min_erc_pct,
        terms.max_erc_pct,
        prefer_low=borrower,
    )
    rate_type = _pref_match(deal.rate_type, terms.preferred_rate_type)
    period = _pref_match(deal.initial_period_years, terms.preferred_initial_period_years)
    repay = _pref_match(deal.repayment_type, terms.preferred_repayment_type)
    portable = _feature_pref_score(deal.portable, terms.portable_preference)
    free_val = _feature_pref_score(deal.free_valuation, terms.free_valuation_preference)
    free_legal = _feature_pref_score(deal.free_legal, terms.free_legal_preference)

    parts = (
        deposit,
        rate,
        length,
        fee,
        cashback,
        overpay,
        erc,
        rate_type,
        period,
        repay,
        portable,
        free_val,
        free_legal,
    )
    total = max(1.0, min(10.0, round(sum(parts) / len(parts), 1)))
    return TermBreakdown(
        deposit,
        rate,
        length,
        fee,
        cashback,
        overpay,
        erc,
        rate_type,
        period,
        repay,
        portable,
        free_val,
        free_legal,
        total,
    )


def score_for_borrower(deal: DealTerms, terms: BorrowerTerms) -> TermBreakdown:
    return _score_party(deal, terms, party="borrower")


def score_for_lender(deal: DealTerms, terms: LenderTerms) -> TermBreakdown:
    return _score_party(deal, terms, party="lender")


def format_score_rationale(
    deal: DealTerms,
    breakdown: TermBreakdown,
    terms: BorrowerTerms | LenderTerms,
    *,
    party: str,
) -> str:
    return (
        f"Score: {breakdown.total:.1f}/10\n\n"
        f"UK mortgage score for the {party}:\n"
        f"- deposit: {breakdown.deposit:.1f}/10\n"
        f"- interest rate: {breakdown.interest_rate:.1f}/10\n"
        f"- loan term: {breakdown.loan_term:.1f}/10\n"
        f"- arrangement fee: {breakdown.arrangement_fee:.1f}/10\n"
        f"- cashback: {breakdown.cashback:.1f}/10\n"
        f"- overpayment allowance: {breakdown.overpayment:.1f}/10\n"
        f"- ERC: {breakdown.erc:.1f}/10\n"
        f"- rate type ({deal.rate_type}, prefer {terms.preferred_rate_type}): "
        f"{breakdown.rate_type:.1f}/10\n"
        f"- initial period ({deal.initial_period_years}yr, prefer "
        f"{terms.preferred_initial_period_years}yr): {breakdown.initial_period:.1f}/10\n"
        f"- repayment ({deal.repayment_type}): {breakdown.repayment_type:.1f}/10\n"
        f"- portable (desire {terms.portable_preference}/10): {breakdown.portable:.1f}/10 | "
        f"free valuation ({terms.free_valuation_preference}/10): {breakdown.free_valuation:.1f}/10 | "
        f"free legal ({terms.free_legal_preference}/10): {breakdown.free_legal:.1f}/10"
    )


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
        lender_rationale=format_score_rationale(deal, lender_bd, lender, party="lender"),
    )
