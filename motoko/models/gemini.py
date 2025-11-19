"""Google Gemini model implementation."""

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import google.generativeai as genai

logger = logging.getLogger(__name__)
from google.generativeai.types import (
    ContentDict,
    FunctionDeclaration,
    GenerateContentResponse,
    Tool,
)

from ..types import (
    DoneEvent,
    Message,
    MessageRole,
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


class GeminiModel(BaseModel):
    """Google Gemini model implementation.

    Supports Gemini models: gemini-2.0-flash, gemini-1.5-pro, etc.
    """

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-exp",
        api_key: str | None = None,
        **kwargs: Any,
    ):
        """Initialize Gemini model.

        Args:
            model_name: Gemini model name (default: gemini-2.0-flash-exp)
            api_key: Google API key (if None, uses GOOGLE_API_KEY env var)
            **kwargs: Additional parameters (temperature, top_p, etc.)
        """
        super().__init__(model_name, api_key, **kwargs)

        # Get API key from parameter or environment
        # Check both GEMINI_API_KEY and GOOGLE_API_KEY for compatibility
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key required. Set GEMINI_API_KEY or GOOGLE_API_KEY env var or pass api_key parameter."
            )

        # Configure SDK
        genai.configure(api_key=self.api_key)

        # Create model
        generation_config = {}
        if "temperature" in kwargs:
            generation_config["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            generation_config["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            generation_config["top_k"] = kwargs["top_k"]
        if "max_output_tokens" in kwargs:
            generation_config["max_output_tokens"] = kwargs["max_output_tokens"]

        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config if generation_config else None,
        )

        # Default parameters
        self.temperature = kwargs.get("temperature", 1.0)

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Send chat request to Gemini.

        Args:
            messages: Conversation history
            tools: Available tools
            system: System prompt
            **kwargs: Additional parameters

        Returns:
            ModelResponse with unified format
        """
        # Format messages for Gemini API
        api_messages = self.format_messages(messages)

        # Format tools if provided
        api_tools = self.format_tools(tools) if tools else None

        # Create chat session or single generation
        if system:
            # Prepend system message
            api_messages.insert(0, {"role": "user", "parts": [{"text": system}]})
            api_messages.insert(1, {
                "role": "model",
                "parts": [{"text": "Understood. I'll follow these instructions."}],
            })

        # Generate content
        if api_tools:
            response = self.model.generate_content(
                contents=api_messages, tools=api_tools, **kwargs
            )
        else:
            response = self.model.generate_content(contents=api_messages, **kwargs)

        # Parse response to unified format
        return self.parse_response(response)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Stream chat response from Gemini.

        Args:
            messages: Conversation history
            tools: Available tools
            system: System prompt
            **kwargs: Additional parameters

        Yields:
            StreamEvent objects (TextChunk, ToolStart, etc.)
        """
        # Format messages for Gemini API
        api_messages = self.format_messages(messages)

        # Format tools if provided
        api_tools = self.format_tools(tools) if tools else None

        # Add system message if provided
        if system:
            api_messages.insert(0, {"role": "user", "parts": [{"text": system}]})
            api_messages.insert(1, {
                "role": "model",
                "parts": [{"text": "Understood. I'll follow these instructions."}],
            })

        # Stream response
        if api_tools:
            response_stream = self.model.generate_content(
                contents=api_messages, tools=api_tools, stream=True, **kwargs
            )
        else:
            response_stream = self.model.generate_content(
                contents=api_messages, stream=True, **kwargs
            )

        # Process chunks
        for chunk in response_stream:
            # Check for function calls and text in parts
            if hasattr(chunk, "candidates") and chunk.candidates:
                for candidate in chunk.candidates:
                    if hasattr(candidate, "content") and candidate.content.parts:
                        for part in candidate.content.parts:
                            # Check for text content first
                            if hasattr(part, "text") and part.text:
                                yield TextChunk(data=part.text)

                            # Also check for function call (parts can have both!)
                            if hasattr(part, "function_call"):
                                fc = part.function_call
                                # Skip function calls with empty names (Gemini bug)
                                if fc.name and fc.name.strip():
                                    # Convert function call to tool use
                                    tool_use = ToolUse(
                                        id=f"tool_{hash(fc.name)}",  # Gemini doesn't provide IDs
                                        name=fc.name,
                                        input=dict(fc.args) if fc.args else {},
                                    )
                                    yield ToolStart(data=tool_use)

        # Signal done
        # Note: We need to get the final response for metadata
        # This is a limitation of streaming - we reconstruct it
        final_response = ModelResponse(
            content=[TextContent(text="")],  # Will be filled by accumulated chunks
            stop_reason=StopReason.END_TURN,
            model=self.model_name,
            usage={},
        )
        yield DoneEvent(data=final_response)

    def format_tools(self, tools: list[ToolDefinition]) -> list[Tool]:
        """Convert tool definitions to Gemini format.

        Args:
            tools: Tool definitions in motoko format

        Returns:
            Gemini-formatted tool list
        """
        function_declarations = []
        for tool in tools:
            # Convert JSON schema to Gemini function declaration
            function_declarations.append(
                FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.input_schema,
                )
            )

        return [Tool(function_declarations=function_declarations)]

    def format_messages(self, messages: list[Message]) -> list[ContentDict]:
        """Convert messages to Gemini format.

        Args:
            messages: Messages in motoko format

        Returns:
            Gemini-formatted message list
        """
        api_messages = []

        for msg in messages:
            # Map role (Gemini uses "user" and "model" instead of "assistant")
            role = "model" if msg.role == MessageRole.ASSISTANT else "user"

            # Convert content
            if isinstance(msg.content, str):
                # Simple text message
                api_messages.append({"role": role, "parts": [{"text": msg.content}]})
            else:
                # Message with content blocks
                parts = []
                for block in msg.content:
                    if isinstance(block, TextContent):
                        parts.append({"text": block.text})
                    elif isinstance(block, ToolUse):
                        # Gemini represents tool use as function_call
                        # This is for the model's output
                        parts.append({
                            "function_call": {
                                "name": block.name,
                                "args": block.input,
                            }
                        })
                    elif isinstance(block, ToolResult):
                        # Gemini represents tool results as function_response
                        parts.append({
                            "function_response": {
                                "name": "tool_result",  # Placeholder
                                "response": {"content": block.content},
                            }
                        })

                if parts:
                    api_messages.append({"role": role, "parts": parts})

        return api_messages

    def parse_response(self, response: GenerateContentResponse) -> ModelResponse:
        """Convert Gemini response to unified format.

        Args:
            response: Gemini API response

        Returns:
            ModelResponse in motoko format
        """
        content_blocks = []

        # Parse candidates
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    # Text content
                    if hasattr(part, "text") and part.text:
                        content_blocks.append(TextContent(text=part.text))

                    # Function call (tool use)
                    if hasattr(part, "function_call"):
                        fc = part.function_call
                        # Skip function calls with empty names (Gemini bug)
                        if fc.name and fc.name.strip():
                            content_blocks.append(
                                ToolUse(
                                    id=f"tool_{hash(fc.name)}",  # Gemini doesn't provide IDs
                                    name=fc.name,
                                    input=dict(fc.args) if fc.args else {},
                                )
                            )

        # Determine stop reason
        stop_reason = StopReason.END_TURN
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
            if finish_reason == 1:  # STOP
                stop_reason = StopReason.END_TURN
            elif finish_reason == 2:  # MAX_TOKENS
                stop_reason = StopReason.MAX_TOKENS

        # Build usage dict (if available)
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "input_tokens": response.usage_metadata.prompt_token_count,
                "output_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count,
            }

        return ModelResponse(
            content=content_blocks,
            stop_reason=stop_reason,
            model=self.model_name,
            usage=usage,
            metadata={},
        )
