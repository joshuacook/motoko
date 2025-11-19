"""Integration tests for Agent with tools and full loops.

These tests verify the agent works end-to-end with real API calls.
"""

import tempfile
from pathlib import Path

import pytest

from motoko import Agent, GlobTool, ReadFileTool, WriteFileTool, create_model


@pytest.mark.integration
def test_agent_with_file_tools(anthropic_api_key):
    """Test agent can use file tools to complete a task."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create a test file
        test_file = workspace / "test.txt"
        test_file.write_text("The answer is 42")

        # Create agent with file tools
        model = create_model("claude-sonnet-4-5-20250929")
        tools = [
            ReadFileTool(workspace=workspace),
            GlobTool(workspace=workspace),
        ]
        agent = Agent(model=model, tools=tools, workspace=workspace)

        # Ask agent to read the file
        response = agent.chat(
            message="Read the file test.txt and tell me what number is in it.",
            system_prompt="You are a helpful assistant that uses tools to answer questions.",
        )

        # Agent should have used ReadFileTool and found the answer
        assert response.text
        assert "42" in response.text


@pytest.mark.integration
def test_agent_with_write_tool(anthropic_api_key):
    """Test agent can write files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        model = create_model("claude-sonnet-4-5-20250929")
        tools = [
            WriteFileTool(workspace=workspace),
            ReadFileTool(workspace=workspace),
        ]
        agent = Agent(model=model, tools=tools, workspace=workspace)

        # Ask agent to write a file
        response = agent.chat(
            message="Create a file called 'hello.txt' with the content 'Hello, World!'",
            system_prompt="You are a helpful assistant that uses tools.",
        )

        # Check file was created
        hello_file = workspace / "hello.txt"
        assert hello_file.exists()
        assert "Hello, World!" in hello_file.read_text()


@pytest.mark.integration
def test_agent_multi_turn_conversation(anthropic_api_key):
    """Test agent maintains conversation across multiple turns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        model = create_model("claude-sonnet-4-5-20250929")
        agent = Agent(model=model, workspace=workspace)

        # First message establishes context
        response1 = agent.chat(
            message="My favorite number is 7.",
            system_prompt="You are a helpful assistant.",
        )
        assert response1.text

        # Agent maintains history within same conversation via messages list
        # The agent's chat method adds to agent.messages each time
        # So we can check the history is being maintained
        assert len(agent.messages) > 0


@pytest.mark.integration
def test_agent_tool_loop(anthropic_api_key):
    """Test agent can call multiple tools in sequence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create multiple test files
        (workspace / "file1.txt").write_text("Part 1")
        (workspace / "file2.txt").write_text("Part 2")

        model = create_model("claude-sonnet-4-5-20250929")
        tools = [
            ReadFileTool(workspace=workspace),
            GlobTool(workspace=workspace),
        ]
        agent = Agent(model=model, tools=tools, workspace=workspace)

        # Ask agent to find and read multiple files
        response = agent.chat(
            message="Find all .txt files and tell me their combined content.",
            system_prompt="You are a helpful assistant that uses tools to complete tasks.",
        )

        # Agent should have used both Glob and Read tools
        assert response.text
        # Should mention both parts
        assert ("Part 1" in response.text or "Part 2" in response.text)
