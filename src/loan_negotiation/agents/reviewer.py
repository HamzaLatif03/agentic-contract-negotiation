from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient

from loan_negotiation.agents.factory import create_assistant_agent
from loan_negotiation.config import Settings
from loan_negotiation.workflow.prompts import REVIEWER_AGENT_PROMPT


def create_reviewer_agent(
    model_client: OllamaChatCompletionClient | None = None,
    settings: Settings | None = None,
) -> AssistantAgent:
    return create_assistant_agent(
        "reviewer_agent",
        REVIEWER_AGENT_PROMPT,
        description="Validates the deal against original terms and required loan details.",
        model_client=model_client,
        settings=settings,
    )
