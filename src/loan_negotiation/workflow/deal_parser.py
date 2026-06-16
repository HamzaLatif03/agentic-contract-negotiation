import json
import re

from pydantic import ValidationError

from loan_negotiation.models.loan_terms import (
    BorrowerTerms,
    DealTerms,
    LenderTerms,
    clamp_interest_structure,
    legacy_interest_type_to_structure,
)
from loan_negotiation.workflow.negotiation_state import (
    LabeledOffer,
    deals_match,
    resolve_consensus_deal,
)

ACCEPT_PHRASES_RE = re.compile(
    r"\b(accept|accepted|agree|agreed|confirm|confirmed|complete|done)\b",
    re.IGNORECASE,
)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)
_SPEAKER_RE = re.compile(r"^(Lender|Borrower):\s*", re.MULTILINE)
def _has_structure_field(data: dict) -> bool:
    return "interest_structure" in data or "interest_type" in data


def _is_deal_payload(data: dict) -> bool:
    if "name" in data and "downpayment" not in data:
        return False
    return (
        "downpayment" in data
        and "interest_rate_pct" in data
        and "loan_length_years" in data
        and _has_structure_field(data)
    )


def _normalize_payload(data: dict, fallback: DealTerms | None = None) -> dict:
    normalized = dict(data)
    if "loan_type" in normalized and "interest_structure" not in normalized:
        legacy = legacy_interest_type_to_structure(str(normalized.pop("loan_type")))
        if legacy is not None:
            normalized["interest_structure"] = legacy
    if "interest_type" in normalized and "interest_structure" not in normalized:
        legacy = legacy_interest_type_to_structure(str(normalized.pop("interest_type")))
        if legacy is not None:
            normalized["interest_structure"] = legacy
    if "interest_structure" not in normalized and fallback is not None:
        normalized["interest_structure"] = fallback.interest_structure
    if "interest_structure" in normalized:
        normalized["interest_structure"] = clamp_interest_structure(
            int(normalized["interest_structure"])
        )
    return normalized


def _coerce_deal(data: dict, fallback: DealTerms | None = None) -> DealTerms | None:
    normalized = _normalize_payload(data, fallback)
    if not _is_deal_payload(normalized):
        return None
    try:
        return DealTerms.model_validate(normalized)
    except (ValidationError, ValueError, TypeError):
        return None


def parse_offer_from_text(text: str, fallback: DealTerms | None = None) -> DealTerms | None:
    candidates: list[str] = []

    for match in _JSON_BLOCK_RE.finditer(text):
        candidates.append(match.group(1))

    if not candidates:
        for match in _JSON_OBJECT_RE.finditer(text):
            snippet = match.group(0)
            if "downpayment" in snippet and "interest_rate_pct" in snippet:
                candidates.append(snippet)

    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        deal = _coerce_deal(data, fallback)
        if deal is not None:
            return deal

    return None


def _has_core_fields(data: dict) -> bool:
    return (
        "downpayment" in data
        and "interest_rate_pct" in data
        and "loan_length_years" in data
    )


def parse_offer_from_text_lenient(
    text: str,
    fallback: DealTerms | None = None,
) -> DealTerms | None:
    """Parse an offer, filling interest_structure from fallback when omitted."""
    candidates: list[str] = []

    for match in _JSON_BLOCK_RE.finditer(text):
        candidates.append(match.group(1))

    if not candidates:
        for match in _JSON_OBJECT_RE.finditer(text):
            snippet = match.group(0)
            if "downpayment" in snippet and "interest_rate_pct" in snippet:
                candidates.append(snippet)

    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or not _has_core_fields(data):
            continue
        if "name" in data and "downpayment" not in data:
            continue
        deal = _coerce_deal(data, fallback)
        if deal is not None:
            return deal

    return None


def parse_labeled_offers(transcript: str) -> list[LabeledOffer]:
    offers: list[LabeledOffer] = []
    parts = _SPEAKER_RE.split(transcript)
    if len(parts) < 2:
        return offers

    last_complete: dict[str, DealTerms] = {}

    index = 1
    while index + 1 < len(parts):
        speaker = parts[index].strip().lower()
        body = parts[index + 1]
        other_speaker = "borrower" if speaker == "lender" else "lender"
        offer = parse_offer_from_text_lenient(body, fallback=last_complete.get(speaker))
        if offer is not None:
            other_last = last_complete.get(other_speaker)
            if (
                not offer.consensus_reached
                and other_last is not None
                and deals_match(offer, other_last)
                and ACCEPT_PHRASES_RE.search(body)
            ):
                offer = offer.model_copy(update={"consensus_reached": True})
            last_complete[speaker] = offer
            offers.append(LabeledOffer(speaker=speaker, deal=offer))
        index += 2

    return offers


