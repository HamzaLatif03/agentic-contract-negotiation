"""Limit checks with subtle soft leeway (~±2%) beyond hard mins/maxes."""

from __future__ import annotations

from dataclasses import dataclass

from loan_negotiation.models.loan_terms import BorrowerTerms, DealTerms, LenderTerms
from loan_negotiation.services.deal_scoring import score_for_borrower, score_for_lender

_RANGE_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("downpayment", "min_downpayment", "max_downpayment", ""),
    ("interest_rate_pct", "min_interest_rate_pct", "max_interest_rate_pct", "%"),
    ("loan_length_years", "min_loan_length_years", "max_loan_length_years", " years"),
    ("arrangement_fee", "min_arrangement_fee", "max_arrangement_fee", ""),
    ("cashback", "min_cashback", "max_cashback", ""),
    (
        "overpayment_allowance_pct",
        "min_overpayment_allowance_pct",
        "max_overpayment_allowance_pct",
        "%",
    ),
    ("erc_pct", "min_erc_pct", "max_erc_pct", ""),
)

# Soft bend = max(2% of scale, absolute floor). Floors matter when bound is £0 / 0%.
_SOFT_RELATIVE = 0.02
_SOFT_ABS_FLOOR: dict[str, float] = {
    "downpayment": 1_500.0,
    "interest_rate_pct": 0.10,
    "loan_length_years": 1.0,
    "arrangement_fee": 100.0,
    "cashback": 100.0,
    "overpayment_allowance_pct": 0.5,
    "erc_pct": 0.15,
}


@dataclass(frozen=True)
class LimitBreach:
    party: str
    field: str
    value: float
    bound: float
    side: str  # "min" | "max"
    unit: str

    @property
    def excess(self) -> float:
        if self.side == "min":
            return max(0.0, self.bound - self.value)
        return max(0.0, self.value - self.bound)

    def message(self, *, party_label: str | None = None) -> str:
        label = self.field.replace("_", " ")
        party = party_label or self.party
        if self.side == "min":
            if party_label:
                return (
                    f"{label.capitalize()} {self.value}{self.unit} is below "
                    f"{party} minimum {self.bound}{self.unit}."
                )
            return f"{label} {self.value} is below your minimum {self.bound}"
        if party_label:
            return (
                f"{label.capitalize()} {self.value}{self.unit} exceeds "
                f"{party} maximum {self.bound}{self.unit}."
            )
        return f"{label} {self.value} is above your maximum {self.bound}"


@dataclass(frozen=True)
class DealLimitValidation:
    blocking_issues: list[str]
    soft_pass_notes: list[str]


def soft_slack(field: str, bound: float, value: float) -> float:
    """Allowed excess past a hard bound — ~2% of scale, never zero when bound is 0."""
    floor = _SOFT_ABS_FLOOR.get(field, 0.0)
    scale = max(abs(bound), abs(value), 1.0)
    return max(floor, _SOFT_RELATIVE * scale)


def breach_is_soft(breach: LimitBreach) -> bool:
    return breach.excess <= soft_slack(breach.field, breach.bound, breach.value) + 1e-9


def collect_party_breaches(
    terms: BorrowerTerms | LenderTerms,
    deal: DealTerms,
    *,
    party: str,
) -> list[LimitBreach]:
    breaches: list[LimitBreach] = []
    for value_attr, min_attr, max_attr, unit in _RANGE_SPECS:
        value = float(getattr(deal, value_attr))
        low = getattr(terms, min_attr)
        high = getattr(terms, max_attr)
        if low is not None and value < float(low):
            breaches.append(
                LimitBreach(party, value_attr, value, float(low), "min", unit)
            )
        if high is not None and value > float(high):
            breaches.append(
                LimitBreach(party, value_attr, value, float(high), "max", unit)
            )
    return breaches


def collect_deal_breaches(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> list[LimitBreach]:
    return [
        *collect_party_breaches(borrower, deal, party="borrower"),
        *collect_party_breaches(lender, deal, party="lender"),
    ]


def split_soft_hard(
    breaches: list[LimitBreach],
) -> tuple[list[LimitBreach], list[LimitBreach]]:
    soft = [b for b in breaches if breach_is_soft(b)]
    hard = [b for b in breaches if not breach_is_soft(b)]
    return soft, hard


def describe_soft_passes(breaches: list[LimitBreach]) -> list[str]:
    notes: list[str] = []
    for b in breaches:
        label = b.field.replace("_", " ")
        notes.append(
            f"Subtle bend OK for {b.party} {label}: "
            f"{b.value:g} vs {b.side} {b.bound:g} "
            f"(within ~±2% / abs soft leeway)."
        )
    return notes


def party_within_hard_limits(
    terms: BorrowerTerms | LenderTerms,
    deal: DealTerms,
) -> tuple[bool, float, list[LimitBreach]]:
    """True when inside hard ranges or only subtle soft bends."""
    party = "borrower" if isinstance(terms, BorrowerTerms) else "lender"
    breaches = collect_party_breaches(terms, deal, party=party)
    soft, hard = split_soft_hard(breaches)
    breakdown = (
        score_for_borrower(deal, terms)
        if isinstance(terms, BorrowerTerms)
        else score_for_lender(deal, terms)
    )
    return (not hard), breakdown.total, soft + hard


# Back-compat alias.
party_package_compensates = party_within_hard_limits


def evaluate_deal_limits(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> DealLimitValidation:
    """Hard breaches block; subtle soft bends become advisory notes only."""
    breaches = collect_deal_breaches(deal, borrower, lender)
    if not breaches:
        return DealLimitValidation(blocking_issues=[], soft_pass_notes=[])
    soft, hard = split_soft_hard(breaches)
    return DealLimitValidation(
        blocking_issues=[b.message(party_label=b.party) for b in hard],
        soft_pass_notes=describe_soft_passes(soft),
    )


def clamp_deal_to_party_limits(
    deal: DealTerms,
    terms: BorrowerTerms | LenderTerms,
) -> tuple[DealTerms, list[str]]:
    """
    Hard-clamp every numeric field into this party's min/max (no soft bend).

    Used so borrower/lender JSON offers cannot leave their own walls mid-negotiation.
    If an 'accept' required clamping, consensus_reached is forced false.
    """
    updates: dict = {}
    notes: list[str] = []
    for value_attr, min_attr, max_attr, _unit in _RANGE_SPECS:
        value = float(getattr(deal, value_attr))
        low = getattr(terms, min_attr)
        high = getattr(terms, max_attr)
        new_val = value
        if low is not None and new_val < float(low):
            new_val = float(low)
            notes.append(f"{value_attr} raised to party min {new_val:g}")
        if high is not None and new_val > float(high):
            new_val = float(high)
            notes.append(f"{value_attr} lowered to party max {new_val:g}")
        if abs(new_val - value) > 1e-9:
            if value_attr == "loan_length_years":
                updates[value_attr] = int(round(new_val))
            else:
                updates[value_attr] = round(new_val, 2)

    if not updates:
        return deal.model_copy(), []

    if deal.consensus_reached:
        updates["consensus_reached"] = False
        notes.append("accept cleared — package was outside this party's walls")

    return deal.model_copy(update=updates), notes
