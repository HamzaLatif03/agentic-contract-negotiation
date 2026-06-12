from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient

from loan_negotiation.agents.factory import create_assistant_agent
from loan_negotiation.config import Settings
from loan_negotiation.workflow.prompts import BORROWER_RANKER_PROMPT, LENDER_RANKER_PROMPT


def create_borrower_ranker(
    model_client: OllamaChatCompletionClient | None = None,
    settings: Settings | None = None,
) -> AssistantAgent:
    return create_assistant_agent(
        "borrower_ranker",
        BORROWER_RANKER_PROMPT,
        description="Scores the final deal from the borrower's perspective (1-10).",
        model_client=model_client,
        settings=settings,
    )


def create_lender_ranker(
    model_client: OllamaChatCompletionClient | None = None,
    settings: Settings | None = None,
) -> AssistantAgent:
    return create_assistant_agent(
        "lender_ranker",
        LENDER_RANKER_PROMPT,
        description="Scores the final deal from the lender's perspective (1-10).",
        model_client=model_client,
        settings=settings,
    )
