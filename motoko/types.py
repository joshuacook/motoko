"""Core types for motoko agent system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class MessageRole(str, Enum):
    """Role of a message in the conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContentBlockType(str, Enum):
    """Type of content block in a message."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


class VerbosityLevel(str, Enum):
    """Verbosity level for tool results."""

    MINIMAL = "minimal"
    NORMAL = "normal"
    VERBOSE = "verbose"


class StopReason(str, Enum):
    """Reason why the model stopped generating."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"


@dataclass
class Role:
    """Represents an agent role with associated context and tools.

    Roles enable the agent to switch contexts and tool access mid-conversation.
    For example, switching from "artist manager" to "booking agent" to "financial advisor".
    """

    name: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)  # Tool names
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextContent:
    """Text content block."""

    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ToolUse:
    """Tool use block from model."""

    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result from tool execution."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: str = ""
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def format(self, verbosity: VerbosityLevel = VerbosityLevel.NORMAL) -> str:
        """Format tool result based on verbosity level.

        Args:
            verbosity: Level of detail to include

        Returns:
            Formatted result string
        """
        if verbosity == VerbosityLevel.MINIMAL:
            return self.summary()
        elif verbosity == VerbosityLevel.NORMAL:
            return self.standard()
        elif verbosity == VerbosityLevel.VERBOSE:
            return self.detailed()
        return self.content

    def summary(self) -> str:
        """Brief summary of result."""
        action = self.metadata.get("action", "executed")
        target = self.metadata.get("target", "tool")
        if self.is_error:
            return f"Error: {action} {target}"
        return f"{action.capitalize()} {target}"

    def standard(self) -> str:
        """Standard output (default)."""
        if len(self.content) > 1000:
            return self.content[:1000] + f"\n... ({len(self.content)} chars total)"
        return self.content

    def detailed(self) -> str:
        """Full output with metadata."""
        result = self.content
        if self.metadata:
            result += f"\n\nMetadata: {self.metadata}"
        return result


ContentBlock = TextContent | ToolUse | ToolResult


@dataclass
class Message:
    """A message in the conversation."""

    role: MessageRole
    content: str | list[ContentBlock]
    metadata: dict[str, Any] = field(default_factory=dict)
    role_name: str | None = None  # Which agent role sent this (if multi-role)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        if isinstance(self.content, str):
            return {"role": self.role.value, "content": self.content}

        # Convert content blocks to dicts
        content_list = []
        for block in self.content:
            if isinstance(block, TextContent):
                content_list.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolUse):
                content_list.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif isinstance(block, ToolResult):
                content_list.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error,
                })

        return {"role": self.role.value, "content": content_list}


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by the model."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class ModelResponse:
    """Unified response from any model."""

    content: list[ContentBlock]
    stop_reason: StopReason
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return any(isinstance(block, ToolUse) for block in self.content)

    @property
    def tool_calls(self) -> list[ToolUse]:
        """Get all tool calls from response."""
        return [block for block in self.content if isinstance(block, ToolUse)]

    @property
    def text(self) -> str:
        """Get all text content concatenated."""
        return "".join(
            block.text for block in self.content if isinstance(block, TextContent)
        )


@dataclass
class StreamEvent:
    """Event from streaming response."""

    type: str
    data: Any
    metadata: dict[str, Any] = field(default_factory=dict)


# Streaming event types
@dataclass
class TextChunk(StreamEvent):
    """Incremental text chunk."""

    type: Literal["text_chunk"] = "text_chunk"
    data: str = ""


@dataclass
class ToolStart(StreamEvent):
    """Tool execution starting."""

    type: Literal["tool_start"] = "tool_start"
    data: ToolUse = field(default_factory=lambda: ToolUse())


@dataclass
class ToolEnd(StreamEvent):
    """Tool execution complete."""

    type: Literal["tool_end"] = "tool_end"
    data: ToolResult = field(default_factory=lambda: ToolResult())


@dataclass
class ErrorEvent(StreamEvent):
    """Error occurred."""

    type: Literal["error"] = "error"
    data: str = ""


@dataclass
class DoneEvent(StreamEvent):
    """Response complete."""

    type: Literal["done"] = "done"
    data: ModelResponse = field(default_factory=lambda: ModelResponse(
        content=[], stop_reason=StopReason.END_TURN, model=""
    ))
