"""motoko - A Python package for building role-based AI agents.

Named after Major Motoko Kusanagi from Ghost in the Shell.
"""

__version__ = "0.1.0"

from .agent import Agent
from .models.anthropic import AnthropicModel
from .models.base import BaseModel
from .models.factory import ModelFactory, create_model
from .models.gemini import GeminiModel
from .skills.loader import SkillLoader
from .skills.skill import Skill
from .streaming import (
    SSEClient,
    create_sse_response_fastapi,
    format_sse,
    parse_sse_event,
    stream_to_sse,
)
from .tools.base import BaseTool
from .tools.bash import BashTool
from .tools.files import EditFileTool, GlobTool, GrepTool, ReadFileTool, WriteFileTool
from .tools.git import GitCommitTool, GitDiffTool, GitStatusTool
from .tools.web import WebFetchTool, WebSearchTool
from .types import (
    Message,
    MessageRole,
    ModelResponse,
    Role,
    StreamEvent,
    ToolDefinition,
    ToolResult,
    VerbosityLevel,
)

__all__ = [
    # Agent
    "Agent",
    # Models
    "AnthropicModel",
    "BaseModel",
    "GeminiModel",
    "ModelFactory",
    "create_model",
    # Skills
    "Skill",
    "SkillLoader",
    # Streaming
    "SSEClient",
    "create_sse_response_fastapi",
    "format_sse",
    "parse_sse_event",
    "stream_to_sse",
    # Tools - Base
    "BaseTool",
    # Tools - Files
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "GlobTool",
    "GrepTool",
    # Tools - Web
    "WebFetchTool",
    "WebSearchTool",
    # Tools - Git
    "GitStatusTool",
    "GitDiffTool",
    "GitCommitTool",
    # Tools - Bash
    "BashTool",
    # Types
    "Message",
    "MessageRole",
    "ModelResponse",
    "Role",
    "StreamEvent",
    "ToolDefinition",
    "ToolResult",
    "VerbosityLevel",
]
