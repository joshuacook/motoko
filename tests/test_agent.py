"""Tests for Agent class."""

import pytest

from motoko.agent import Agent
from motoko.models.base import BaseModel
from motoko.tools.base import BaseTool


class MockModel(BaseModel):
    """Mock model for testing."""

    def chat(self, messages, tools=None, system=None, **kwargs):
        """Mock chat method."""
        raise NotImplementedError("Mock model")

    async def stream(self, messages, tools=None, system=None, **kwargs):
        """Mock stream method."""
        raise NotImplementedError("Mock model")
        yield  # Make it a generator

    def format_tools(self, tools):
        """Mock format_tools."""
        return tools

    def format_messages(self, messages):
        """Mock format_messages."""
        return messages

    def parse_response(self, response):
        """Mock parse_response."""
        return response


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool"

    def get_schema(self):
        """Get mock schema."""
        return {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        }

    def execute(self, **kwargs):
        """Execute mock tool."""
        return self._create_result(content=f"Mock result: {kwargs}")


def test_agent_initialization():
    """Test agent can be initialized."""
    model = MockModel(model_name="mock-model")
    tools = [MockTool()]

    agent = Agent(model=model, tools=tools, workspace="/tmp")

    assert agent.model == model
    assert len(agent.tools) == 1
    assert agent.workspace.as_posix() == "/tmp"


def test_agent_tool_registry():
    """Test agent builds tool registry."""
    model = MockModel(model_name="mock-model")
    tools = [MockTool()]

    agent = Agent(model=model, tools=tools)

    assert "mock_tool" in agent._tool_registry
    assert agent._tool_registry["mock_tool"] == tools[0]


def test_agent_role_management():
    """Test agent role management methods work."""
    model = MockModel(model_name="mock-model")
    agent = Agent(model=model)

    # Test switch_role works (doesn't raise)
    agent.switch_role("new prompt", role_name="test_role")
    assert agent.current_role == "test_role"
    assert agent.current_system_prompt == "new prompt"

    # Test add_role works
    agent.add_role("architect", "You are an architect")
    assert "architect" in agent.roles
    assert agent.roles["architect"].name == "architect"

    # Test chat_as raises ValueError for non-existent role
    with pytest.raises(ValueError, match="Role 'nonexistent' not found"):
        agent.chat_as("nonexistent", "Hello")


def test_agent_reset():
    """Test agent reset clears state."""
    model = MockModel(model_name="mock-model")
    agent = Agent(model=model)

    # Add some state
    agent.messages.append({"role": "user", "content": "test"})
    agent.current_system_prompt = "test prompt"

    # Reset
    agent.reset()

    assert len(agent.messages) == 0
    assert agent.current_system_prompt is None
