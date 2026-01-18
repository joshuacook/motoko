"""Schema loading and entity type configuration."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: Text to slugify

    Returns:
        Lowercase slug with hyphens
    """
    # Lowercase and replace spaces/underscores with hyphens
    slug = text.lower().strip()
    slug = re.sub(r'[\s_]+', '-', slug)
    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    return slug


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

        # Build substitution dict with special values
        subs = dict(frontmatter)

        # Handle {slug} - derive from title if not explicitly provided
        if "{slug}" in naming and "slug" not in subs:
            title = frontmatter.get("title", "untitled")
            subs["slug"] = slugify(title)

        # Handle {date} - use today if not provided
        if "{date}" in naming and "date" not in subs:
            subs["date"] = date.today().isoformat()

        # Handle {number} - would need to scan directory for next number
        # For now, leave it for the caller to provide

        # Template substitution
        filename = naming
        for key, value in subs.items():
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
