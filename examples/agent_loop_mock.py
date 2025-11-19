"""Mock example showing how the agent loop works (no API key required)."""

from pathlib import Path

from motoko import Agent, ReadFileTool, GlobTool
from motoko.models.base import BaseModel
from motoko.types import (
    Message,
    ModelResponse,
    StopReason,
    TextContent,
    ToolUse,
)


class MockModel(BaseModel):
    """Mock model that demonstrates tool calling."""

    def __init__(self):
        super().__init__("mock-model")
        self.call_count = 0

    def chat(self, messages, tools=None, system=None, **kwargs):
        """Simulate model behavior with tool calling."""
        self.call_count += 1

        # Get last user message
        last_msg = messages[-1]

        # First call: request to use glob tool
        if self.call_count == 1:
            print("  [Model] I need to use the glob tool to find files...")
            return ModelResponse(
                content=[
                    TextContent(text="Let me search for Python files."),
                    ToolUse(
                        id="tool_1",
                        name="glob",
                        input={"pattern": "**/*.py"},
                    ),
                ],
                stop_reason=StopReason.TOOL_USE,
                model="mock-model",
            )

        # Second call: after seeing tool results, respond with answer
        elif self.call_count == 2:
            # Extract tool result from messages
            print("  [Model] I received the tool results, now I'll answer...")
            return ModelResponse(
                content=[
                    TextContent(
                        text="Based on the glob search, I found multiple Python files "
                        "in the motoko package, including agent.py, types.py, and various "
                        "tool implementations."
                    )
                ],
                stop_reason=StopReason.END_TURN,
                model="mock-model",
            )

        # Fallback
        return ModelResponse(
            content=[TextContent(text="Task complete.")],
            stop_reason=StopReason.END_TURN,
            model="mock-model",
        )

    async def stream(self, messages, tools=None, system=None, **kwargs):
        """Not implemented for mock."""
        raise NotImplementedError()
        yield

    def format_tools(self, tools):
        """Mock format."""
        return [t.to_dict() for t in tools]

    def format_messages(self, messages):
        """Mock format."""
        return [m.to_dict() for m in messages]

    def parse_response(self, response):
        """Mock parse."""
        return response


# Set up workspace
workspace = Path("/Users/joshuacook/working/motoko")

# Create tools
tools = [
    GlobTool(workspace=workspace),
    ReadFileTool(workspace=workspace),
]

# Create mock model
model = MockModel()

# Create agent
agent = Agent(
    model=model,
    tools=tools,
    workspace=workspace,
)

print("=== Mock Agent Loop Demonstration ===\n")
print("This shows how the agent loop works without requiring API keys.\n")

print("User: How many Python files are in this project?")
print()

# Agent will:
# 1. Receive user message
# 2. Model requests glob tool
# 3. Agent executes glob tool
# 4. Model sees results and responds

response = agent.chat(
    message="How many Python files are in this project?",
    system_prompt="You are a helpful assistant.",
)

print()
print(f"Agent final response: {response.text}")
print()
print(f"Total model calls: {model.call_count}")
print(f"Conversation history: {len(agent.messages)} messages")

print("\n=== Conversation Flow ===")
for i, msg in enumerate(agent.messages, 1):
    role = msg.role.value
    if isinstance(msg.content, str):
        content_preview = msg.content[:80]
    else:
        content_types = [type(block).__name__ for block in msg.content]
        content_preview = f"[{', '.join(content_types)}]"

    print(f"{i}. {role}: {content_preview}...")
