"""AssistantAgent that clamps each offer into the party's private min/max walls."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from typing import Any, Union

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, TextMessage
from autogen_core import CancellationToken

from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.workflow.wall_enforcement import enforce_party_walls_in_message


class PartyWallAssistantAgent(AssistantAgent):
    """
    After each model reply, hard-clamp JSON offer fields into this party's walls.

    Prevents borrower/lender from publishing deposits (etc.) outside their own
    min/max into the shared negotiation transcript.
    """

    def __init__(
        self,
        *args: Any,
        party_terms: BorrowerTerms | LenderTerms,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._party_terms = party_terms
        self.last_wall_notes: list[str] = []

    def _rewrite_text(self, content: str) -> str:
        rewritten, notes = enforce_party_walls_in_message(content, self._party_terms)
        self.last_wall_notes = notes
        return rewritten

    def _rewrite_chat_message(self, message: BaseChatMessage) -> BaseChatMessage:
        if not isinstance(message, TextMessage):
            return message
        content = message.to_text() if hasattr(message, "to_text") else str(message.content)
        rewritten = self._rewrite_text(content)
        if rewritten == content:
            return message
        return TextMessage(content=rewritten, source=message.source)

    def _rewrite_item(
        self, item: Union[BaseAgentEvent, BaseChatMessage, Response]
    ) -> Union[BaseAgentEvent, BaseChatMessage, Response]:
        if isinstance(item, Response):
            return Response(
                chat_message=self._rewrite_chat_message(item.chat_message),
                inner_messages=item.inner_messages,
            )
        if isinstance(item, TextMessage) and item.source == self.name:
            return self._rewrite_chat_message(item)
        return item

    async def on_messages_stream(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, Response], None]:
        async for item in super().on_messages_stream(messages, cancellation_token):
            yield self._rewrite_item(item)
