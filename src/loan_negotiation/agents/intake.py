from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient

from loan_negotiation.agents.factory import create_assistant_agent
from loan_negotiation.config import Settings
from loan_negotiation.workflow.prompts import INTAKE_AGENT_PROMPT


def create_intake_agent(
    model_client: OllamaChatCompletionClient | None = None,
    settings: Settings | None = None,
) -> AssistantAgent:
    return create_assistant_agent(
        "intake_agent",
        INTAKE_AGENT_PROMPT,
        description="Gathers missing borrower and lender information before negotiation.",
        model_client=model_client,
        settings=settings,
    )
