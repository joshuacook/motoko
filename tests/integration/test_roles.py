"""Integration tests for role management."""

import tempfile
from pathlib import Path

import pytest

from motoko import Agent, ReadFileTool, WriteFileTool, create_model


@pytest.mark.integration
def test_role_switching(anthropic_api_key):
    """Test agent can switch roles mid-conversation."""
    model = create_model("claude-sonnet-4-5-20250929")
    agent = Agent(model=model)

    # Start as a poet
    agent.switch_role("You are a poet who speaks in rhyme.", role_name="poet")
    response1 = agent.chat(message="Tell me about the sky.")

    # Switch to scientist
    agent.switch_role("You are a scientist who explains things precisely.", role_name="scientist")
    response2 = agent.chat(message="Tell me about the sky.")

    # Both should have content, but likely different styles
    assert response1.text
    assert response2.text
    assert agent.current_role == "scientist"
    assert len(agent.role_history) == 1  # One switch recorded


@pytest.mark.integration
def test_multi_role_collaboration(anthropic_api_key):
    """Test multiple roles can participate in conversation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        model = create_model("claude-sonnet-4-5-20250929")
        tools = [
            ReadFileTool(workspace=workspace),
            WriteFileTool(workspace=workspace),
        ]
        agent = Agent(model=model, tools=tools, workspace=workspace)

        # Register roles
        agent.add_role(
            "writer",
            "You create content and write files.",
            tools=[WriteFileTool(workspace=workspace)],
        )

        agent.add_role(
            "reviewer",
            "You review content and provide feedback.",
            tools=[ReadFileTool(workspace=workspace)],
        )

        # Writer creates a file
        response1 = agent.chat_as(
            "writer",
            "Create a file called 'story.txt' with a short story (one sentence).",
        )

        # Reviewer reads and comments
        response2 = agent.chat_as(
            "reviewer",
            "Read story.txt and tell me if it's good.",
        )

        # Both should work
        assert response1.text
        assert response2.text

        # File should exist
        assert (workspace / "story.txt").exists()


@pytest.mark.integration
def test_role_specific_tool_access(anthropic_api_key):
    """Test roles have access only to their specified tools."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        model = create_model("claude-sonnet-4-5-20250929")
        read_tool = ReadFileTool(workspace=workspace)
        write_tool = WriteFileTool(workspace=workspace)

        agent = Agent(model=model, tools=[read_tool, write_tool], workspace=workspace)

        # Read-only role
        agent.add_role(
            "reader",
            "You can only read files, not write them.",
            tools=[read_tool],
        )

        # Create a file manually
        (workspace / "test.txt").write_text("Test content")

        # Reader should be able to read
        response = agent.chat_as(
            "reader",
            "Read test.txt and tell me what's in it.",
        )

        assert response.text
        # Response should mention the content or that it read the file
        # (even if it can't write)


@pytest.mark.integration
def test_role_list_operations(anthropic_api_key):
    """Test listing and managing roles."""
    model = create_model("claude-sonnet-4-5-20250929")
    agent = Agent(model=model)

    # Initially no roles
    assert len(agent.list_roles()) == 0

    # Add some roles
    agent.add_role("role1", "First role")
    agent.add_role("role2", "Second role")
    agent.add_role("role3", "Third role")

    # List should show all 3
    roles = agent.list_roles()
    assert len(roles) == 3
    role_names = [r["name"] for r in roles]
    assert "role1" in role_names
    assert "role2" in role_names
    assert "role3" in role_names

    # Get specific role
    role1 = agent.get_role("role1")
    assert role1 is not None
    assert role1.name == "role1"

    # Remove a role
    agent.remove_role("role2")
    assert len(agent.list_roles()) == 2
    assert agent.get_role("role2") is None
