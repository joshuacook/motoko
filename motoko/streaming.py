"""Streaming utilities for Server-Sent Events (SSE)."""

import json
from collections.abc import AsyncIterator
from typing import Any

from .types import StreamEvent


def format_sse(event: StreamEvent) -> str:
    """Format a StreamEvent as Server-Sent Event (SSE).

    Args:
        event: StreamEvent to format

    Returns:
        SSE-formatted string

    Example:
        >>> event = TextChunk(data="Hello")
        >>> print(format_sse(event))
        event: text_chunk
        data: {"type":"text_chunk","data":"Hello"}

    """
    # Build SSE message
    lines = []

    # Event type
    lines.append(f"event: {event.type}")

    # Data payload
    data_dict = {"type": event.type, "data": _serialize_data(event.data)}

    # Add metadata if present
    if event.metadata:
        data_dict["metadata"] = event.metadata

    lines.append(f"data: {json.dumps(data_dict)}")

    # SSE messages end with double newline
    return "\n".join(lines) + "\n\n"


def _serialize_data(data: Any) -> Any:
    """Serialize event data to JSON-compatible format.

    Args:
        data: Event data

    Returns:
        JSON-serializable data
    """
    # Handle strings
    if isinstance(data, str):
        return data

    # Handle objects with to_dict method
    if hasattr(data, "to_dict"):
        return data.to_dict()

    # Handle dataclasses
    if hasattr(data, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(data)

    # Fallback to string representation
    return str(data)


async def stream_to_sse(
    stream: AsyncIterator[StreamEvent],
) -> AsyncIterator[str]:
    """Convert StreamEvent iterator to SSE-formatted strings.

    Args:
        stream: Stream of events

    Yields:
        SSE-formatted strings

    Example:
        >>> async for sse_message in stream_to_sse(agent.stream("Hello")):
        ...     print(sse_message)
    """
    async for event in stream:
        yield format_sse(event)


def create_sse_response_fastapi(
    stream: AsyncIterator[StreamEvent],
) -> AsyncIterator[str]:
    """Create FastAPI StreamingResponse-compatible generator.

    Args:
        stream: Stream of events

    Returns:
        Generator for StreamingResponse

    Example:
        ```python
        from fastapi import FastAPI
        from fastapi.responses import StreamingResponse

        app = FastAPI()

        @app.post("/stream")
        async def stream_endpoint(message: str):
            events = agent.stream(message)
            return StreamingResponse(
                create_sse_response_fastapi(events),
                media_type="text/event-stream"
            )
        ```
    """
    return stream_to_sse(stream)


def parse_sse_event(sse_message: str) -> dict[str, Any]:
    """Parse an SSE message into a dictionary.

    Args:
        sse_message: SSE-formatted string

    Returns:
        Parsed event dictionary

    Example:
        >>> msg = 'event: text_chunk\\ndata: {"type":"text_chunk","data":"Hi"}\\n\\n'
        >>> parse_sse_event(msg)
        {'event': 'text_chunk', 'data': {'type': 'text_chunk', 'data': 'Hi'}}
    """
    lines = sse_message.strip().split("\n")
    result = {}

    for line in lines:
        if line.startswith("event:"):
            result["event"] = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
            try:
                result["data"] = json.loads(data_str)
            except json.JSONDecodeError:
                result["data"] = data_str

    return result


class SSEClient:
    """Client for consuming SSE streams.

    Example:
        ```python
        async def consume_stream(url: str):
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json={"message": "Hello"}) as response:
                    sse_client = SSEClient()
                    async for line in response.aiter_lines():
                        event = sse_client.process_line(line)
                        if event:
                            print(event)
        ```
    """

    def __init__(self):
        """Initialize SSE client."""
        self.buffer = []

    def process_line(self, line: str) -> dict[str, Any] | None:
        """Process a line from SSE stream.

        Args:
            line: Line from stream

        Returns:
            Parsed event dict if complete, None if incomplete
        """
        # Empty line signals end of event
        if not line.strip():
            if self.buffer:
                event = parse_sse_event("\n".join(self.buffer))
                self.buffer = []
                return event
            return None

        # Accumulate lines
        self.buffer.append(line)
        return None
