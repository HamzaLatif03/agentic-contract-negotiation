from dataclasses import dataclass

from loan_negotiation.models.loan_terms import DealTerms


@dataclass(frozen=True)
class LabeledOffer:
    speaker: str
    deal: DealTerms


def deals_match(left: DealTerms, right: DealTerms) -> bool:
    return (
        left.downpayment == right.downpayment
        and left.interest_rate_pct == right.interest_rate_pct
        and left.loan_length_years == right.loan_length_years
        and left.interest_structure == right.interest_structure
    )


def find_matching_latest_offers(offers: list[LabeledOffer]) -> DealTerms | None:
    """Both parties' most recent offers are identical — treat as agreed."""
    last: dict[str, DealTerms] = {}
    for item in offers:
        last[item.speaker] = item.deal

    lender = last.get("lender")
    borrower = last.get("borrower")
    if lender is None or borrower is None:
        return None
    if not deals_match(lender, borrower):
        return None
    return lender.model_copy(update={"consensus_reached": True})


def resolve_consensus_deal(offers: list[LabeledOffer]) -> DealTerms | None:
    """First explicit acceptance, otherwise latest matching offers from both sides."""
    last_by_speaker: dict[str, DealTerms] = {}
    last_consensus: dict[str, DealTerms] = {}

    for item in offers:
        if item.deal.consensus_reached:
            other = "borrower" if item.speaker == "lender" else "lender"
            other_last = last_by_speaker.get(other)
            if other_last is not None and deals_match(item.deal, other_last):
                return item.deal.model_copy(update={"consensus_reached": True})

            last_consensus[item.speaker] = item.deal
            other_consensus = last_consensus.get(other)
            if other_consensus is not None and deals_match(item.deal, other_consensus):
                return item.deal.model_copy(update={"consensus_reached": True})

        last_by_speaker[item.speaker] = item.deal

    return find_matching_latest_offers(offers)
