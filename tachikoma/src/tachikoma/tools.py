"""Tool definitions for Tachikoma agent using Claude Agent SDK."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter
import yaml
from claude_agent_sdk import tool, create_sdk_mcp_server


def create_tachikoma_tools(workspace_path: str):
    """Create Tachikoma tools for the given workspace.

    Args:
        workspace_path: Root path of the workspace

    Returns:
        SDK MCP server with all tools
    """
    workspace = Path(workspace_path).resolve()
    decisions_dir = workspace / "decisions"
    summary_path = workspace / ".claude" / "tachikoma-summary.yaml"

    def resolve_path(path: str) -> Path:
        """Resolve a relative path to absolute, ensuring it's within workspace."""
        resolved = (workspace / path).resolve()
        if not str(resolved).startswith(str(workspace)):
            raise ValueError(f"Path escapes workspace: {path}")
        return resolved

    @tool(
        name="read_file",
        description="Read the contents of a file in the workspace",
        input_schema={"path": str}
    )
    async def read_file(args: dict[str, Any]) -> dict:
        """Read a file from the workspace."""
        try:
            file_path = resolve_path(args["path"])
            if not file_path.exists():
                return {"content": [{"type": "text", "text": f"Error: File not found: {args['path']}"}]}
            if file_path.is_dir():
                return {"content": [{"type": "text", "text": f"Error: Path is a directory: {args['path']}"}]}
            content = file_path.read_text()
            return {"content": [{"type": "text", "text": content}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    @tool(
        name="list_directory",
        description="List files and directories at a path",
        input_schema={"path": str}
    )
    async def list_directory(args: dict[str, Any]) -> dict:
        """List contents of a directory."""
        try:
            dir_path = resolve_path(args["path"])
            if not dir_path.exists():
                return {"content": [{"type": "text", "text": f"Error: Directory not found: {args['path']}"}]}
            if not dir_path.is_dir():
                return {"content": [{"type": "text", "text": f"Error: Path is not a directory: {args['path']}"}]}

            entries = []
            for entry in sorted(dir_path.iterdir()):
                entry_type = "d" if entry.is_dir() else "f"
                entries.append(f"[{entry_type}] {entry.name}")
            result = "\n".join(entries) if entries else "(empty directory)"
            return {"content": [{"type": "text", "text": result}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    @tool(
        name="glob_files",
        description="Find files matching a glob pattern",
        input_schema={"pattern": str}
    )
    async def glob_files(args: dict[str, Any]) -> dict:
        """Find files matching a glob pattern."""
        try:
            matches = list(workspace.glob(args["pattern"]))
            if not matches:
                return {"content": [{"type": "text", "text": "(no matches)"}]}

            results = []
            for match in sorted(matches):
                rel_path = match.relative_to(workspace)
                results.append(str(rel_path))
            return {"content": [{"type": "text", "text": "\n".join(results)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    @tool(
        name="write_decision",
        description="Write a decision file to decisions/. Only use this for proposing changes.",
        input_schema={
            "filename": str,
            "title": str,
            "decision_type": str,
            "current_state": str,
            "suggested_change": str,
            "reasoning": str,
            "subject_path": str,
            "suggested_path": str,
            "confidence": float,
        }
    )
    async def write_decision(args: dict[str, Any]) -> dict:
        """Write a decision file to decisions/."""
        try:
            decisions_dir.mkdir(parents=True, exist_ok=True)

            filename = args["filename"]
            if not filename.endswith(".md"):
                filename += ".md"

            file_path = decisions_dir / filename

            # Build frontmatter
            fm = {
                "title": args["title"],
                "status": "pending",
                "decision_type": args["decision_type"],
                "created_at": datetime.now().isoformat(),
            }

            if args.get("subject_path"):
                fm["subject_path"] = args["subject_path"]
            if args.get("suggested_path"):
                fm["suggested_path"] = args["suggested_path"]
            if args.get("confidence"):
                fm["confidence"] = args["confidence"]

            # Build content
            content = f"""## Current State

{args["current_state"]}

## Suggested Change

{args["suggested_change"]}

## Reasoning

{args["reasoning"]}
"""

            # Write file
            post = frontmatter.Post(content, **fm)
            file_path.write_text(frontmatter.dumps(post))

            return {"content": [{"type": "text", "text": f"Created decision: decisions/{filename}"}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    @tool(
        name="update_summary",
        description="Update the .claude/tachikoma-summary.yaml file with observations",
        input_schema={
            "entity_counts": dict,
            "observations": list,
            "pending_decisions": list,
        }
    )
    async def update_summary(args: dict[str, Any]) -> dict:
        """Update the tachikoma summary file."""
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)

            summary = {
                "last_scan": datetime.now().isoformat(),
                "entity_counts": args["entity_counts"],
                "observations": args["observations"],
                "pending_decisions": args["pending_decisions"],
            }

            summary_path.write_text(yaml.dump(summary, default_flow_style=False))

            return {"content": [{"type": "text", "text": "Updated summary: .claude/tachikoma-summary.yaml"}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    # Create and return the SDK MCP server
    return create_sdk_mcp_server(
        name="tachikoma-tools",
        version="0.2.0",
        tools=[read_file, list_directory, glob_files, write_decision, update_summary]
    )
