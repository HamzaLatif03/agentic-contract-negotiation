"""Local Llama 3.2 agent extracts a structured opening offer from contract text."""

from __future__ import annotations

from loan_negotiation.agents.factory import ask_agent, create_assistant_agent, create_model_client
from loan_negotiation.config import Settings, settings_with_model
from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.services.ollama_check import ensure_model_ready
from loan_negotiation.workflow.deal_parser import parse_offer_from_text
from loan_negotiation.workflow.negotiation_messages import format_deal_line

OFFER_EXTRACTION_PROMPT = """\
You extract a lender's opening UK mortgage offer from contract or offer-letter text.

Read the full text carefully. Values may appear in tables, bullets, or prose.

Return ONLY one fenced JSON block with these fields:
- downpayment: deposit in pounds (absolute amount, not percent)
- interest_rate_pct: number (e.g. 4.49)
- loan_length_years: full mortgage term (whole number)
- rate_type: "fixed" | "tracker" | "discount"
- initial_period_years: 2, 5, or 10 (initial deal / product period)
- arrangement_fee: pounds (0 if fee-free / not stated)
- cashback: pounds (0 if none)
- overpayment_allowance_pct: annual % without ERC (default 10 if unclear)
- erc_pct: early repayment charge % during initial period (0 if none/not stated)
- repayment_type: "capital_repayment" | "interest_only"
- portable: true/false (default true if unclear)
- free_valuation: true/false
- free_legal: true/false
- consensus_reached: false

Rules:
- Prefer the opening/proposed offer amounts, not repayment schedules or examples.
- Do not invent values that are not supported by the text; use sensible defaults only when noted above.
"""


class OpeningOfferExtractionError(ValueError):
    """Raised when local Llama cannot produce a usable opening offer."""


def format_opening_offer_announcement(offer: DealTerms) -> str:
    """Human-readable opening line plus JSON for the negotiation transcript."""
    payload = offer.model_copy(update={"consensus_reached": False})
    return (
        f"My opening offer is {format_deal_line(offer)}.\n"
        f"```json\n{payload.model_dump_json(indent=2)}\n```"
    )


async def extract_opening_offer_with_local_llama(
    contract_text: str,
    settings: Settings | None = None,
) -> DealTerms:
    """Always use local Ollama Llama 3.2 — never the comparison/cloud model."""
    base = settings or settings_with_model(None)
    local_settings = settings_with_model("ollama-local", base)
    ensure_model_ready(local_settings)
    client = create_model_client(local_settings)
    agent = create_assistant_agent(
        "offer_extractor",
        OFFER_EXTRACTION_PROMPT,
        description="Extract structured UK mortgage opening offer from contract text",
        model_client=client,
    )
    clipped = contract_text if len(contract_text) <= 16000 else contract_text[:16000]
    response = await ask_agent(
        agent,
        "Extract the lender's opening UK mortgage offer from this contract text.\n"
        "Return only the JSON block described in your instructions.\n\n"
        f"{clipped}",
    )
    deal = parse_offer_from_text(response)
    if deal is None:
        raise OpeningOfferExtractionError(
            "Local Llama 3.2 could not extract a usable UK mortgage opening offer "
            "(deposit, rate, and term) from the contract text."
        )
    return deal.model_copy(update={"consensus_reached": False})
