"""MCP server for library file management."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import LibraryManager from major without triggering major's __init__.py
# (which pulls in heavy dependencies like claude_agent_sdk)
import importlib.util

_library_module_path = str(
    Path(__file__).parent.parent.parent.parent / "major" / "src" / "major" / "library.py"
)
_spec = importlib.util.spec_from_file_location("major_library", _library_module_path)
_library_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_library_module)
LibraryManager = _library_module.LibraryManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("library-mcp")

# Create MCP server
server = Server("library")

# Library manager instance (initialized from WORKSPACE_PATH env var)
_library_manager: LibraryManager | None = None


def get_library_manager() -> LibraryManager:
    """Get or create LibraryManager instance."""
    global _library_manager
    if _library_manager is None:
        cwd = os.getcwd()
        env_workspace = os.environ.get("WORKSPACE_PATH")
        workspace_path = env_workspace or cwd

        logger.info(f"[LIBRARY] cwd: {cwd}")
        logger.info(f"[LIBRARY] WORKSPACE_PATH env: {env_workspace}")
        logger.info(f"[LIBRARY] Using workspace: {workspace_path}")

        _library_manager = LibraryManager(workspace_path)
        logger.info(f"[LIBRARY] LibraryManager initialized")
    return _library_manager


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="add_to_library",
            description="Add text content as a new library file. Use this when the user pastes text, shares content, or asks to save something to their library.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text content to save",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Filename for the content (e.g., 'meeting-notes.md', 'recipe.txt')",
                    },
                    "content_type": {
                        "type": "string",
                        "description": "MIME type (default: text/markdown). Use text/plain for plain text.",
                    },
                },
                "required": ["content", "filename"],
            },
        ),
        Tool(
            name="list_library_files",
            description="List all files in the library with their metadata (id, filename, status, size, dates).",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: pending, processing, complete, or failed (optional)",
                    },
                },
            },
        ),
        Tool(
            name="get_library_file",
            description="Get a specific library file's metadata and extracted content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The file ID",
                    },
                },
                "required": ["file_id"],
            },
        ),
        Tool(
            name="search_library",
            description="Search library files by filename or extracted content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to match against filenames and content",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="delete_library_file",
            description="Delete a file from the library.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The file ID to delete",
                    },
                },
                "required": ["file_id"],
            },
        ),
        Tool(
            name="import_google_doc",
            description="Import a Google Doc into the library by URL. The doc must be shared as 'anyone with the link can view'. If the doc is private, ask the user to share it or paste the content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Google Docs URL (e.g., https://docs.google.com/document/d/DOC_ID/edit)",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional filename override. If not provided, uses the doc title.",
                    },
                },
                "required": ["url"],
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
    manager = get_library_manager()

    if name == "add_to_library":
        return _add_to_library(
            manager,
            arguments["content"],
            arguments["filename"],
            arguments.get("content_type", "text/markdown"),
        )

    elif name == "list_library_files":
        return _list_files(manager, arguments.get("status"))

    elif name == "get_library_file":
        return _get_file(manager, arguments["file_id"])

    elif name == "search_library":
        return _search_files(manager, arguments["query"])

    elif name == "delete_library_file":
        return _delete_file(manager, arguments["file_id"])

    elif name == "import_google_doc":
        return _import_google_doc(
            manager,
            arguments["url"],
            arguments.get("filename"),
        )

    else:
        raise ValueError(f"Unknown tool: {name}")


def _add_to_library(
    manager: LibraryManager,
    content: str,
    filename: str,
    content_type: str,
) -> dict[str, Any]:
    """Add text content to the library."""
    file_id = uuid.uuid4().hex[:12]

    # Save the file
    library_file = manager.save_uploaded_file(
        file_id=file_id,
        filename=filename,
        content=content.encode("utf-8"),
        content_type=content_type,
    )

    # Process (extract content)
    library_file = manager.process_file(file_id)

    return {
        "success": True,
        "file": library_file.to_dict(),
        "message": f"Added '{filename}' to library (id: {file_id})",
    }


def _list_files(
    manager: LibraryManager,
    status: str | None,
) -> dict[str, Any]:
    """List library files with optional status filter."""
    files = manager.list_files()

    if status:
        files = [f for f in files if f.status == status]

    return {
        "success": True,
        "count": len(files),
        "files": [f.to_dict() for f in files],
    }


def _get_file(
    manager: LibraryManager,
    file_id: str,
) -> dict[str, Any]:
    """Get file metadata and extracted content."""
    library_file = manager.get_file(file_id)

    if not library_file:
        return {
            "success": False,
            "error": f"File not found: {file_id}",
        }

    result = {
        "success": True,
        "file": library_file.to_dict(),
    }

    # Include extracted content if available
    extracted = manager.get_extracted_content(file_id)
    if extracted:
        result["extracted_content"] = extracted

    # Include extra metadata if available
    extra = manager.get_extra_metadata(file_id)
    if extra:
        result["extra_metadata"] = extra

    return result


def _search_files(
    manager: LibraryManager,
    query: str,
) -> dict[str, Any]:
    """Search library files by filename or content."""
    query_lower = query.lower()
    files = manager.list_files()
    matches = []

    for f in files:
        # Match against filename
        if query_lower in f.filename.lower():
            matches.append({"file": f.to_dict(), "match": "filename"})
            continue

        # Match against extracted content
        extracted = manager.get_extracted_content(f.id)
        if extracted and query_lower in extracted.lower():
            # Include a snippet around the match
            idx = extracted.lower().index(query_lower)
            start = max(0, idx - 100)
            end = min(len(extracted), idx + len(query) + 100)
            snippet = extracted[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(extracted):
                snippet = snippet + "..."
            matches.append({"file": f.to_dict(), "match": "content", "snippet": snippet})

    return {
        "success": True,
        "query": query,
        "count": len(matches),
        "results": matches,
    }


def _delete_file(
    manager: LibraryManager,
    file_id: str,
) -> dict[str, Any]:
    """Delete a library file."""
    deleted = manager.delete_file(file_id)

    if deleted:
        return {
            "success": True,
            "message": f"Deleted file: {file_id}",
        }
    else:
        return {
            "success": False,
            "error": f"File not found: {file_id}",
        }


_GOOGLE_DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def _extract_google_doc_id(url: str) -> str:
    """Extract Google Doc ID from a URL or raw ID string."""
    match = _GOOGLE_DOC_ID_RE.search(url)
    if match:
        return match.group(1)
    # Treat as raw doc ID if it looks like one (alphanumeric, hyphens, underscores)
    stripped = url.strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]+", stripped):
        return stripped
    raise ValueError(f"Could not extract Google Doc ID from: {url}")


def _fetch_google_doc_title(doc_id: str) -> str | None:
    """Best-effort fetch of the doc title from the HTML page."""
    try:
        resp = httpx.get(
            f"https://docs.google.com/document/d/{doc_id}/edit",
            follow_redirects=True,
            timeout=10,
        )
        if resp.status_code == 200:
            match = re.search(r"<title>(.+?)(?:\s*-\s*Google Docs)?</title>", resp.text)
            if match:
                title = match.group(1).strip()
                if title:
                    return title
    except Exception:
        pass
    return None


def _import_google_doc(
    manager: LibraryManager,
    url: str,
    filename: str | None = None,
) -> dict[str, Any]:
    """Import a publicly-shared Google Doc into the library."""
    doc_id = _extract_google_doc_id(url)

    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    response = httpx.get(export_url, follow_redirects=True, timeout=30)

    if response.status_code != 200:
        return {
            "success": False,
            "error": (
                "Could not access this Google Doc. It may be private. "
                "Ask the user to either share it with 'anyone with the link can view', "
                "or paste the content directly."
            ),
        }

    content = response.text

    if not filename:
        filename = _fetch_google_doc_title(doc_id) or f"google-doc-{doc_id[:8]}"
    if not filename.endswith((".md", ".txt")):
        filename += ".md"

    file_id = uuid.uuid4().hex[:12]
    library_file = manager.save_uploaded_file(
        file_id=file_id,
        filename=filename,
        content=content.encode("utf-8"),
        content_type="text/markdown",
    )
    library_file = manager.process_file(file_id)

    return {
        "success": True,
        "file": library_file.to_dict(),
        "message": f"Imported Google Doc as '{filename}' (id: {file_id})",
        "source_url": url,
    }


def main():
    """Run the MCP server."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Library MCP server")
    parser.add_argument("--workspace", help="Workspace path (overrides WORKSPACE_PATH env var)")
    args = parser.parse_args()

    # If --workspace provided, set it as env var
    if args.workspace:
        workspace = Path(args.workspace)
        if not workspace.is_absolute():
            workspace = workspace.resolve()
        os.environ["WORKSPACE_PATH"] = str(workspace)
        logger.info(f"[LIBRARY] --workspace arg set WORKSPACE_PATH to: {workspace}")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
