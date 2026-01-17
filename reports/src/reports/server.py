"""MCP server for report storage and retrieval."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from reports.report_tools import ReportTools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reports")

# Create MCP server
server = Server("reports")

# Report tools instance (initialized from WORKSPACE_PATH env var)
_report_tools: ReportTools | None = None


def get_report_tools() -> ReportTools:
    """Get or create ReportTools instance."""
    global _report_tools
    if _report_tools is None:
        cwd = os.getcwd()
        env_workspace = os.environ.get("WORKSPACE_PATH")
        workspace_path = env_workspace or cwd

        logger.info(f"[REPORTS] cwd: {cwd}")
        logger.info(f"[REPORTS] WORKSPACE_PATH env: {env_workspace}")
        logger.info(f"[REPORTS] Using workspace: {workspace_path}")

        _report_tools = ReportTools(workspace_path)
        logger.info(f"[REPORTS] ReportTools initialized")
    return _report_tools


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="list_reports",
            description="List available report types and their versions. Returns report types with dates, counts, and metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "description": "Filter to specific report type (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum versions to return per type (default 50)",
                    },
                },
            },
        ),
        Tool(
            name="get_report",
            description="Get a specific report by type and date. Returns latest if no date specified.",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "description": "Report type (e.g., 'deliverability-analysis')",
                    },
                    "date": {
                        "type": "string",
                        "description": "Report date (YYYY-MM-DD). Returns latest if not specified.",
                    },
                },
                "required": ["report_type"],
            },
        ),
        Tool(
            name="save_report",
            description="Save a report. Auto-dates to today if no date specified.",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "description": "Report type (e.g., 'deliverability-analysis')",
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content of the report",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata (title, description, skill_name)",
                    },
                    "date": {
                        "type": "string",
                        "description": "Report date (YYYY-MM-DD). Defaults to today.",
                    },
                },
                "required": ["report_type", "content"],
            },
        ),
        Tool(
            name="compare_reports",
            description="Compare two reports of the same type. Returns both reports for comparison.",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "description": "Report type",
                    },
                    "date1": {
                        "type": "string",
                        "description": "First report date (YYYY-MM-DD)",
                    },
                    "date2": {
                        "type": "string",
                        "description": "Second report date (YYYY-MM-DD)",
                    },
                },
                "required": ["report_type", "date1", "date2"],
            },
        ),
        Tool(
            name="get_recent_reports",
            description="Get the N most recent reports of a type. Useful for trend analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "description": "Report type",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of reports to return (default 4)",
                    },
                },
                "required": ["report_type"],
            },
        ),
        Tool(
            name="debug_info",
            description="Get debug information about the reports server configuration.",
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
    tools = get_report_tools()

    if name == "list_reports":
        return tools.list_reports(
            arguments.get("report_type"),
            arguments.get("limit", 50),
        )

    elif name == "get_report":
        return tools.get_report(
            arguments["report_type"],
            arguments.get("date"),
        )

    elif name == "save_report":
        return tools.save_report(
            arguments["report_type"],
            arguments["content"],
            arguments.get("metadata"),
            arguments.get("date"),
        )

    elif name == "compare_reports":
        return tools.compare_reports(
            arguments["report_type"],
            arguments["date1"],
            arguments["date2"],
        )

    elif name == "get_recent_reports":
        return tools.get_recent_reports(
            arguments["report_type"],
            arguments.get("count", 4),
        )

    elif name == "debug_info":
        cwd = os.getcwd()
        env_workspace = os.environ.get("WORKSPACE_PATH")
        workspace_path = env_workspace or cwd
        workspace = Path(workspace_path)
        reports_dir = workspace / "reports"
        return {
            "success": True,
            "cwd": cwd,
            "WORKSPACE_PATH_env": env_workspace,
            "effective_workspace": workspace_path,
            "workspace_exists": workspace.exists(),
            "reports_dir_exists": reports_dir.exists(),
            "report_types": [d.name for d in reports_dir.iterdir() if d.is_dir()] if reports_dir.exists() else [],
        }

    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """Run the MCP server."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Reports MCP server")
    parser.add_argument("--workspace", help="Workspace path (overrides WORKSPACE_PATH env var)")
    args = parser.parse_args()

    # If --workspace provided, set it as env var
    if args.workspace:
        workspace = Path(args.workspace)
        if not workspace.is_absolute():
            workspace = workspace.resolve()
        os.environ["WORKSPACE_PATH"] = str(workspace)
        logger.info(f"[REPORTS] --workspace arg set WORKSPACE_PATH to: {workspace}")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
