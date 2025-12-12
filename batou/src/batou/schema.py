"""Schema loading and entity type configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class Schema:
    """Workspace schema loaded from .claude/schema.yaml."""

    def __init__(self, workspace_path: Path):
        """Initialize schema for a workspace.

        Args:
            workspace_path: Path to the workspace root directory
        """
        self.workspace_path = workspace_path
        self._schema: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load schema from .claude/schema.yaml if it exists."""
        schema_path = self.workspace_path / ".claude" / "schema.yaml"

        if schema_path.exists():
            with open(schema_path) as f:
                self._schema = yaml.safe_load(f) or {}

    def reload(self) -> None:
        """Reload schema from disk."""
        self._load()

    @property
    def entities(self) -> dict[str, dict]:
        """Get entity type definitions."""
        return self._schema.get("entities", {})

    def get_entity_config(self, entity_type: str) -> dict[str, Any]:
        """Get configuration for an entity type.

        Args:
            entity_type: The entity type name (e.g., 'tasks', 'notes')

        Returns:
            Entity configuration dict with directory, naming, frontmatter rules.
            Returns sensible defaults if entity type not defined in schema.
        """
        config = self.entities.get(entity_type, {})

        # Apply defaults for undefined entity types
        # Default directory is just the entity type (workspace IS the lake)
        return {
            "directory": config.get("directory", entity_type),
            "naming": config.get("naming", "{slug}.md"),
            "frontmatter": config.get("frontmatter", {}),
        }

    def get_directory(self, entity_type: str) -> Path:
        """Get the directory path for an entity type.

        Args:
            entity_type: The entity type name

        Returns:
            Absolute path to the entity type directory
        """
        config = self.get_entity_config(entity_type)
        return self.workspace_path / config["directory"]

    def get_required_fields(self, entity_type: str) -> list[str]:
        """Get required frontmatter fields for an entity type.

        Args:
            entity_type: The entity type name

        Returns:
            List of required field names
        """
        config = self.get_entity_config(entity_type)
        return config.get("frontmatter", {}).get("required", [])

    def get_defaults(self, entity_type: str) -> dict[str, Any]:
        """Get default frontmatter values for an entity type.

        Args:
            entity_type: The entity type name

        Returns:
            Dict of field names to default values
        """
        config = self.get_entity_config(entity_type)
        return config.get("frontmatter", {}).get("defaults", {})

    def generate_filename(self, entity_type: str, frontmatter: dict[str, Any]) -> str:
        """Generate filename from schema naming pattern.

        Args:
            entity_type: The entity type name
            frontmatter: Entity frontmatter to use for template substitution

        Returns:
            Generated filename (e.g., 'my-task.md', '2024-01-15.md')
        """
        config = self.get_entity_config(entity_type)
        naming = config["naming"]

        # Simple template substitution
        filename = naming
        for key, value in frontmatter.items():
            placeholder = "{" + key + "}"
            if placeholder in filename:
                filename = filename.replace(placeholder, str(value))

        return filename

    def list_entity_types(self) -> list[str]:
        """List all defined entity types.

        Returns:
            List of entity type names defined in schema
        """
        return list(self.entities.keys())
