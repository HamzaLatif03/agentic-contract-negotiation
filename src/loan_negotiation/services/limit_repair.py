"""Clamp a deal into overlapping ranges — small touch-ups only."""

from __future__ import annotations

from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.services.limit_compensation import evaluate_deal_limits

_CONTINUOUS_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("downpayment", "min_downpayment", "max_downpayment", "deposit"),
    ("interest_rate_pct", "min_interest_rate_pct", "max_interest_rate_pct", "interest rate"),
    ("loan_length_years", "min_loan_length_years", "max_loan_length_years", "loan term"),
    ("arrangement_fee", "min_arrangement_fee", "max_arrangement_fee", "arrangement fee"),
    ("cashback", "min_cashback", "max_cashback", "cashback"),
    (
        "overpayment_allowance_pct",
        "min_overpayment_allowance_pct",
        "max_overpayment_allowance_pct",
        "overpayment allowance",
    ),
    ("erc_pct", "min_erc_pct", "max_erc_pct", "ERC"),
)

# Reject repair if any field needs a larger move than this (middleman irons instead).
_MAX_TOUCHUP: dict[str, float] = {
    "downpayment": 2_000.0,
    "interest_rate_pct": 0.10,
    "loan_length_years": 1.0,
    "arrangement_fee": 150.0,
    "cashback": 100.0,
    "overpayment_allowance_pct": 1.0,
    "erc_pct": 0.25,
}


def _overlap_min(a: float | int | None, b: float | int | None) -> float | None:
    values = [float(v) for v in (a, b) if v is not None]
    return max(values) if values else None


def _overlap_max(a: float | int | None, b: float | int | None) -> float | None:
    values = [float(v) for v in (a, b) if v is not None]
    return min(values) if values else None


def _clamp(value: float, low: float | None, high: float | None) -> float:
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def _project_fields(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
    *,
    max_delta: dict[str, float] | None,
) -> tuple[DealTerms, list[str]]:
    """Clamp continuous fields into overlap. If max_delta set, skip oversized moves."""
    updates: dict = {}
    notes: list[str] = []

    for value_attr, min_attr, max_attr, label in _CONTINUOUS_FIELDS:
        current = float(getattr(deal, value_attr))
        low = _overlap_min(getattr(borrower, min_attr), getattr(lender, min_attr))
        high = _overlap_max(getattr(borrower, max_attr), getattr(lender, max_attr))
        if low is not None and high is not None and low > high:
            continue
        repaired = _clamp(current, low, high)
        if value_attr == "loan_length_years":
            repaired = float(int(round(repaired)))
        else:
            repaired = round(repaired, 2)
        delta = abs(repaired - current)
        if delta <= 1e-9:
            continue
        if max_delta is not None:
            cap = max_delta.get(value_attr, 0.0)
            if delta > cap:
                notes.append(
                    f"{label}: {current:g} needs {repaired:g} "
                    f"(delta {delta:g} exceeds touch-up max {cap:g})"
                )
                continue
        updates[value_attr] = int(repaired) if value_attr == "loan_length_years" else repaired
        notes.append(f"{label}: {current:g} → {repaired:g}")

    if not updates:
        return deal.model_copy(), notes
    return deal.model_copy(update=updates), notes


def repair_deal_to_limits(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> tuple[DealTerms, list[str]]:
    """Tiny clamps into overlap; large gaps left for middleman fairness ironing."""
    return _project_fields(deal, borrower, lender, max_delta=_MAX_TOUCHUP)


def project_deal_into_overlap(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> tuple[DealTerms, list[str]]:
    """Full clamp into overlapping ranges (fairness mediator proposals)."""
    return _project_fields(deal, borrower, lender, max_delta=None)


def repair_clears_limit_issues(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> tuple[DealTerms | None, list[str]]:
    """Return repaired deal only if hard limits clear after small touch-ups."""
    repaired, notes = repair_deal_to_limits(deal, borrower, lender)
    if evaluate_deal_limits(repaired, borrower, lender).blocking_issues:
        return None, notes
    return repaired, notes
