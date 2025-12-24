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
        cwd = os.getcwd()
        env_workspace = os.environ.get("WORKSPACE_PATH")
        workspace_path = env_workspace or cwd

        logger.info(f"[BATOU] cwd: {cwd}")
        logger.info(f"[BATOU] WORKSPACE_PATH env: {env_workspace}")
        logger.info(f"[BATOU] Using workspace: {workspace_path}")
        logger.info(f"[BATOU] Workspace exists: {Path(workspace_path).exists()}")
        logger.info(f"[BATOU] Workspace contents: {list(Path(workspace_path).iterdir()) if Path(workspace_path).exists() else 'N/A'}")

        _entity_tools = EntityTools(workspace_path)
        logger.info(f"[BATOU] EntityTools initialized")
    return _entity_tools


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="list_entities",
            description="List entities of a given type with optional filtering. Returns entity IDs, titles, status, and paths. By default excludes archived entities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type (e.g., 'tasks', 'notes', 'projects', 'journal')",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (e.g., 'open', 'done', 'archived'). Optional.",
                    },
                    "include_archived": {
                        "type": "boolean",
                        "description": "Include archived entities (default false). Set true to see all entities including archived.",
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
        Tool(
            name="debug_info",
            description="Get debug information about batou's configuration (cwd, workspace path, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="archive_entity",
            description="Archive an entity by moving it to zzz_archive/. Blocks if other active entities reference this one.",
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
            name="unarchive_entity",
            description="Unarchive an entity by moving it back from zzz_archive/ to the main directory.",
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
            name="list_archived_entities",
            description="List archived entities of a given type from zzz_archive/.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type",
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
            name="search_archived",
            description="Search archived entities by text content (case-insensitive substring match).",
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
            arguments.get("include_archived", False),
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

    elif name == "archive_entity":
        return tools.archive_entity(
            arguments["entity_type"],
            arguments["entity_id"],
        )

    elif name == "unarchive_entity":
        return tools.unarchive_entity(
            arguments["entity_type"],
            arguments["entity_id"],
        )

    elif name == "list_archived_entities":
        return tools.list_archived_entities(
            arguments["entity_type"],
            arguments.get("limit", 50),
        )

    elif name == "search_archived":
        return tools.search_archived(
            arguments["query"],
            arguments.get("entity_type"),
            arguments.get("limit", 10),
        )

    elif name == "debug_info":
        cwd = os.getcwd()
        env_workspace = os.environ.get("WORKSPACE_PATH")
        workspace_path = env_workspace or cwd
        workspace = Path(workspace_path)
        return {
            "success": True,
            "cwd": cwd,
            "WORKSPACE_PATH_env": env_workspace,
            "effective_workspace": workspace_path,
            "workspace_exists": workspace.exists(),
            "workspace_contents": [p.name for p in workspace.iterdir()] if workspace.exists() else [],
            "projects_dir_exists": (workspace / "projects").exists(),
            "projects_count": len(list((workspace / "projects").glob("*.md"))) if (workspace / "projects").exists() else 0,
        }

    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """Run the MCP server."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Batou MCP server")
    parser.add_argument("--workspace", help="Workspace path (overrides WORKSPACE_PATH env var)")
    args = parser.parse_args()

    # If --workspace provided, set it as env var so get_entity_tools() picks it up
    if args.workspace:
        # Resolve relative path from original cwd (before uv --directory changed it)
        # Note: This won't work because cwd is already changed. See below.
        workspace = Path(args.workspace)
        if not workspace.is_absolute():
            # Try to resolve - but cwd is wrong at this point
            workspace = workspace.resolve()
        os.environ["WORKSPACE_PATH"] = str(workspace)
        logger.info(f"[BATOU] --workspace arg set WORKSPACE_PATH to: {workspace}")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
