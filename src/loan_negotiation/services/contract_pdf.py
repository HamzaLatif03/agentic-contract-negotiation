"""Extract text from lender offer PDFs and map it to DealTerms."""

from __future__ import annotations

import re
from io import BytesIO

from pypdf import PdfReader

from loan_negotiation.models.loan_terms import (
    DealTerms,
    clamp_interest_structure,
    legacy_interest_type_to_structure,
)
from loan_negotiation.workflow.deal_parser import parse_offer_from_text

_MONEY_RE = re.compile(
    r"(?:down\s*-?\s*payment|deposit|equity\s+contribution)"
    r"[^\d£$]{0,40}(?:£|\$|GBP\s*)?([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_MONEY_FALLBACK_RE = re.compile(r"(?:£|GBP\s*)([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_RATE_RE = re.compile(
    r"(?:interest\s+rate|rate\s+of\s+interest|apr)"
    r"[^\d%]{0,40}([\d]+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
_RATE_FALLBACK_RE = re.compile(r"([\d]+(?:\.\d+)?)\s*%\s*(?:p\.?a\.?|per\s+annum|interest)?", re.IGNORECASE)
_TERM_RE = re.compile(
    r"(?:loan\s+(?:term|length|duration)|term|tenure|repayment\s+period)"
    r"[^\d]{0,40}([\d]+)\s*(?:years?|yrs?)",
    re.IGNORECASE,
)
_TERM_FALLBACK_RE = re.compile(r"([\d]+)\s*(?:years?|yrs?)\s+(?:term|loan|mortgage)", re.IGNORECASE)
_FIXED_RE = re.compile(r"\b(fixed(?:[\s-]?rate)?)\b", re.IGNORECASE)
_VARIABLE_RE = re.compile(
    r"\b(variable(?:[\s-]?rate)?|floating|tracker|adjustable)\b",
    re.IGNORECASE,
)

OFFER_EXTRACTION_PROMPT = """\
You extract a lender's opening loan offer from contract or offer-letter text.

Read the full text carefully. Values may be written in tables, bullet lists, or prose
(e.g. "seventy thousand pounds", "5.25 percent", "twenty-five year term").

Return ONLY one fenced JSON block with these fields:
- downpayment: number in pounds (absolute amount, not percent)
- interest_rate_pct: number (e.g. 5.0)
- loan_length_years: whole number
- interest_structure: integer 1-10 where 1=fully fixed and 10=fully variable
- consensus_reached: false

Rules:
- If fixed rate, use interest_structure 1. If variable/tracker/floating, use 10.
- If mixed or unclear, use 5.
- Prefer the opening/proposed offer amounts, not later repayment schedules or examples.
- Do not invent values that are not supported by the text.
"""


class ContractExtractionError(ValueError):
    """Raised when a PDF cannot be turned into a usable opening offer."""


def extract_text_from_pdf(data: bytes) -> str:
    if not data:
        raise ContractExtractionError("Uploaded PDF is empty.")
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - pypdf raises varied errors
        raise ContractExtractionError(f"Could not read PDF: {exc}") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")
    text = "\n".join(pages).strip()
    if not text:
        raise ContractExtractionError(
            "No extractable text found in the PDF. Use a text-based (not scanned) offer."
        )
    return text


def _parse_money(raw: str) -> float:
    return float(raw.replace(",", ""))


def _first_float(patterns: list[re.Pattern[str]], text: str) -> float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return _parse_money(match.group(1))
    return None


def _first_int(patterns: list[re.Pattern[str]], text: str) -> int | None:
    value = _first_float(patterns, text)
    return int(value) if value is not None else None


def _infer_structure(text: str) -> int:
    has_fixed = bool(_FIXED_RE.search(text))
    has_variable = bool(_VARIABLE_RE.search(text))
    if has_fixed and not has_variable:
        return 1
    if has_variable and not has_fixed:
        return 10
    if has_fixed and has_variable:
        return 5
    legacy = None
    for token in ("fixed", "variable", "tracker", "floating"):
        if re.search(rf"\b{token}\b", text, re.IGNORECASE):
            legacy = legacy_interest_type_to_structure(
                "fixed" if token == "fixed" else "variable"
            )
            if legacy is not None:
                return legacy
    return 5


def extract_offer_heuristically(text: str) -> DealTerms | None:
    """Rule-based extraction for typical mock lender offer wording."""
    from_json = parse_offer_from_text(text)
    if from_json is not None:
        return from_json.model_copy(update={"consensus_reached": False})

    downpayment = _first_float([_MONEY_RE, _MONEY_FALLBACK_RE], text)
    rate = _first_float([_RATE_RE, _RATE_FALLBACK_RE], text)
    years = _first_int([_TERM_RE, _TERM_FALLBACK_RE], text)
    if downpayment is None or rate is None or years is None:
        return None

    return DealTerms(
        downpayment=downpayment,
        interest_rate_pct=rate,
        loan_length_years=years,
        interest_structure=clamp_interest_structure(_infer_structure(text)),
        consensus_reached=False,
    )


async def extract_offer_with_llm(text: str) -> DealTerms | None:
    """Use an extraction agent to read offer terms from contract text."""
    from loan_negotiation.agents.factory import create_assistant_agent
    from loan_negotiation.workflow.agent_runner import ask_agent

    agent = create_assistant_agent(
        "offer_extractor",
        OFFER_EXTRACTION_PROMPT,
        description="Extract structured opening offer from contract text",
    )
    clipped = text if len(text) <= 16000 else text[:16000]
    response = await ask_agent(
        agent,
        "Extract the lender's opening loan offer from this contract text.\n"
        "Return only the JSON block described in your instructions.\n\n"
        f"{clipped}",
    )
    deal = parse_offer_from_text(response)
    if deal is None:
        return None
    return deal.model_copy(update={"consensus_reached": False})


async def extract_opening_offer_from_pdf(
    data: bytes,
    *,
    use_llm: bool = True,
) -> tuple[DealTerms, str]:
    """
    Read a lender offer PDF and return (opening DealTerms, raw text).

    Prefers an extraction agent for messy real-world wording, then falls back
    to deterministic heuristics when the agent is unavailable or inconclusive.
    """
    text = extract_text_from_pdf(data)
    offer: DealTerms | None = None
    llm_error: Exception | None = None

    if use_llm:
        try:
            offer = await extract_offer_with_llm(text)
        except Exception as exc:  # noqa: BLE001
            llm_error = exc

    if offer is None:
        offer = extract_offer_heuristically(text)

    if offer is None:
        detail = f" Agent error: {llm_error}" if llm_error else ""
        raise ContractExtractionError(
            "Could not extract downpayment, interest rate, and loan length from the PDF."
            + detail
        )
    return offer, text
