"""Tachikoma agent using Claude Agent SDK."""

from __future__ import annotations

import logging
import re
from typing import Any

import anyio
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from .prompts import PROMPTS
from .tools import create_tachikoma_tools

logger = logging.getLogger("tachikoma")


class TachikomaAgent:
    """Tachikoma maintenance agent using Claude Agent SDK."""

    def __init__(
        self,
        workspace_path: str,
        cleanup_mode: str,
        model: str = "claude-sonnet-4-20250514",
        max_turns: int = 20,
    ):
        """Initialize the agent.

        Args:
            workspace_path: Path to the workspace to analyze
            cleanup_mode: One of 'schema', 'frontmatter', 'structure'
            model: Anthropic model to use
            max_turns: Maximum conversation turns
        """
        if cleanup_mode not in PROMPTS:
            raise ValueError(f"Invalid cleanup mode: {cleanup_mode}. Must be one of: {list(PROMPTS.keys())}")

        self.workspace_path = workspace_path
        self.cleanup_mode = cleanup_mode
        self.model = model
        self.max_turns = max_turns
        self.system_prompt = PROMPTS[cleanup_mode]

    def run(self) -> dict[str, Any]:
        """Run the agent and return results.

        Returns:
            Summary of the run including decisions created
        """
        return anyio.run(self._run_async)

    async def _run_async(self) -> dict[str, Any]:
        """Async implementation of the agent run."""
        logger.info(f"Starting {self.cleanup_mode} cleanup on {self.workspace_path}")

        # Create tools MCP server
        tools_server = create_tachikoma_tools(self.workspace_path)

        # Build list of allowed tools (all tachikoma tools)
        allowed_tools = [
            "mcp__tachikoma-tools__read_file",
            "mcp__tachikoma-tools__list_directory",
            "mcp__tachikoma-tools__glob_files",
            "mcp__tachikoma-tools__write_decision",
            "mcp__tachikoma-tools__update_summary",
        ]

        # Configure agent options
        options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            max_turns=self.max_turns,
            mcp_servers={"tachikoma-tools": tools_server},
            allowed_tools=allowed_tools,
            permission_mode="acceptEdits",
            cwd=self.workspace_path,
        )

        decisions_created = []
        turns = 0
        final_text = ""

        prompt = (
            f"Analyze the workspace at {self.workspace_path} and run {self.cleanup_mode} cleanup. "
            f"Start by exploring the workspace structure, then identify issues and create decisions."
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    turns += 1
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text = block.text[:200] + "..." if len(block.text) > 200 else block.text
                            logger.info(f"Agent: {text}")
                            final_text = block.text
                        elif isinstance(block, ToolUseBlock):
                            # Check if write_decision was called
                            if block.name == "mcp__tachikoma-tools__write_decision":
                                filename = block.input.get("filename", "unknown")
                                if not filename.endswith(".md"):
                                    filename += ".md"
                                decisions_created.append(filename)
                                logger.debug(f"Decision created: {filename}")

                elif isinstance(message, ResultMessage):
                    # Final message with stats
                    logger.info(f"Completed: {message.num_turns} turns, error={message.is_error}")
                    if message.result:
                        final_text = message.result

        logger.info(f"Agent finished: {final_text[:200] if final_text else '(no final text)'}...")

        return {
            "workspace": self.workspace_path,
            "cleanup_mode": self.cleanup_mode,
            "turns": turns,
            "decisions_created": decisions_created,
        }
