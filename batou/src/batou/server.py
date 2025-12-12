"""MCP server for structured entity operations."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from batou.entities import EntityTools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("batou")

# Create MCP server
server = Server("batou")

# Entity tools instance (initialized from WORKSPACE_PATH env var)
_entity_tools: EntityTools | None = None


def get_entity_tools() -> EntityTools:
    """Get or create EntityTools instance."""
    global _entity_tools
    if _entity_tools is None:
        workspace_path = os.environ.get("WORKSPACE_PATH", os.getcwd())
        _entity_tools = EntityTools(workspace_path)
        logger.info(f"Initialized EntityTools for workspace: {workspace_path}")
    return _entity_tools


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="list_entities",
            description="List entities of a given type with optional filtering. Returns entity IDs, titles, status, and paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type (e.g., 'tasks', 'notes', 'projects', 'journal')",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (e.g., 'open', 'done'). Optional.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 50)",
                    },
                },
                "required": ["entity_type"],
            },
        ),
        Tool(
            name="get_entity",
            description="Get a specific entity by type and ID. Returns frontmatter and full content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID (filename without .md extension)",
                    },
                },
                "required": ["entity_type", "entity_id"],
            },
        ),
        Tool(
            name="create_entity",
            description="Create a new entity with frontmatter and content. Applies schema defaults and validates required fields.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type",
                    },
                    "frontmatter": {
                        "type": "object",
                        "description": "Entity frontmatter (title, status, slug, etc.)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content body",
                    },
                },
                "required": ["entity_type", "frontmatter", "content"],
            },
        ),
        Tool(
            name="update_entity",
            description="Update an existing entity's frontmatter and/or content. Frontmatter is merged with existing values.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID",
                    },
                    "frontmatter": {
                        "type": "object",
                        "description": "Frontmatter updates (merged with existing)",
                    },
                    "content": {
                        "type": "string",
                        "description": "New content (replaces existing if provided)",
                    },
                },
                "required": ["entity_type", "entity_id"],
            },
        ),
        Tool(
            name="delete_entity",
            description="Delete an entity by type and ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID",
                    },
                },
                "required": ["entity_type", "entity_id"],
            },
        ),
        Tool(
            name="search_entities",
            description="Search entities by text content (case-insensitive substring match).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Filter to specific entity type (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 10)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_schema",
            description="Get information about the workspace schema, including defined entity types and their configuration.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        result = _dispatch_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        error_result = {
            "success": False,
            "error": str(e),
        }
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch tool call to appropriate handler."""
    tools = get_entity_tools()

    if name == "list_entities":
        return tools.list_entities(
            arguments["entity_type"],
            arguments.get("status"),
            arguments.get("limit", 50),
        )

    elif name == "get_entity":
        return tools.get_entity(
            arguments["entity_type"],
            arguments["entity_id"],
        )

    elif name == "create_entity":
        return tools.create_entity(
            arguments["entity_type"],
            arguments["frontmatter"],
            arguments["content"],
        )

    elif name == "update_entity":
        return tools.update_entity(
            arguments["entity_type"],
            arguments["entity_id"],
            arguments.get("frontmatter"),
            arguments.get("content"),
        )

    elif name == "delete_entity":
        return tools.delete_entity(
            arguments["entity_type"],
            arguments["entity_id"],
        )

    elif name == "search_entities":
        return tools.search_entities(
            arguments["query"],
            arguments.get("entity_type"),
            arguments.get("limit", 10),
        )

    elif name == "get_schema":
        return tools.get_schema_info()

    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """Run the MCP server."""
    import asyncio

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
