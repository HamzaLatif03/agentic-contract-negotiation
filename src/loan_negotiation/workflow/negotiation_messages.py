import re

from autogen_agentchat.messages import BaseChatMessage

from loan_negotiation.workflow.deal_parser import (
    ACCEPT_PHRASES_RE,
    parse_offer_from_text,
    parse_offer_from_text_lenient,
)
from loan_negotiation.workflow.negotiation_state import deals_match

NEGOTIATOR_SOURCES = {"borrower_negotiator", "lender_negotiator"}

_TOOL_JSON_RE = re.compile(
    r'\{["\']summary["\'].*?\}\s*',
    re.DOTALL | re.IGNORECASE,
)
_PROSE_BEFORE_JSON_RE = re.compile(
    r"^(.*?)(?:```|\{)",
    re.DOTALL,
)


def negotiator_label(source: str) -> str:
    return "Lender" if source == "lender_negotiator" else "Borrower"


def _speaker_key(source: str) -> str:
    return "lender" if source == "lender_negotiator" else "borrower"


def structure_kind(value: int) -> str:
    return "fixed" if value <= 5 else "variable"


def _format_offer_line(label: str, deal) -> str:
    kind = structure_kind(deal.interest_structure)
    return (
        f"  {label}: £{deal.downpayment:,.0f} down | {deal.interest_rate_pct}% | "
        f"{deal.loan_length_years}yr | {kind}"
    )


def _format_deal_summary(deal) -> str:
    kind = structure_kind(deal.interest_structure)
    action = "Accepting" if deal.consensus_reached else "Offering"
    return (
        f"{action}: £{deal.downpayment:,.0f} down, {deal.interest_rate_pct}% rate, "
        f"{deal.loan_length_years} years, {kind}"
    )


def format_positions_table(
    lender_offer,
    borrower_offer,
) -> str:
    lines = ["Current positions:"]
    if lender_offer is not None:
        lines.append(_format_offer_line("Lender", lender_offer))
    else:
        lines.append("  Lender: —")
    if borrower_offer is not None:
        lines.append(_format_offer_line("Borrower", borrower_offer))
    else:
        lines.append("  Borrower: —")
    return "\n".join(lines)


class NegotiationTracker:
    """Track each party's latest offer for feed summaries."""

    def __init__(self) -> None:
        self._last: dict[str, object] = {}

    @property
    def lender_offer(self):
        return self._last.get("lender")

    @property
    def borrower_offer(self):
        return self._last.get("borrower")

    def update_from_raw(self, source: str, raw: str):
        speaker = _speaker_key(source)
        fallback = self._last.get(speaker)
        deal = parse_offer_from_text_lenient(raw, fallback=fallback)
        if deal is None:
            return None

        other = "borrower" if speaker == "lender" else "lender"
        other_last = self._last.get(other)
        if (
            not deal.consensus_reached
            and other_last is not None
            and deals_match(deal, other_last)
            and ACCEPT_PHRASES_RE.search(raw)
        ):
            deal = deal.model_copy(update={"consensus_reached": True})

        self._last[speaker] = deal
        return deal

    def format_for_display(self, source: str, raw: str) -> str | None:
        self.update_from_raw(source, raw)
        formatted = format_negotiator_message(raw)
        if not formatted:
            return None
        table = format_positions_table(self.lender_offer, self.borrower_offer)
        return f"{formatted}\n\n{table}"


def format_negotiator_message(text: str) -> str:
    """Turn raw agent output into a concise human-readable negotiation line."""
    stripped = text.strip()
    if not stripped:
        return stripped

    deal = parse_offer_from_text(stripped)
    prose_match = _PROSE_BEFORE_JSON_RE.match(stripped)
    prose = (prose_match.group(1).strip() if prose_match else "").strip()
    prose = _TOOL_JSON_RE.sub("", prose).strip()

    if deal is not None:
        summary = _format_deal_summary(deal)
        if prose and not prose.startswith("{") and len(prose) > 12:
            if prose.lower() in summary.lower():
                return summary
            return f"{prose}\n{summary}"
        return summary

    cleaned = _TOOL_JSON_RE.sub("", stripped).strip()
    if cleaned.startswith("{") and '"downpayment"' not in cleaned:
        return ""
    return cleaned


def extract_negotiator_text(
    message: BaseChatMessage,
    tracker: NegotiationTracker | None = None,
) -> str | None:
    """Pull displayable negotiation text from a chat message, if any."""
    if message.source not in NEGOTIATOR_SOURCES:
        return None
    if not hasattr(message, "to_text"):
        return None

    text = message.to_text().strip()
    if not text:
        return None

    if text in {"OK", "OK: all four values are within your limits."}:
        return None
    if text.startswith("PROBLEMS:") and "downpayment" not in text.lower():
        return None

    if tracker is not None:
        formatted = tracker.format_for_display(message.source, text)
    else:
        formatted = format_negotiator_message(text)

    if not formatted:
        return None

    lower = formatted.lower()
    if (
        "goodbye" in lower
        and parse_offer_from_text(text) is None
        and len(formatted) < 80
    ):
        return None
    if lower.startswith("no offer") and parse_offer_from_text(text) is None:
        return None

    return formatted


def transcript_line(source: str, text: str) -> str:
    return f"{negotiator_label(source)}:\n{text}"
