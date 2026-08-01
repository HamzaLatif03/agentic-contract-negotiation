import re

from autogen_agentchat.messages import BaseChatMessage

from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.workflow.deal_parser import (
    parse_offer_from_text,
    parse_offer_from_text_lenient,
    prose_claims_acceptance,
)
from loan_negotiation.workflow.negotiation_state import apply_acceptance_semantics, deals_match

NEGOTIATOR_SOURCES = {"borrower_negotiator", "lender_negotiator"}

_TOOL_JSON_RE = re.compile(
    r'\{["\']summary["\'].*?\}\s*',
    re.DOTALL | re.IGNORECASE,
)
_XML_TOOL_CALL_RE = re.compile(r"<tool_call\b[^>]*>.*?</tool_call>", re.DOTALL | re.IGNORECASE)
_PROSE_BEFORE_JSON_RE = re.compile(
    r"^(.*?)(?:```|\{|<tool_call\b)",
    re.DOTALL | re.IGNORECASE,
)
_REASONING_PREFIX_RE = re.compile(r"(?i)^\s*reasoning\s*:\s*")


def negotiator_label(source: str) -> str:
    return "Lender" if source == "lender_negotiator" else "Borrower"


def _speaker_key(source: str) -> str:
    return "lender" if source == "lender_negotiator" else "borrower"


def format_deal_line(deal: DealTerms) -> str:
    extras = []
    if deal.arrangement_fee:
        extras.append(f"fee £{deal.arrangement_fee:,.0f}")
    if deal.cashback:
        extras.append(f"cashback £{deal.cashback:,.0f}")
    extras.append(f"overpay {deal.overpayment_allowance_pct:g}%")
    if deal.erc_pct:
        extras.append(f"ERC {deal.erc_pct:g}%")
    if deal.portable:
        extras.append("portable")
    if deal.free_valuation:
        extras.append("free val")
    if deal.free_legal:
        extras.append("free legal")
    extra = (" | " + " | ".join(extras)) if extras else ""
    return (
        f"£{deal.downpayment:,.0f} deposit | {deal.interest_rate_pct}% {deal.rate_type} "
        f"({deal.initial_period_years}yr deal) | {deal.loan_length_years}yr term | "
        f"{deal.repayment_type.replace('_', ' ')}{extra}"
    )


def _format_offer_line(label: str, deal: DealTerms) -> str:
    return f"  {label}: {format_deal_line(deal)}"


def _format_deal_summary(deal: DealTerms) -> str:
    action = "Accepting" if deal.consensus_reached else "Offering"
    return f"{action}: {format_deal_line(deal)}"


def format_positions_table(lender_offer, borrower_offer) -> str:
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


def _fmt_money(value: float) -> str:
    return f"£{value:,.0f}"


def describe_offer_changes(
    current: DealTerms,
    previous: DealTerms | None,
    *,
    counterpart: DealTerms | None = None,
) -> str:
    """Human-readable justification of what moved (fallback when model omits prose)."""
    if current.consensus_reached:
        return "Accepting the other party's latest package as offered."

    baseline = counterpart if counterpart is not None else previous
    if baseline is None:
        return (
            f"Opening with {format_deal_line(current)} as the starting package "
            "to negotiate from."
        )

    if previous is not None and deals_match(current, previous) and counterpart is not None:
        return (
            "Holding our previous package; waiting for movement on the remaining gaps "
            f"versus their latest offer ({format_deal_line(counterpart)})."
        )

    changes: list[str] = []
    specs: list[tuple[str, str, object, object]] = [
        ("deposit", "£", current.downpayment, baseline.downpayment),
        ("rate", "%", current.interest_rate_pct, baseline.interest_rate_pct),
        ("term", "yr", current.loan_length_years, baseline.loan_length_years),
        ("fee", "£", current.arrangement_fee, baseline.arrangement_fee),
        ("cashback", "£", current.cashback, baseline.cashback),
        ("overpay", "%", current.overpayment_allowance_pct, baseline.overpayment_allowance_pct),
        ("ERC", "%", current.erc_pct, baseline.erc_pct),
    ]
    for label, unit, new, old in specs:
        if isinstance(new, (int, float)) and isinstance(old, (int, float)):
            if abs(float(new) - float(old)) < 1e-9:
                continue
            if unit == "£":
                changes.append(f"{label} {_fmt_money(float(old))} → {_fmt_money(float(new))}")
            elif unit == "%":
                changes.append(f"{label} {float(old):g}% → {float(new):g}%")
            else:
                changes.append(f"{label} {old}{unit} → {new}{unit}")

    if current.rate_type != baseline.rate_type:
        changes.append(f"rate type {baseline.rate_type} → {current.rate_type}")
    if current.initial_period_years != baseline.initial_period_years:
        changes.append(
            f"deal period {baseline.initial_period_years}yr → {current.initial_period_years}yr"
        )
    if current.repayment_type != baseline.repayment_type:
        changes.append(f"repayment {baseline.repayment_type} → {current.repayment_type}")
    for feat in ("portable", "free_valuation", "free_legal"):
        new_v = bool(getattr(current, feat))
        old_v = bool(getattr(baseline, feat))
        if new_v != old_v:
            nice = feat.replace("_", " ")
            changes.append(f"{nice} {'on' if new_v else 'off'} (was {'on' if old_v else 'off'})")

    if not changes:
        return "Countering with an adjusted package to keep negotiation moving."
    focus = "; ".join(changes[:4])
    if len(changes) > 4:
        focus += f"; +{len(changes) - 4} more"
    ref = "their latest offer" if counterpart is not None else "our previous offer"
    return f"Adjusting versus {ref}: {focus}."


