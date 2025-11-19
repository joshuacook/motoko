"""File operation tools."""

import re
from pathlib import Path
from typing import Any

from ..types import ToolResult
from .base import BaseTool


class ReadFileTool(BaseTool):
    """Read contents of a file.

    Supports reading with optional offset and limit for large files.
    """

    name = "read_file"
    description = "Read contents of a file from the filesystem"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory for file operations
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to read",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-indexed)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read",
                },
            },
            "required": ["file_path"],
        }

    def execute(
        self,
        file_path: str,
        offset: int | None = None,
        limit: int | None = None,
    ) -> ToolResult:
        """Execute file read.

        Args:
            file_path: Path to file
            offset: Starting line (1-indexed)
            limit: Max lines to read

        Returns:
            ToolResult with file contents
        """
        try:
            # Resolve path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.workspace / path

            # Check file exists
            if not path.exists():
                return self._create_result(
                    content=f"Error: File not found: {path}",
                    is_error=True,
                    metadata={"action": "read", "target": str(path)},
                )

            # Read file
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()

            # Apply offset and limit
            total_lines = len(lines)
            start = (offset - 1) if offset else 0
            end = (start + limit) if limit else len(lines)

            selected_lines = lines[start:end]

            # Format with line numbers
            content = "".join(
                f"{i + start + 1:6d}→{line}" for i, line in enumerate(selected_lines)
            )

            metadata = {
                "action": "read",
                "target": str(path),
                "total_lines": total_lines,
                "returned_lines": len(selected_lines),
            }

            return self._create_result(content=content, metadata=metadata)

        except Exception as e:
            return self._create_result(
                content=f"Error reading file: {str(e)}",
                is_error=True,
                metadata={"action": "read", "target": file_path},
            )


class WriteFileTool(BaseTool):
    """Write or overwrite a file."""

    name = "write_file"
    description = "Write content to a file (creates or overwrites)"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory for file operations
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        }

    def execute(self, file_path: str, content: str) -> ToolResult:
        """Execute file write.

        Args:
            file_path: Path to file
            content: Content to write

        Returns:
            ToolResult with success message
        """
        try:
            # Resolve path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.workspace / path

            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            lines_written = len(content.splitlines())
            bytes_written = len(content.encode("utf-8"))

            # Auto-commit if file is in data/ directory
            commit_msg = None
            try:
                # Check if path is under data/ directory
                relative_path = path.relative_to(self.workspace)
                if relative_path.parts[0] == "data":
                    # Auto-commit the file
                    import subprocess

                    subprocess.run(
                        ["git", "add", str(path)],
                        cwd=self.workspace,
                        check=True,
                        capture_output=True,
                    )
                    result = subprocess.run(
                        [
                            "git",
                            "commit",
                            "-m",
                            f"Update {relative_path}",
                        ],
                        cwd=self.workspace,
                        capture_output=True,
                    )
                    if result.returncode == 0:
                        commit_msg = f" (committed to git)"
            except (ValueError, subprocess.CalledProcessError):
                # Not in data/ or git command failed - continue without commit
                pass

            metadata = {
                "action": "write",
                "target": str(path),
                "lines": lines_written,
                "bytes": bytes_written,
            }

            success_msg = f"Successfully wrote {lines_written} lines ({bytes_written} bytes) to {path}"
            if commit_msg:
                success_msg += commit_msg

            return self._create_result(
                content=success_msg,
                metadata=metadata,
            )

        except Exception as e:
            return self._create_result(
                content=f"Error writing file: {str(e)}",
                is_error=True,
                metadata={"action": "write", "target": file_path},
            )