def extract_final_deal(
    transcript: str,
    borrower: BorrowerTerms | None = None,
    lender: LenderTerms | None = None,
) -> DealTerms | None:
    labeled = parse_labeled_offers(transcript)
    resolved = resolve_consensus_deal(labeled)
    if resolved is not None:
        if borrower is not None and lender is not None:
            if not validate_deal_against_terms(resolved, borrower, lender):
                return resolved
        else:
            return resolved

    parsed = [item.deal for item in labeled]
    if not parsed:
        offer = parse_offer_from_text(transcript)
        if offer is None:
            return None
        parsed = [offer]

    consensus_offers = [offer for offer in parsed if offer.consensus_reached]
    candidates = list(reversed(consensus_offers or parsed))

    if borrower is not None and lender is not None:
        for offer in candidates:
            if not validate_deal_against_terms(offer, borrower, lender):
                return offer
        for offer in reversed(parsed):
            if not validate_deal_against_terms(offer, borrower, lender):
                return offer

    return candidates[0]


def format_deal(deal: DealTerms) -> str:
    return deal.model_dump_json(indent=2)


def validate_deal_against_terms(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> list[str]:
    reasons: list[str] = []

    if borrower.min_downpayment is not None and deal.downpayment < borrower.min_downpayment:
        reasons.append(
            f"Downpayment {deal.downpayment} is below borrower minimum {borrower.min_downpayment}."
        )
    if borrower.max_downpayment is not None and deal.downpayment > borrower.max_downpayment:
        reasons.append(
            f"Downpayment {deal.downpayment} exceeds borrower maximum {borrower.max_downpayment}."
        )
    if lender.min_downpayment is not None and deal.downpayment < lender.min_downpayment:
        reasons.append(
            f"Downpayment {deal.downpayment} is below lender minimum {lender.min_downpayment}."
        )
    if lender.max_downpayment is not None and deal.downpayment > lender.max_downpayment:
        reasons.append(
            f"Downpayment {deal.downpayment} exceeds lender maximum {lender.max_downpayment}."
        )

    if (
        borrower.min_interest_rate_pct is not None
        and deal.interest_rate_pct < borrower.min_interest_rate_pct
    ):
        reasons.append(
            f"Interest rate {deal.interest_rate_pct}% is below borrower minimum "
            f"{borrower.min_interest_rate_pct}%."
        )
    if (
        borrower.max_interest_rate_pct is not None
        and deal.interest_rate_pct > borrower.max_interest_rate_pct
    ):
        reasons.append(
            f"Interest rate {deal.interest_rate_pct}% exceeds borrower maximum "
            f"{borrower.max_interest_rate_pct}%."
        )
    if (
        lender.min_interest_rate_pct is not None
        and deal.interest_rate_pct < lender.min_interest_rate_pct
    ):
        reasons.append(
            f"Interest rate {deal.interest_rate_pct}% is below lender minimum "
            f"{lender.min_interest_rate_pct}%."
        )
    if (
        lender.max_interest_rate_pct is not None
        and deal.interest_rate_pct > lender.max_interest_rate_pct
    ):
        reasons.append(
            f"Interest rate {deal.interest_rate_pct}% exceeds lender maximum "
            f"{lender.max_interest_rate_pct}%."
        )

    if (
        borrower.min_loan_length_years is not None
        and deal.loan_length_years < borrower.min_loan_length_years
    ):
        reasons.append(
            f"Loan length {deal.loan_length_years} years is below borrower minimum "
            f"{borrower.min_loan_length_years} years."
        )
    if (
        borrower.max_loan_length_years is not None
        and deal.loan_length_years > borrower.max_loan_length_years
    ):
        reasons.append(
            f"Loan length {deal.loan_length_years} years exceeds borrower maximum "
            f"{borrower.max_loan_length_years} years."
        )
    if (
        lender.min_loan_length_years is not None
        and deal.loan_length_years < lender.min_loan_length_years
    ):
        reasons.append(
            f"Loan length {deal.loan_length_years} years is below lender minimum "
            f"{lender.min_loan_length_years} years."
        )
    if (
        lender.max_loan_length_years is not None
        and deal.loan_length_years > lender.max_loan_length_years
    ):
        reasons.append(
            f"Loan length {deal.loan_length_years} years exceeds lender maximum "
            f"{lender.max_loan_length_years} years."
        )

    return reasons