def extract_reasoning_prose(text: str) -> str:
    prose_match = _PROSE_BEFORE_JSON_RE.match(text.strip())
    prose = (prose_match.group(1).strip() if prose_match else "").strip()
    prose = _TOOL_JSON_RE.sub("", prose).strip()
    prose = _XML_TOOL_CALL_RE.sub("", prose).strip()
    if not prose or prose.startswith("{") or prose.startswith("<"):
        return ""
    return _REASONING_PREFIX_RE.sub("", prose).strip()


def format_positions_with_justification(
    *,
    deal: DealTerms,
    reasoning: str,
    lender_offer: DealTerms | None,
    borrower_offer: DealTerms | None,
) -> str:
    reason_line = _REASONING_PREFIX_RE.sub("", (reasoning or "").strip())
    if not reason_line:
        reason_line = "No justification provided."
    return (
        f"{reason_line}\n{_format_deal_summary(deal)}\n\n"
        f"{format_positions_table(lender_offer, borrower_offer)}"
    )


class NegotiationTracker:
    """Track each party's latest offer for feed summaries."""

    def __init__(self) -> None:
        self._last: dict[str, DealTerms] = {}

    @property
    def lender_offer(self) -> DealTerms | None:
        return self._last.get("lender")

    @property
    def borrower_offer(self) -> DealTerms | None:
        return self._last.get("borrower")

    def update_from_raw(self, source: str, raw: str) -> DealTerms | None:
        speaker = _speaker_key(source)
        other = "borrower" if speaker == "lender" else "lender"
        other_last = self._last.get(other)
        own_previous = self._last.get(speaker)
        deal = parse_offer_from_text_lenient(raw, fallback=own_previous)
        accepting = prose_claims_acceptance(raw)
        if deal is None:
            if accepting and other_last is not None:
                deal = other_last.model_copy(update={"consensus_reached": True})
            else:
                return None
        else:
            accepting = accepting or deal.consensus_reached
            deal = apply_acceptance_semantics(
                deal, other_last, raw, accepting=accepting
            )

        self._last[speaker] = deal
        return deal

    def format_for_display(self, source: str, raw: str) -> str | None:
        speaker = _speaker_key(source)
        other = "borrower" if speaker == "lender" else "lender"
        own_previous = self._last.get(speaker)
        other_last = self._last.get(other)

        deal = self.update_from_raw(source, raw)
        if deal is None:
            # Fall back to prose-only formatting when no deal parsed.
            formatted = format_negotiator_message(raw)
            return formatted or None

        reasoning = extract_reasoning_prose(raw)
        if len(reasoning) < 12:
            reasoning = describe_offer_changes(
                deal,
                own_previous,
                counterpart=other_last,
            )

        return format_positions_with_justification(
            deal=deal,
            reasoning=reasoning,
            lender_offer=self.lender_offer,
            borrower_offer=self.borrower_offer,
        )


def format_negotiator_message(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped

    deal = parse_offer_from_text(stripped)
    reasoning = extract_reasoning_prose(stripped)

    if deal is not None:
        summary = _format_deal_summary(deal)
        if reasoning:
            prose = _REASONING_PREFIX_RE.sub("", reasoning).strip()
            if prose.lower() in summary.lower():
                return f"{describe_offer_changes(deal, None)}\n{summary}"
            return f"{prose}\n{summary}"
        return f"{describe_offer_changes(deal, None)}\n{summary}"

    cleaned = _TOOL_JSON_RE.sub("", stripped).strip()
    cleaned = _XML_TOOL_CALL_RE.sub("", cleaned).strip()
    if cleaned.startswith("{") and '"downpayment"' not in cleaned:
        return ""
    if cleaned.startswith("<") or not cleaned:
        return ""
    return cleaned


def extract_negotiator_text(
    message: BaseChatMessage,
    tracker: NegotiationTracker | None = None,
) -> str | None:
    if message.source not in NEGOTIATOR_SOURCES:
        return None
    if not hasattr(message, "to_text"):
        return None

    text = message.to_text().strip()
    if not text:
        return None

    if text.startswith("OK:") or text == "OK":
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
    if "goodbye" in lower and parse_offer_from_text(text) is None and len(formatted) < 80:
        return None
    if lower.startswith("no offer") and parse_offer_from_text(text) is None:
        return None

    return formatted


def transcript_line(source: str, text: str) -> str:
    return f"{negotiator_label(source)}:\n{text}"
