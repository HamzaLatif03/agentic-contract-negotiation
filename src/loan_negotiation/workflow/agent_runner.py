from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken


async def ask_agent(agent: AssistantAgent, prompt: str) -> str:
    response = await agent.on_messages(
        [TextMessage(content=prompt, source="user")],
        cancellation_token=CancellationToken(),
    )
    return response.chat_message.to_text()
