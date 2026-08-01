import json
import re

from pydantic import ValidationError

from loan_negotiation.models.loan_terms import (
    BorrowerTerms,
    DealTerms,
    LenderTerms,
    normalize_rate_type,
)
from loan_negotiation.services.limit_compensation import (
    collect_party_breaches,
    evaluate_deal_limits,
    split_soft_hard,
)
from loan_negotiation.workflow.negotiation_state import (
    LabeledOffer,
    apply_acceptance_semantics,
    deals_match,
    resolve_consensus_deal,
)

ACCEPT_PHRASES_RE = re.compile(
    r"(?i)\b("
    r"i accept|we accept|accepted|accepting|"
    r"deal accepted|accept the (offer|deal|terms)|let'?s accept|"
    r"consensus (has been )?reached|stop here"
    r")\b"
)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)
_SPEAKER_RE = re.compile(r"^(Lender|Borrower):\s*", re.MULTILINE)
_XML_TOOL_CALL_RE = re.compile(r"<tool_call\b[^>]*>.*?</tool_call>", re.DOTALL | re.IGNORECASE)
_XML_TOOL_PARAM_RE = re.compile(
    r"<parameter=([a-zA-Z0-9_]+)>\s*([^<]*?)\s*</parameter>",
    re.IGNORECASE,
)
_XML_FUNCTION_RE = re.compile(r"<function=([a-zA-Z0-9_]+)>", re.IGNORECASE)

__all__ = [
    "ACCEPT_PHRASES_RE",
    "extract_final_deal",
    "format_deal",
    "parse_labeled_offers",
    "parse_offer_from_text",
    "parse_offer_from_text_lenient",
    "problems_against_party_limits",
    "prose_claims_acceptance",
    "validate_deal_against_terms",
]


def prose_claims_acceptance(text: str) -> bool:
    """Match accept language in prose only — ignore JSON keys like consensus_reached."""
    prose = _JSON_BLOCK_RE.sub(" ", text)
    prose = _JSON_OBJECT_RE.sub(" ", prose)
    prose = _XML_TOOL_CALL_RE.sub(" ", prose)
    return bool(ACCEPT_PHRASES_RE.search(prose))


def problems_against_party_limits(
    terms: BorrowerTerms | LenderTerms,
    deal: DealTerms,
    *,
    party_label: str | None = None,
) -> list[str]:
    """Return hard (beyond soft leeway) violations for one party (empty = OK)."""
    party = party_label or ("borrower" if isinstance(terms, BorrowerTerms) else "lender")
    _soft, hard = split_soft_hard(collect_party_breaches(terms, deal, party=party))
    return [breach.message(party_label=party_label) for breach in hard]


def validate_deal_against_terms(
    deal: DealTerms,
    borrower: BorrowerTerms,
    lender: LenderTerms,
) -> list[str]:
    """Blocking hard-limit issues beyond subtle soft leeway (empty = OK to approve)."""
    return evaluate_deal_limits(deal, borrower, lender).blocking_issues


def format_deal(deal: DealTerms) -> str:
    return deal.model_dump_json(indent=2)


def _normalize_payload(data: dict, fallback: DealTerms | None = None) -> dict:
    normalized = dict(data)
    # Legacy aliases → current UK mortgage fields.
    if "deposit" in normalized and "downpayment" not in normalized:
        normalized["downpayment"] = normalized.pop("deposit")
    if "interest_structure" in normalized and "rate_type" not in normalized:
        try:
            normalized["rate_type"] = normalize_rate_type(normalized.pop("interest_structure"))
        except (TypeError, ValueError):
            normalized.pop("interest_structure", None)
    for legacy_key in ("loan_type", "interest_type"):
        if legacy_key in normalized and "rate_type" not in normalized:
            try:
                normalized["rate_type"] = normalize_rate_type(str(normalized.pop(legacy_key)))
            except ValueError:
                normalized.pop(legacy_key, None)

    if fallback is not None:
        for field in DealTerms.model_fields:
            if field == "consensus_reached":
                continue
            if field not in normalized:
                normalized[field] = getattr(fallback, field)
    return normalized


def _coerce_deal(
    data: dict,
    fallback: DealTerms | None = None,
    *,
    require_structure: bool,
) -> DealTerms | None:
    if "name" in data and "downpayment" not in data and "deposit" not in data:
        return None
    if not (
        ("downpayment" in data or "deposit" in data)
        and "interest_rate_pct" in data
        and "loan_length_years" in data
    ):
        return None
    normalized = _normalize_payload(data, fallback)
    if require_structure and "rate_type" not in normalized:
        return None
    try:
        return DealTerms.model_validate(normalized)
    except (ValidationError, ValueError, TypeError):
        return None


