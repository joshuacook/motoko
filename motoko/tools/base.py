"""Base class for tools."""

from abc import ABC, abstractmethod
from typing import Any

from ..types import ToolDefinition, ToolResult, VerbosityLevel


class BaseTool(ABC):
    """Base class for all tools.

    Tools are capabilities that the agent can use to interact with
    the world (read files, search web, execute commands, etc.).
    """

    # Subclasses should define these
    name: str = ""
    description: str = ""

    def __init__(self, verbosity: VerbosityLevel = VerbosityLevel.NORMAL):
        """Initialize tool.

        Args:
            verbosity: Default verbosity level for tool results
        """
        self.verbosity = verbosity

    @abstractmethod
    def get_schema(self) -> dict[str, Any]:
        """Return JSON schema for tool parameters.

        Returns:
            JSON schema dict with type, properties, required fields
        """
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with execution result

        Raises:
            Exception: If tool execution fails
        """
        pass

    def get_definition(self) -> ToolDefinition:
        """Get tool definition for model.

        Returns:
            ToolDefinition with name, description, and schema
        """
        return ToolDefinition(
            name=self.name, description=self.description, input_schema=self.get_schema()
        )

    def _create_result(
        self,
        content: str,
        is_error: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Helper to create ToolResult.

        Args:
            content: Result content
            is_error: Whether this is an error result
            metadata: Additional metadata

        Returns:
            ToolResult with formatted content
        """
        return ToolResult(
            content=content,
            is_error=is_error,
            metadata=metadata or {},
        )

    def __repr__(self) -> str:
        """String representation of tool."""
        return f"{self.__class__.__name__}(name={self.name})"
