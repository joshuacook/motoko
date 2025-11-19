"""Bash command execution tool."""

import subprocess
from pathlib import Path
from typing import Any

from ..types import ToolResult
from .base import BaseTool


class BashTool(BaseTool):
    """Execute bash commands.

    Security note: This tool executes arbitrary commands. Use with caution
    and implement appropriate security measures in production.
    """

    name = "bash"
    description = "Execute bash commands in a shell"

    def __init__(
        self,
        workspace: Path | None = None,
        timeout: int = 120,
        **kwargs: Any,
    ):
        """Initialize tool.

        Args:
            workspace: Working directory for commands
            timeout: Command timeout in seconds (default: 120)
            **kwargs: Additional parameters
        """
        super().__init__(**kwargs)
        self.workspace = workspace or Path.cwd()
        self.timeout = timeout

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Bash command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (default: workspace)",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Command timeout in seconds (default: {self.timeout})",
                },
            },
            "required": ["command"],
        }

    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> ToolResult:
        """Execute bash command.

        Args:
            command: Command to execute
            cwd: Working directory
            timeout: Command timeout

        Returns:
            ToolResult with command output
        """
        try:
            # Resolve working directory
            work_dir = Path(cwd) if cwd else self.workspace
            if not work_dir.is_absolute():
                work_dir = self.workspace / work_dir

            # Use provided timeout or default
            cmd_timeout = timeout or self.timeout

            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=cmd_timeout,
            )

            # Combine stdout and stderr
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\n"
                output += result.stderr

            # Check if command failed
            is_error = result.returncode != 0

            # Limit output size
            max_size = 10000
            if len(output) > max_size:
                output = output[:max_size] + f"\n... (truncated, {len(output)} total chars)"

            metadata = {
                "action": "bash",
                "command": command,
                "exit_code": result.returncode,
                "cwd": str(work_dir),
            }

            return self._create_result(
                content=output or "(no output)",
                is_error=is_error,
                metadata=metadata,
            )

        except subprocess.TimeoutExpired:
            return self._create_result(
                content=f"Error: Command timed out after {cmd_timeout} seconds",
                is_error=True,
                metadata={"action": "bash", "command": command},
            )
        except Exception as e:
            return self._create_result(
                content=f"Error executing command: {str(e)}",
                is_error=True,
                metadata={"action": "bash", "command": command},
            )
