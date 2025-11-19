"""Anthropic Claude model implementation."""

import os
from collections.abc import AsyncIterator
from typing import Any

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import (
    Message as AnthropicMessage,
)
from anthropic.types import (
    MessageParam,
    TextBlock,
    ToolUseBlock,
)

from ..types import (
    DoneEvent,
    Message,
    ModelResponse,
    StopReason,
    StreamEvent,
    TextChunk,
    TextContent,
    ToolDefinition,
    ToolResult,
    ToolStart,
    ToolUse,
)
from .base import BaseModel


class AnthropicModel(BaseModel):
    """Anthropic Claude model implementation.

    Supports all Claude models: claude-3-5-sonnet, claude-3-opus, claude-3-haiku, etc.
    """

    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-20241022",
        api_key: str | None = None,
        **kwargs: Any,
    ):
        """Initialize Anthropic model.

        Args:
            model_name: Claude model name (default: claude-3-5-sonnet-20241022)
            api_key: Anthropic API key (if None, uses ANTHROPIC_API_KEY env var)
            **kwargs: Additional parameters (max_tokens, temperature, etc.)
        """
        super().__init__(model_name, api_key, **kwargs)

        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key parameter."
            )

        # Create client
        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)

        # Default parameters
        self.max_tokens = kwargs.get("max_tokens", 4096)
        self.temperature = kwargs.get("temperature", 1.0)

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Send chat request to Claude.

        Args:
            messages: Conversation history
            tools: Available tools
            system: System prompt
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            ModelResponse with unified format
        """
        # Format messages for Anthropic API
        api_messages = self.format_messages(messages)

        # Format tools if provided
        api_tools = self.format_tools(tools) if tools else None

        # Build request parameters
        params = {
            "model": self.model_name,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        if system:
            params["system"] = system

        if api_tools:
            params["tools"] = api_tools

        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]

        # Make API call
        response = self.client.messages.create(**params)

        # Parse response to unified format
        return self.parse_response(response)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Stream chat response from Claude.

        Args:
            messages: Conversation history
            tools: Available tools
            system: System prompt
            **kwargs: Additional parameters

        Yields:
            StreamEvent objects (TextChunk, ToolStart, etc.)
        """
        # Format messages for Anthropic API
        api_messages = self.format_messages(messages)

        # Format tools if provided
        api_tools = self.format_tools(tools) if tools else None

        # Build request parameters
        params = {
            "model": self.model_name,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        if system:
            params["system"] = system

        if api_tools:
            params["tools"] = api_tools

        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]

        # Stream response
        async with self.async_client.messages.stream(**params) as stream:
            async for event in stream:
                # Handle different event types
                if event.type == "content_block_start":
                    block = event.content_block
                    if hasattr(block, "type") and block.type == "tool_use":
                        # Tool use starting
                        yield ToolStart(
                            data=ToolUse(
                                id=block.id,
                                name=block.name,
                                input=block.input if hasattr(block, "input") else {},
                            )
                        )

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text"):
                        # Text content delta
                        yield TextChunk(data=delta.text)

                elif event.type == "message_stop":
                    # Message complete
                    final_message = await stream.get_final_message()
                    yield DoneEvent(data=self.parse_response(final_message))

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert tool definitions to Anthropic format.

        Args:
            tools: Tool definitions in motoko format

        Returns:
            Anthropic-formatted tool list
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tools
        ]

    def format_messages(self, messages: list[Message]) -> list[MessageParam]:
        """Convert messages to Anthropic format.

        Args:
            messages: Messages in motoko format

        Returns:
            Anthropic-formatted message list
        """
        api_messages = []

        for msg in messages:
            # Convert message content
            if isinstance(msg.content, str):
                # Simple text message
                api_messages.append({"role": msg.role.value, "content": msg.content})
            else:
                # Message with content blocks
                content_blocks = []
                for block in msg.content:
                    if isinstance(block, TextContent):
                        content_blocks.append({"type": "text", "text": block.text})
                    elif isinstance(block, ToolUse):
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                    elif isinstance(block, ToolResult):
                        content_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": block.content,
                        })

                api_messages.append({"role": msg.role.value, "content": content_blocks})

        return api_messages

    def parse_response(self, response: AnthropicMessage) -> ModelResponse:
        """Convert Anthropic response to unified format.

        Args:
            response: Anthropic API response

        Returns:
            ModelResponse in motoko format
        """
        # Parse content blocks
        content_blocks = []
        for block in response.content:
            if isinstance(block, TextBlock):
                content_blocks.append(TextContent(text=block.text))
            elif isinstance(block, ToolUseBlock):
                content_blocks.append(
                    ToolUse(id=block.id, name=block.name, input=block.input)
                )

        # Map stop reason
        stop_reason_map = {
            "end_turn": StopReason.END_TURN,
            "tool_use": StopReason.TOOL_USE,
            "max_tokens": StopReason.MAX_TOKENS,
            "stop_sequence": StopReason.STOP_SEQUENCE,
        }
        stop_reason = stop_reason_map.get(response.stop_reason, StopReason.END_TURN)

        # Build usage dict
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        return ModelResponse(
            content=content_blocks,
            stop_reason=stop_reason,
            model=response.model,
            usage=usage,
            metadata={"id": response.id, "role": response.role},
        )
