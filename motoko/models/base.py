"""Base class for model implementations."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ..types import Message, ModelResponse, StreamEvent, ToolDefinition


class BaseModel(ABC):
    """Base class for all model implementations.

    This abstract class defines the interface that all model providers
    (Anthropic, Gemini, OpenAI, etc.) must implement. It hides provider-specific
    details and provides a unified interface to the Agent.
    """

    def __init__(self, model_name: str, api_key: str | None = None, **kwargs: Any):
        """Initialize model.

        Args:
            model_name: Name of the model (e.g., "claude-3-5-sonnet", "gemini-2.0-flash")
            api_key: API key for the provider (if None, will use environment variable)
            **kwargs: Additional provider-specific configuration
        """
        self.model_name = model_name
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Send chat request to model.

        Args:
            messages: Conversation history
            tools: Available tools the model can use
            system: System prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with unified format

        Raises:
            Exception: If API call fails
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Stream chat response from model.

        Args:
            messages: Conversation history
            tools: Available tools the model can use
            system: System prompt
            **kwargs: Additional provider-specific parameters

        Yields:
            StreamEvent objects (TextChunk, ToolStart, ToolEnd, etc.)

        Raises:
            Exception: If API call fails
        """
        pass

    @abstractmethod
    def format_tools(self, tools: list[ToolDefinition]) -> Any:
        """Convert tool definitions to provider-specific format.

        Args:
            tools: Tool definitions in motoko format

        Returns:
            Provider-specific tool format
        """
        pass

    @abstractmethod
    def format_messages(self, messages: list[Message]) -> Any:
        """Convert messages to provider-specific format.

        Args:
            messages: Messages in motoko format

        Returns:
            Provider-specific message format
        """
        pass

    @abstractmethod
    def parse_response(self, response: Any) -> ModelResponse:
        """Convert provider response to unified format.

        Args:
            response: Provider-specific response

        Returns:
            ModelResponse in motoko format
        """
        pass

    def __repr__(self) -> str:
        """String representation of model."""
        return f"{self.__class__.__name__}(model={self.model_name})"
