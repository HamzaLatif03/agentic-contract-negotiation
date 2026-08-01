from collections.abc import Sequence

from autogen_agentchat.base import TerminatedException, TerminationCondition
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, StopMessage

from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.workflow.deal_parser import (
    parse_offer_from_text_lenient,
    prose_claims_acceptance,
)
from loan_negotiation.workflow.negotiation_state import (
    apply_acceptance_semantics,
    deals_match,
)


class JsonConsensusTermination(TerminationCondition):
    """End only when a party explicitly accepts the other's latest package."""

    def __init__(self, sources: set[str]) -> None:
        self._sources = sources
        self._last_offer: dict[str, DealTerms] = {}
        self._terminated = False

    @property
    def terminated(self) -> bool:
        return self._terminated

    def _speaker(self, source: str) -> str:
        return "lender" if source == "lender_negotiator" else "borrower"

    def _normalize_message_offer(
        self, speaker: str, text: str
    ) -> DealTerms | None:
        other = "borrower" if speaker == "lender" else "lender"
        other_last = self._last_offer.get(other)
        offer = parse_offer_from_text_lenient(
            text,
            fallback=self._last_offer.get(speaker),
        )
        accepting = prose_claims_acceptance(text)
        if offer is None:
            if accepting and other_last is not None:
                return other_last.model_copy(update={"consensus_reached": True})
            return None
        accepting = accepting or offer.consensus_reached
        # Echo-copy without accept: keep as a non-consensus counter so chat continues.
        if (
            not accepting
            and other_last is not None
            and deals_match(offer, other_last)
        ):
            return offer.model_copy(update={"consensus_reached": False})
        return apply_acceptance_semantics(
            offer, other_last, text, accepting=accepting
        )

    async def __call__(
        self, messages: Sequence[BaseAgentEvent | BaseChatMessage]
    ) -> StopMessage | None:
        if self._terminated:
            raise TerminatedException("Termination condition has already been reached")

        for message in messages:
            if not isinstance(message, BaseChatMessage):
                continue
            if message.source not in self._sources:
                continue
            if not hasattr(message, "to_text"):
                continue

            speaker = self._speaker(message.source)
            offer = self._normalize_message_offer(speaker, message.to_text())
            if offer is None:
                continue

            self._last_offer[speaker] = offer
            if offer.consensus_reached:
                self._terminated = True
                return StopMessage(
                    content="Parties reached agreement on the same offer",
                    source="JsonConsensusTermination",
                )

        return None

    async def reset(self) -> None:
        self._last_offer.clear()
        self._terminated = False
