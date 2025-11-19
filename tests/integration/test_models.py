"""Integration tests for model implementations.

These tests make real API calls to verify models work correctly.
"""

import pytest

from motoko import Message, MessageRole, create_model


@pytest.mark.integration
def test_anthropic_basic_chat(anthropic_api_key):
    """Test basic Anthropic chat works."""
    model = create_model("claude-sonnet-4-5-20250929")

    messages = [Message(role=MessageRole.USER, content="Say 'Hello, World!' and nothing else.")]

    response = model.chat(messages=messages, system="You follow instructions exactly.")

    assert response.text
    assert "hello" in response.text.lower()
    assert response.model.startswith("claude-sonnet-4")


@pytest.mark.integration
def test_gemini_basic_chat(google_api_key):
    """Test basic Gemini chat works."""
    model = create_model("gemini-3-pro-preview")

    messages = [Message(role=MessageRole.USER, content="Say 'Hello, World!' and nothing else.")]

    response = model.chat(messages=messages, system="You follow instructions exactly.")

    assert response.text
    assert "hello" in response.text.lower()
    assert response.model.startswith("gemini-3")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_anthropic_streaming(anthropic_api_key):
    """Test Anthropic streaming works."""
    model = create_model("claude-sonnet-4-5-20250929")

    messages = [Message(role=MessageRole.USER, content="Count from 1 to 3, one number per line.")]

    chunks = []
    async for event in model.stream(messages=messages):
        if event.type == "text_chunk":
            chunks.append(event.data)

    full_text = "".join(chunks)
    assert full_text
    assert len(chunks) > 1  # Should have multiple chunks


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gemini_streaming(google_api_key):
    """Test Gemini streaming works."""
    model = create_model("gemini-3-pro-preview")

    messages = [Message(role=MessageRole.USER, content="Count from 1 to 3, one number per line.")]

    chunks = []
    async for event in model.stream(messages=messages):
        if event.type == "text_chunk":
            chunks.append(event.data)

    full_text = "".join(chunks)
    assert full_text
    assert len(chunks) >= 1  # Should have at least one chunk (Gemini 3 can be very fast)


@pytest.mark.integration
def test_model_switching(anthropic_api_key, google_api_key):
    """Test switching between models works."""
    prompt = "What is 2+2? Answer with just the number."
    messages = [Message(role=MessageRole.USER, content=prompt)]

    # Test with Anthropic
    claude = create_model("claude-sonnet-4-5-20250929")
    response1 = claude.chat(messages=messages)
    assert response1.text

    # Test with Gemini
    gemini = create_model("gemini-3-pro-preview")
    response2 = gemini.chat(messages=messages)
    assert response2.text

    # Both should mention 4
    assert "4" in response1.text or "four" in response1.text.lower()
    assert "4" in response2.text or "four" in response2.text.lower()
