"""Tests for core types."""

import pytest

from motoko.types import (
    Message,
    MessageRole,
    TextContent,
    ToolResult,
    ToolUse,
    VerbosityLevel,
)


def test_tool_result_verbosity():
    """Test tool result formatting at different verbosity levels."""
    result = ToolResult(
        content="This is a long result " * 100,
        metadata={"action": "read", "target": "main.py"},
    )

    # Minimal should be brief
    minimal = result.format(VerbosityLevel.MINIMAL)
    assert "Read main.py" in minimal
    assert len(minimal) < 100

    # Normal should truncate long content
    normal = result.format(VerbosityLevel.NORMAL)
    assert "..." in normal or len(normal) <= 1000

    # Verbose should include metadata
    verbose = result.format(VerbosityLevel.VERBOSE)
    assert "Metadata:" in verbose


def test_message_to_dict():
    """Test message conversion to dict."""
    # Simple text message
    msg1 = Message(role=MessageRole.USER, content="Hello")
    assert msg1.to_dict() == {"role": "user", "content": "Hello"}

    # Message with content blocks
    msg2 = Message(
        role=MessageRole.ASSISTANT,
        content=[
            TextContent(text="Let me read that file"),
            ToolUse(id="tool_1", name="read_file", input={"path": "main.py"}),
        ],
    )
    dict2 = msg2.to_dict()
    assert dict2["role"] == "assistant"
    assert len(dict2["content"]) == 2
    assert dict2["content"][0]["type"] == "text"
    assert dict2["content"][1]["type"] == "tool_use"


def test_tool_result_error():
    """Test tool result with error."""
    error_result = ToolResult(
        content="File not found",
        is_error=True,
        metadata={"action": "read", "target": "missing.py"},
    )

    assert error_result.is_error
    assert "Error" in error_result.summary()
