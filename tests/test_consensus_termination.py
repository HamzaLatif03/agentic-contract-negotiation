import asyncio

from autogen_agentchat.messages import TextMessage

from loan_negotiation.services.model_catalog import (
    find_comparison_model,
    provider_supports_autogen_tools,
)
from loan_negotiation.workflow.negotiation_state import (
    apply_acceptance_semantics,
    deals_match,
)
from loan_negotiation.workflow.negotiation_termination import JsonConsensusTermination
from deal_fixtures import sample_deal


def test_mistral_disables_autogen_tools():
    mistral = find_comparison_model("mistral-small")
    gemini = find_comparison_model("gemini-3.1-flash-lite")
    assert mistral is not None and provider_supports_autogen_tools(mistral) is False
    assert gemini is not None and provider_supports_autogen_tools(gemini) is False


def test_acceptance_coerces_to_counterparty_package():
    lender = sample_deal(interest_rate_pct=5.2, cashback=500, consensus_reached=False)
    drifted = sample_deal(
        interest_rate_pct=5.0,
        cashback=2_500,
        consensus_reached=True,
    )
    locked = apply_acceptance_semantics(
        drifted, lender, "Let's accept the offer.", accepting=True
    )
    assert deals_match(locked, lender)
    assert locked.consensus_reached is True
    assert locked.interest_rate_pct == 5.2
    assert locked.cashback == 500


def test_termination_stops_on_accept_phrase_with_drifted_json():
    term = JsonConsensusTermination({"lender_negotiator", "borrower_negotiator"})
    lender_json = sample_deal(
        interest_rate_pct=5.2,
        cashback=500,
        overpayment_allowance_pct=6,
        consensus_reached=False,
    ).model_dump_json()
    borrower_drift = sample_deal(
        interest_rate_pct=5.0,
        cashback=2_500,
        overpayment_allowance_pct=5,
        consensus_reached=False,
    ).model_dump_json()

    async def run() -> object:
        first = await term(
            [
                TextMessage(
                    content=f"Opening.\n```json\n{lender_json}\n```",
                    source="lender_negotiator",
                )
            ]
        )
        assert first is None
        return await term(
            [
                TextMessage(
                    content=(
                        "I think we have a good deal now. Let's accept the offer.\n"
                        f"```json\n{borrower_drift}\n```"
                    ),
                    source="borrower_negotiator",
                )
            ]
        )

    stop = asyncio.run(run())
    assert stop is not None
    assert "agreement" in stop.content.lower()
    assert term.terminated is True


def test_termination_stops_on_accept_without_json():
    term = JsonConsensusTermination({"lender_negotiator", "borrower_negotiator"})
    lender_json = sample_deal(consensus_reached=False).model_dump_json()

    async def run() -> object:
        await term(
            [
                TextMessage(
                    content=f"```json\n{lender_json}\n```",
                    source="lender_negotiator",
                )
            ]
        )
        return await term(
            [
                TextMessage(
                    content="Deal accepted! Since consensus_reached has been reached, I will stop here.",
                    source="borrower_negotiator",
                )
            ]
        )

    stop = asyncio.run(run())
    assert stop is not None
    assert term.terminated is True


def test_termination_does_not_stop_when_borrower_echoes_without_accept():
    term = JsonConsensusTermination({"lender_negotiator", "borrower_negotiator"})
    package = sample_deal(downpayment=100_000, consensus_reached=False).model_dump_json()

    async def run() -> object:
        await term(
            [
                TextMessage(
                    content=f"Opening.\n```json\n{package}\n```",
                    source="lender_negotiator",
                )
            ]
        )
        return await term(
            [
                TextMessage(
                    content=(
                        "We'd like a lower deposit and more flexible terms.\n"
                        f"```json\n{package}\n```"
                    ),
                    source="borrower_negotiator",
                )
            ]
        )

    stop = asyncio.run(run())
    assert stop is None
    assert term.terminated is False
