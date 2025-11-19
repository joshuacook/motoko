"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_workspace(tmp_path):
    """Create a temporary workspace for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create some sample files
    (workspace / "test.txt").write_text("Hello, world!")
    (workspace / "data.json").write_text('{"key": "value"}')

    return workspace
