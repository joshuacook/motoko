"""Basic streaming example."""

import asyncio
from pathlib import Path

from motoko import Agent, create_model, ReadFileTool, GlobTool
from motoko.types import TextChunk, ToolStart, ToolEnd, DoneEvent, ErrorEvent


async def basic_streaming_example():
    """Demonstrate basic streaming with agent."""
    # Create agent
    model = create_model("claude-3-5-sonnet-20241022")

    tools = [
        ReadFileTool(workspace=Path.cwd()),
        GlobTool(workspace=Path.cwd()),
    ]

    agent = Agent(model=model, tools=tools)

    print("=== Basic Streaming Example ===\n")
    print("User: How many Python files are in this project?\n")
    print("Agent: ", end="", flush=True)

    # Stream response
    async for event in agent.stream(
        message="How many Python files are in this project?",
        system_prompt="You are a helpful assistant.",
    ):
        # Handle different event types
        if isinstance(event, TextChunk):
            # Print text as it arrives
            print(event.data, end="", flush=True)

        elif isinstance(event, ToolStart):
            # Notify when tool starts
            print(f"\n[Using tool: {event.data.name}]", flush=True)

        elif isinstance(event, ToolEnd):
            # Tool completed
            if event.data.is_error:
                print(f"[Tool error: {event.data.content}]", flush=True)
            else:
                print(f"[Tool complete]", flush=True)
            print("Agent: ", end="", flush=True)

        elif isinstance(event, DoneEvent):
            # Response complete
            print("\n\n[Response complete]")
            print(f"Model: {event.data.model}")
            print(f"Usage: {event.data.usage}")

        elif isinstance(event, ErrorEvent):
            # Error occurred
            print(f"\n[Error: {event.data}]")
            break

    print()


async def streaming_with_context():
    """Show streaming with conversation context."""
    model = create_model("claude-3-5-sonnet-20241022")
    agent = Agent(model=model)

    print("\n=== Streaming with Context ===\n")

    # First message
    print("User: What is 2+2?")
    print("Agent: ", end="", flush=True)

    async for event in agent.stream("What is 2+2?"):
        if isinstance(event, TextChunk):
            print(event.data, end="", flush=True)
        elif isinstance(event, DoneEvent):
            print("\n")

    # Follow-up (uses context)
    print("User: Multiply that by 3")
    print("Agent: ", end="", flush=True)

    async for event in agent.stream("Multiply that by 3"):
        if isinstance(event, TextChunk):
            print(event.data, end="", flush=True)
        elif isinstance(event, DoneEvent):
            print("\n")

    print(f"Conversation length: {len(agent.messages)} messages\n")


async def collect_full_response():
    """Show how to collect full response from stream."""
    model = create_model("claude-3-5-sonnet-20241022")
    agent = Agent(model=model)

    print("\n=== Collecting Full Response ===\n")

    # Collect all text chunks
    full_text = []

    async for event in agent.stream("Tell me a haiku about coding"):
        if isinstance(event, TextChunk):
            full_text.append(event.data)
        elif isinstance(event, DoneEvent):
            break

    # Print complete response
    response = "".join(full_text)
    print("Complete response:")
    print(response)
    print()


if __name__ == "__main__":
    # Run examples
    print("Note: These examples require ANTHROPIC_API_KEY environment variable\n")

    asyncio.run(basic_streaming_example())
    # asyncio.run(streaming_with_context())
    # asyncio.run(collect_full_response())
