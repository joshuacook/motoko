"""Configuration for Major agent - MCP loading, workspace validation."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MajorConfig:
    """Configuration for Major agent.

    Attributes:
        workspace_root: Root directory for workspaces (default: /opt/workspaces)
        platform_config_path: Path to platform .mcp.json (default: /opt/claude-code-apps/platform)
        platform_skills_path: Path to platform skills (default: /opt/claude-code-apps/platform/.claude/skills)
    """
    workspace_root: str = "/opt/workspaces"
    platform_config_path: str = "/opt/claude-code-apps/platform"
    platform_skills_path: str = "/opt/claude-code-apps/platform/.claude/skills"

    def validate_workspace(self, workspace_path: str) -> str:
        """Validate workspace path is under workspace root.

        Args:
            workspace_path: Path to validate

        Returns:
            Normalized workspace path

        Raises:
            ValueError: If path is invalid or outside workspace root
        """
        if not workspace_path:
            raise ValueError("workspace_path is required")

        # Translate legacy Docker paths
        if workspace_path.startswith('/workspace/'):
            workspace_path = workspace_path.replace('/workspace/', f'{self.workspace_root}/', 1)

        path = Path(workspace_path)

        if not path.exists():
            raise ValueError(f"Workspace does not exist: {workspace_path}")

        if not workspace_path.startswith(self.workspace_root):
            raise ValueError(f"Workspace must be under {self.workspace_root}, got: {workspace_path}")

        return workspace_path

    def load_mcp_servers(
        self,
        workspace_path: str,
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Load and merge MCP configs from platform, user, and workspace levels.

        Hierarchy (later overrides earlier):
        1. Platform: {platform_config_path}/.mcp.json
        2. User: {workspace_path}/../.mcp.json
        3. Workspace: {workspace_path}/.mcp.json

        Args:
            workspace_path: Path to workspace
            user_context: Optional user context to inject into MCP env vars.
                         Keys like 'clerk_id' are injected as CLERK_ID env var.

        Returns:
            Merged MCP server configurations
        """
        merged_servers: dict[str, Any] = {}
        workspace = Path(workspace_path)

        config_paths = [
            Path(self.platform_config_path) / ".mcp.json",
            workspace.parent / ".mcp.json",
            workspace / ".mcp.json",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                        servers = config.get("mcpServers", {})
                        merged_servers.update(servers)
                except Exception:
                    pass  # Skip invalid configs

        # Inject WORKSPACE_PATH for batou MCP server
        if "batou" in merged_servers:
            if "env" not in merged_servers["batou"]:
                merged_servers["batou"]["env"] = {}
            merged_servers["batou"]["env"]["WORKSPACE_PATH"] = workspace_path

        # Inject user context as env vars for MCP servers that need it
        if user_context:
            # chelle-api needs ORGANIZATION_ID (from clerk_id)
            if "chelle-api" in merged_servers and user_context.get("clerk_id"):
                if "env" not in merged_servers["chelle-api"]:
                    merged_servers["chelle-api"]["env"] = {}
                merged_servers["chelle-api"]["env"]["ORGANIZATION_ID"] = user_context["clerk_id"]

        return merged_servers

    def sync_skills(self, workspace_path: str) -> None:
        """Copy skills from platform and user levels to workspace.

        Skills are copied so the SDK can find them in cwd.
        Workspace-level skills take precedence (won't be overwritten).

        Args:
            workspace_path: Path to workspace
        """
        import shutil

        workspace = Path(workspace_path)
        workspace_skills = workspace / ".claude" / "skills"
        workspace_skills.mkdir(parents=True, exist_ok=True)

        source_dirs = [
            Path(self.platform_skills_path),
            workspace.parent / ".claude" / "skills",
        ]

        for source_dir in source_dirs:
            if not source_dir.exists():
                continue

            for skill_dir in source_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                target_dir = workspace_skills / skill_dir.name

                # Don't overwrite existing workspace skills
                if target_dir.exists():
                    continue

                try:
                    shutil.copytree(skill_dir, target_dir)
                except Exception:
                    pass  # Skip failed copies
