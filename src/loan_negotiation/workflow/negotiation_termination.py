from collections.abc import Sequence

from autogen_agentchat.base import TerminatedException, TerminationCondition
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, StopMessage

from loan_negotiation.models.loan_terms import DealTerms
from loan_negotiation.workflow.deal_parser import parse_offer_from_text_lenient
from loan_negotiation.workflow.negotiation_state import deals_match


class JsonConsensusTermination(TerminationCondition):
    """End when parties reach agreement on matching terms."""

    def __init__(self, sources: set[str]) -> None:
        self._sources = sources
        self._last_offer: dict[str, DealTerms] = {}
        self._last_consensus: dict[str, DealTerms] = {}
        self._terminated = False

    @property
    def terminated(self) -> bool:
        return self._terminated

    def _speaker(self, source: str) -> str:
        return "lender" if source == "lender_negotiator" else "borrower"

    def _both_latest_offers_match(self) -> bool:
        lender = self._last_offer.get("lender")
        borrower = self._last_offer.get("borrower")
        return (
            lender is not None
            and borrower is not None
            and deals_match(lender, borrower)
        )

    def _check_explicit_consensus(self, speaker: str, offer: DealTerms) -> bool:
        if not offer.consensus_reached:
            return False

        other = "borrower" if speaker == "lender" else "lender"
        other_last = self._last_offer.get(other)
        if other_last is not None and deals_match(offer, other_last):
            return True

        self._last_consensus[speaker] = offer
        other_consensus = self._last_consensus.get(other)
        return other_consensus is not None and deals_match(offer, other_consensus)

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
            offer = parse_offer_from_text_lenient(
                message.to_text(),
                fallback=self._last_offer.get(speaker),
            )
            if offer is None:
                continue

            self._last_offer[speaker] = offer
            if self._check_explicit_consensus(speaker, offer) or self._both_latest_offers_match():
                self._terminated = True
                return StopMessage(
                    content="Parties reached agreement on the same offer",
                    source="JsonConsensusTermination",
                )

        return None

    async def reset(self) -> None:
        self._last_offer.clear()
        self._last_consensus.clear()
        self._terminated = False