class EditFileTool(BaseTool):
    """Edit a file using exact string replacement."""

    name = "edit_file"
    description = "Edit a file by replacing old_string with new_string (must be exact match)"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory for file operations
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact string to replace (must match exactly)",
                },
                "new_string": {
                    "type": "string",
                    "description": "New string to replace with",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: false, only first occurrence)",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> ToolResult:
        """Execute file edit.

        Args:
            file_path: Path to file
            old_string: String to replace
            new_string: Replacement string
            replace_all: Replace all occurrences

        Returns:
            ToolResult with edit summary
        """
        try:
            # Resolve path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.workspace / path

            # Check file exists
            if not path.exists():
                return self._create_result(
                    content=f"Error: File not found: {path}",
                    is_error=True,
                    metadata={"action": "edit", "target": str(path)},
                )

            # Read file
            with open(path, encoding="utf-8") as f:
                content = f.read()

            # Check if old_string exists
            if old_string not in content:
                return self._create_result(
                    content=f"Error: String not found in file: {old_string[:100]}...",
                    is_error=True,
                    metadata={"action": "edit", "target": str(path)},
                )

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            # Write file
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            metadata = {
                "action": "edit",
                "target": str(path),
                "replacements": count,
                "old_length": len(old_string),
                "new_length": len(new_string),
            }

            return self._create_result(
                content=f"Successfully replaced {count} occurrence(s) in {path}",
                metadata=metadata,
            )

        except Exception as e:
            return self._create_result(
                content=f"Error editing file: {str(e)}",
                is_error=True,
                metadata={"action": "edit", "target": file_path},
            )


class GlobTool(BaseTool):
    """Find files matching a pattern."""

    name = "glob"
    description = "Find files matching a glob pattern (e.g., '*.py', '**/*.md')"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory for file operations
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '*.py', '**/*.md', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: workspace)",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, pattern: str, path: str | None = None) -> ToolResult:
        """Execute glob search.

        Args:
            pattern: Glob pattern
            path: Directory to search in

        Returns:
            ToolResult with matching files
        """
        try:
            # Resolve search path
            search_path = Path(path) if path else self.workspace
            if not search_path.is_absolute():
                search_path = self.workspace / search_path

            # Perform glob
            matches = sorted(search_path.glob(pattern))

            # Format results
            if matches:
                content = "\n".join(str(p.relative_to(search_path)) for p in matches)
            else:
                content = f"No files found matching pattern: {pattern}"

            metadata = {
                "action": "glob",
                "target": str(search_path),
                "pattern": pattern,
                "matches": len(matches),
            }

            return self._create_result(content=content, metadata=metadata)

        except Exception as e:
            return self._create_result(
                content=f"Error in glob search: {str(e)}",
                is_error=True,
                metadata={"action": "glob", "pattern": pattern},
            )


class GrepTool(BaseTool):
    """Search file contents using regex."""

    name = "grep"
    description = "Search for text patterns in files using regex"

    def __init__(self, workspace: Path | None = None, **kwargs: Any):
        """Initialize tool.

        Args:
            workspace: Base directory for file operations
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern for files to search (e.g., '*.py')",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case sensitive search (default: true)",
                },
            },
            "required": ["pattern"],
        }

    def execute(
        self,
        pattern: str,
        path: str | None = None,
        file_pattern: str = "*",
        case_sensitive: bool = True,
    ) -> ToolResult:
        """Execute grep search.

        Args:
            pattern: Regex pattern
            path: File or directory to search
            file_pattern: Glob pattern for files
            case_sensitive: Case sensitive search

        Returns:
            ToolResult with matches
        """
        try:
            # Compile regex
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)

            # Resolve search path
            search_path = Path(path) if path else self.workspace
            if not search_path.is_absolute():
                search_path = self.workspace / search_path

            # Collect files to search
            if search_path.is_file():
                files = [search_path]
            else:
                files = sorted(search_path.glob(f"**/{file_pattern}"))

            # Search files
            results = []
            total_matches = 0

            for file_path in files:
                if not file_path.is_file():
                    continue

                try:
                    with open(file_path, encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(
                                    f"{file_path.relative_to(self.workspace)}:{line_num}:{line.rstrip()}"
                                )
                                total_matches += 1
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary files or files we can't read
                    continue

            # Format results
            if results:
                content = "\n".join(results[:100])  # Limit to 100 matches
                if len(results) > 100:
                    content += f"\n... ({len(results) - 100} more matches)"
            else:
                content = f"No matches found for pattern: {pattern}"

            metadata = {
                "action": "grep",
                "pattern": pattern,
                "files_searched": len(files),
                "total_matches": total_matches,
            }

            return self._create_result(content=content, metadata=metadata)

        except Exception as e:
            return self._create_result(
                content=f"Error in grep search: {str(e)}",
                is_error=True,
                metadata={"action": "grep", "pattern": pattern},
            )
