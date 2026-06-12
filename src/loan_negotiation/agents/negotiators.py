from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient

from loan_negotiation.agents.factory import create_assistant_agent
from loan_negotiation.config import Settings
from loan_negotiation.workflow.prompts import (
    BORROWER_NEGOTIATOR_PROMPT,
    LENDER_NEGOTIATOR_PROMPT,
)


def create_borrower_negotiator(
    model_client: OllamaChatCompletionClient | None = None,
    settings: Settings | None = None,
) -> AssistantAgent:
    return create_assistant_agent(
        "borrower_negotiator",
        BORROWER_NEGOTIATOR_PROMPT,
        description="Negotiates loan terms on behalf of the borrower.",
        model_client=model_client,
        settings=settings,
    )


def create_lender_negotiator(
    model_client: OllamaChatCompletionClient | None = None,
    settings: Settings | None = None,
) -> AssistantAgent:
    return create_assistant_agent(
        "lender_negotiator",
        LENDER_NEGOTIATOR_PROMPT,
        description="Negotiates loan terms on behalf of the lender.",
        model_client=model_client,
        settings=settings,
    )
