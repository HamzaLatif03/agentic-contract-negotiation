from dataclasses import dataclass

from loan_negotiation.models.loan_terms import DealTerms

_DEAL_COMPARE_FIELDS = (
    "downpayment",
    "interest_rate_pct",
    "loan_length_years",
    "rate_type",
    "initial_period_years",
    "arrangement_fee",
    "cashback",
    "overpayment_allowance_pct",
    "erc_pct",
    "repayment_type",
    "portable",
    "free_valuation",
    "free_legal",
)


@dataclass(frozen=True)
class LabeledOffer:
    speaker: str
    deal: DealTerms


def _numeric_close(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 1e-6
    return left == right


def deals_match(left: DealTerms, right: DealTerms) -> bool:
    return all(
        _numeric_close(getattr(left, name), getattr(right, name))
        for name in _DEAL_COMPARE_FIELDS
    )


def apply_acceptance_semantics(
    offer: DealTerms,
    other_last: DealTerms | None,
    text: str,
    *,
    accepting: bool,
) -> DealTerms:
    """Accept means copy the counterparty's latest package exactly.

    Models often say "accept" / set consensus_reached while still changing numbers.
    When an acceptance is declared and we know their last offer, lock to that package
    so termination and scoring see a real deal.
    """
    if other_last is None:
        return offer.model_copy(update={"consensus_reached": True}) if accepting else offer
    if accepting:
        return other_last.model_copy(update={"consensus_reached": True})
    if deals_match(offer, other_last):
        return offer.model_copy(update={"consensus_reached": offer.consensus_reached})
    return offer


def find_matching_latest_offers(offers: list[LabeledOffer]) -> DealTerms | None:
    """Matching packages alone are not consensus — require an explicit accept elsewhere."""
    return None


def resolve_consensus_deal(offers: list[LabeledOffer]) -> DealTerms | None:
    """First explicit acceptance of the other's package (echo-copy without accept is ignored)."""
    last_by_speaker: dict[str, DealTerms] = {}

    for item in offers:
        if item.deal.consensus_reached:
            other = "borrower" if item.speaker == "lender" else "lender"
            other_last = last_by_speaker.get(other)
            if other_last is not None and deals_match(item.deal, other_last):
                return item.deal.model_copy(update={"consensus_reached": True})
            if other_last is not None:
                # Acceptance with drifted numbers — honour the counterparty package.
                return other_last.model_copy(update={"consensus_reached": True})
        last_by_speaker[item.speaker] = item.deal

    return None
