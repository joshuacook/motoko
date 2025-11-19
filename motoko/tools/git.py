"""Git operation tools."""

import subprocess
from pathlib import Path
from typing import Any

from ..types import ToolResult
from .base import BaseTool


class GitStatusTool(BaseTool):
    """Get git repository status."""

    name = "git_status"
    description = "Get the status of a git repository"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory (git repo root)
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to git repository (default: workspace)",
                }
            },
        }

    def execute(self, path: str | None = None) -> ToolResult:
        """Execute git status.

        Args:
            path: Repository path

        Returns:
            ToolResult with git status
        """
        try:
            repo_path = Path(path) if path else self.workspace

            # Run git status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return self._create_result(
                    content=f"Git error: {result.stderr}",
                    is_error=True,
                    metadata={"action": "git_status", "path": str(repo_path)},
                )

            # Also get branch info
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

            # Format output
            status_output = result.stdout.strip()
            if status_output:
                content = f"Branch: {branch}\n\n{status_output}"
            else:
                content = f"Branch: {branch}\n\nWorking tree clean"

            metadata = {
                "action": "git_status",
                "path": str(repo_path),
                "branch": branch,
                "clean": not bool(status_output),
            }

            return self._create_result(content=content, metadata=metadata)

        except subprocess.TimeoutExpired:
            return self._create_result(
                content="Error: Git command timed out",
                is_error=True,
                metadata={"action": "git_status"},
            )
        except Exception as e:
            return self._create_result(
                content=f"Error running git status: {str(e)}",
                is_error=True,
                metadata={"action": "git_status"},
            )


class GitDiffTool(BaseTool):
    """Show git diff."""

    name = "git_diff"
    description = "Show changes in git repository"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory (git repo root)
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to git repository (default: workspace)",
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show staged changes only (default: false)",
                },
                "file": {
                    "type": "string",
                    "description": "Specific file to diff",
                },
            },
        }

    def execute(
        self, path: str | None = None, staged: bool = False, file: str | None = None
    ) -> ToolResult:
        """Execute git diff.

        Args:
            path: Repository path
            staged: Show staged changes
            file: Specific file to diff

        Returns:
            ToolResult with git diff
        """
        try:
            repo_path = Path(path) if path else self.workspace

            # Build git diff command
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--staged")
            if file:
                cmd.append(file)

            # Run git diff
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return self._create_result(
                    content=f"Git error: {result.stderr}",
                    is_error=True,
                    metadata={"action": "git_diff", "path": str(repo_path)},
                )

            content = result.stdout.strip() or "No changes"

            metadata = {
                "action": "git_diff",
                "path": str(repo_path),
                "staged": staged,
                "file": file,
            }

            return self._create_result(content=content, metadata=metadata)

        except subprocess.TimeoutExpired:
            return self._create_result(
                content="Error: Git command timed out",
                is_error=True,
                metadata={"action": "git_diff"},
            )
        except Exception as e:
            return self._create_result(
                content=f"Error running git diff: {str(e)}",
                is_error=True,
                metadata={"action": "git_diff"},
            )


class GitCommitTool(BaseTool):
    """Create a git commit."""

    name = "git_commit"
    description = "Create a git commit with a message"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory (git repo root)
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to stage and commit (empty = all changes)",
                },
                "path": {
                    "type": "string",
                    "description": "Path to git repository (default: workspace)",
                },
            },
            "required": ["message"],
        }

    def execute(
        self,
        message: str,
        files: list[str] | None = None,
        path: str | None = None,
    ) -> ToolResult:
        """Execute git commit.

        Args:
            message: Commit message
            files: Files to commit
            path: Repository path

        Returns:
            ToolResult with commit info
        """
        try:
            repo_path = Path(path) if path else self.workspace

            # Stage files
            if files:
                for file in files:
                    subprocess.run(
                        ["git", "add", file],
                        cwd=repo_path,
                        capture_output=True,
                        timeout=30,
                    )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=30,
                )

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Check if it's because there's nothing to commit
                if "nothing to commit" in result.stdout.lower():
                    content = "Nothing to commit, working tree clean"
                else:
                    return self._create_result(
                        content=f"Git error: {result.stderr}",
                        is_error=True,
                        metadata={"action": "git_commit"},
                    )
            else:
                content = result.stdout.strip()

            metadata = {
                "action": "git_commit",
                "path": str(repo_path),
                "files": files or "all",
            }

            return self._create_result(content=content, metadata=metadata)

        except subprocess.TimeoutExpired:
            return self._create_result(
                content="Error: Git command timed out",
                is_error=True,
                metadata={"action": "git_commit"},
            )
        except Exception as e:
            return self._create_result(
                content=f"Error running git commit: {str(e)}",
                is_error=True,
                metadata={"action": "git_commit"},
            )