def _json_candidates(text: str) -> list[str]:
    candidates = [m.group(1) for m in _JSON_BLOCK_RE.finditer(text)]
    if candidates:
        return candidates
    return [
        m.group(0)
        for m in _JSON_OBJECT_RE.finditer(text)
        if "downpayment" in m.group(0) and "interest_rate_pct" in m.group(0)
    ]


def _parse_xml_tool_offer(text: str, fallback: DealTerms | None = None) -> DealTerms | None:
    blocks = _XML_TOOL_CALL_RE.findall(text)
    if not blocks and "<parameter=" in text.lower():
        blocks = [text]
    for block in reversed(blocks):
        fn = _XML_FUNCTION_RE.search(block)
        if fn and fn.group(1).lower() not in {"check_offer", "offer", "counter_offer"}:
            continue
        params = {
            m.group(1).lower(): m.group(2).strip() for m in _XML_TOOL_PARAM_RE.finditer(block)
        }
        if not {"downpayment", "interest_rate_pct", "loan_length_years"} <= params.keys():
            continue
        try:
            data = {
                "downpayment": float(params["downpayment"].replace(",", "")),
                "interest_rate_pct": float(params["interest_rate_pct"].replace("%", "")),
                "loan_length_years": int(float(params["loan_length_years"])),
                "consensus_reached": False,
            }
            for key in (
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
                "interest_structure",
                "interest_type",
            ):
                if key in params:
                    data[key] = params[key]
        except (TypeError, ValueError):
            continue
        deal = _coerce_deal(data, fallback, require_structure=False)
        if deal is not None:
            return deal
    return None


def parse_offer_from_text(
    text: str,
    fallback: DealTerms | None = None,
    *,
    require_structure: bool = True,
) -> DealTerms | None:
    for raw in reversed(_json_candidates(text)):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            deal = _coerce_deal(data, fallback, require_structure=require_structure)
            if deal is not None:
                return deal
    return _parse_xml_tool_offer(text, fallback)


def parse_offer_from_text_lenient(
    text: str,
    fallback: DealTerms | None = None,
) -> DealTerms | None:
    return parse_offer_from_text(text, fallback, require_structure=False)


def parse_labeled_offers(transcript: str) -> list[LabeledOffer]:
    offers: list[LabeledOffer] = []
    parts = _SPEAKER_RE.split(transcript)
    if len(parts) < 2:
        return offers

    last_complete: dict[str, DealTerms] = {}
    index = 1
    while index + 1 < len(parts):
        speaker = parts[index].lower()
        body = parts[index + 1]
        other = "borrower" if speaker == "lender" else "lender"
        offer = parse_offer_from_text_lenient(body, fallback=last_complete.get(speaker))
        other_last = last_complete.get(other)
        accepting = prose_claims_acceptance(body)
        if offer is None and accepting and other_last is not None:
            offer = other_last.model_copy(update={"consensus_reached": True})
        if offer is not None:
            accepting = accepting or offer.consensus_reached
            offer = apply_acceptance_semantics(
                offer, other_last, body, accepting=accepting
            )
            last_complete[speaker] = offer
            offers.append(LabeledOffer(speaker=speaker, deal=offer))
        index += 2
    return offers


def extract_final_deal(
    transcript: str,
    borrower: BorrowerTerms | None = None,
    lender: LenderTerms | None = None,
) -> DealTerms | None:
    """Return the agreed package when possible.

    Prefer an explicit acceptance even if that package sits outside hard limits —
    the orchestrator repairs or renegotiates. Echo-copy without accept is not consensus.
    Only fall back to "latest valid non-consensus offer" when there was no agreement.
    """
    labeled = parse_labeled_offers(transcript)
    resolved = resolve_consensus_deal(labeled)
    if resolved is not None:
        return resolved

    parsed = [item.deal for item in labeled]
    if not parsed:
        offer = parse_offer_from_text(transcript)
        if offer is None:
            return None
        parsed = [offer]

    # No consensus — prefer the latest offer that already clears limits when known.
    if borrower is not None and lender is not None:
        for offer in reversed(parsed):
            if not validate_deal_against_terms(offer, borrower, lender):
                return offer

    return parsed[-1]
