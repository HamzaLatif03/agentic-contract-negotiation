"""Rewrite negotiator messages so JSON offers stay inside that party's private walls."""

from __future__ import annotations

import re

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.services.limit_compensation import clamp_deal_to_party_limits
from loan_negotiation.workflow.deal_parser import (
    format_deal,
    parse_offer_from_text,
    parse_offer_from_text_lenient,
)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(
    r"\{[^{}]*\"downpayment\"[^{}]*\"interest_rate_pct\"[^{}]*\}",
    re.DOTALL,
)


def enforce_party_walls_in_message(
    text: str,
    terms: BorrowerTerms | LenderTerms,
) -> tuple[str, list[str]]:
    """
    If the message contains an offer outside this party's min/max, rewrite the JSON
    so every numeric field is clamped into their walls.
    """
    deal = parse_offer_from_text(text) or parse_offer_from_text_lenient(text)
    if deal is None:
        return text, []

    clamped, notes = clamp_deal_to_party_limits(deal, terms)
    if not notes:
        return text, []

    replacement = format_deal(clamped)
    blocks = list(_JSON_BLOCK_RE.finditer(text))
    if blocks:
        last = blocks[-1]
        return text[: last.start()] + f"```json\n{replacement}\n```" + text[last.end() :], notes

    objects = [
        m
        for m in _JSON_OBJECT_RE.finditer(text)
        if "downpayment" in m.group(0) and "interest_rate_pct" in m.group(0)
    ]
    if objects:
        last = objects[-1]
        return text[: last.start()] + replacement + text[last.end() :], notes

    # No recognizable JSON block — append the corrected offer.
    return f"{text.rstrip()}\n\n```json\n{replacement}\n```", notes
