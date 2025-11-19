"""Shared fixtures for integration tests."""

import os

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires API keys)"
    )


@pytest.fixture(scope="session")
def anthropic_api_key():
    """Get Anthropic API key from environment."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def google_api_key():
    """Get Google API key from environment."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def has_api_keys():
    """Check if both API keys are available."""
    return bool(os.getenv("ANTHROPIC_API_KEY") and os.getenv("GEMINI_API_KEY"))
