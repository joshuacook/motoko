"""Entity operations for the Context Lake."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter

from batou.schema import Schema


class EntityTools:
    """Structured entity operations on local filesystem."""

    def __init__(self, workspace_path: str | Path):
        """Initialize entity tools for a workspace.

        Args:
            workspace_path: Path to the workspace root directory
        """
        self.workspace_path = Path(workspace_path)
        self.schema = Schema(self.workspace_path)

    def _entity_id_from_path(self, path: Path) -> str:
        """Extract entity ID from file path."""
        return path.stem  # filename without extension

    def _parse_file(self, path: Path) -> tuple[dict[str, Any], str]:
        """Parse a markdown file into frontmatter and content.

        Args:
            path: Path to the markdown file

        Returns:
            Tuple of (frontmatter dict, content string)
        """
        with open(path) as f:
            post = frontmatter.load(f)
        return dict(post.metadata), post.content

    def _write_file(self, path: Path, fm: dict[str, Any], content: str) -> None:
        """Write frontmatter and content to a markdown file.

        Args:
            path: Path to write to
            fm: Frontmatter dict
            content: Markdown content
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post(content, **fm)
        with open(path, "w") as f:
            f.write(frontmatter.dumps(post))

    def list_entities(
        self,
        entity_type: str,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List entities of a given type.

        Args:
            entity_type: Entity type (e.g., 'tasks', 'notes')
            status: Optional status filter (if set, overrides include_archived)
            include_archived: If False (default), exclude archived entities
            limit: Maximum number of results

        Returns:
            Dict with entities list and count
        """
        directory = self.schema.get_directory(entity_type)

        if not directory.exists():
            return {"success": True, "entities": [], "count": 0}

        entities = []
        for path in sorted(directory.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(entities) >= limit:
                break

            try:
                fm, _ = self._parse_file(path)
                entity_status = fm.get("status")

                # Apply status filter
                if status:
                    # Explicit status filter - only show matching
                    if entity_status != status:
                        continue
                elif not include_archived:
                    # Default: exclude archived unless explicitly requested
                    if entity_status == "archived":
                        continue

                entities.append({
                    "entity_id": self._entity_id_from_path(path),
                    "entity_type": entity_type,
                    "title": fm.get("title") or fm.get("name") or path.stem,
                    "status": entity_status,
                    "path": str(path.relative_to(self.workspace_path)),
                    "frontmatter": fm,
                })
            except Exception:
                # Skip files that can't be parsed
                continue

        return {
            "success": True,
            "entities": entities,
            "count": len(entities),
        }

    def get_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict[str, Any]:
        """Get a specific entity by type and ID.

        Args:
            entity_type: Entity type
            entity_id: Entity ID (filename without extension)

        Returns:
            Dict with entity data or error
        """
        directory = self.schema.get_directory(entity_type)
        path = directory / f"{entity_id}.md"

        if not path.exists():
            return {
                "success": False,
                "error": f"Entity not found: {entity_type}/{entity_id}",
            }

        try:
            fm, content = self._parse_file(path)
            return {
                "success": True,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "path": str(path.relative_to(self.workspace_path)),
                "frontmatter": fm,
                "content": content,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read entity: {e}",
            }

    def create_entity(
        self,
        entity_type: str,
        frontmatter: dict[str, Any],
        content: str,
    ) -> dict[str, Any]:
        """Create a new entity.

        Args:
            entity_type: Entity type
            frontmatter: Entity frontmatter
            content: Markdown content

        Returns:
            Dict with created entity info or error
        """
        # Apply defaults from schema
        defaults = self.schema.get_defaults(entity_type)
        fm = {**defaults, **frontmatter}

        # Add created_at if not present
        if "created_at" not in fm:
            fm["created_at"] = datetime.now().isoformat()

        # Generate filename
        filename = self.schema.generate_filename(entity_type, fm)
        directory = self.schema.get_directory(entity_type)
        path = directory / filename

        # Check if already exists
        if path.exists():
            return {
                "success": False,
                "error": f"Entity already exists: {path.relative_to(self.workspace_path)}",
            }

        # Validate required fields
        required = self.schema.get_required_fields(entity_type)
        missing = [f for f in required if f not in fm]
        if missing:
            return {
                "success": False,
                "error": f"Missing required fields: {missing}",
            }

        try:
            self._write_file(path, fm, content)
            entity_id = self._entity_id_from_path(path)

            return {
                "success": True,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "path": str(path.relative_to(self.workspace_path)),
                "frontmatter": fm,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create entity: {e}",
            }

    def update_entity(
        self,
        entity_type: str,
        entity_id: str,
        frontmatter: dict[str, Any] | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            frontmatter: Frontmatter updates (merged with existing)
            content: New content (replaces existing if provided)

        Returns:
            Dict with updated entity info or error
        """
        # Get existing entity
        existing = self.get_entity(entity_type, entity_id)
        if not existing.get("success"):
            return existing

        # Merge frontmatter
        new_fm = {**existing["frontmatter"]}
        if frontmatter:
            new_fm.update(frontmatter)

        # Add updated_at
        new_fm["updated_at"] = datetime.now().isoformat()

        # Use new content or keep existing
        new_content = content if content is not None else existing["content"]

        # Write back
        path = self.workspace_path / existing["path"]

        try:
            self._write_file(path, new_fm, new_content)
            return {
                "success": True,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "path": existing["path"],
                "frontmatter": new_fm,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to update entity: {e}",
            }

    def delete_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict[str, Any]:
        """Delete an entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            Dict with success status
        """
        directory = self.schema.get_directory(entity_type)
        path = directory / f"{entity_id}.md"

        if not path.exists():
            return {
                "success": False,
                "error": f"Entity not found: {entity_type}/{entity_id}",
            }

        try:
            path.unlink()
            return {
                "success": True,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "deleted": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete entity: {e}",
            }

    def search_entities(
        self,
        query: str,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search entities by text content.

        Simple grep-style search. For semantic search, use external tools.

        Args:
            query: Search query (case-insensitive substring match)
            entity_type: Optional entity type filter
            limit: Maximum results

        Returns:
            Dict with matching entities
        """
        query_lower = query.lower()
        results = []

        # Determine which directories to search
        if entity_type:
            directories = [(entity_type, self.schema.get_directory(entity_type))]
        else:
            # Search all entity types in schema, plus common defaults
            entity_types = set(self.schema.list_entity_types())
            entity_types.update(["tasks", "notes", "projects", "journal"])

            directories = [
                (et, self.schema.get_directory(et))
                for et in entity_types
            ]

        for et, directory in directories:
            if not directory.exists():
                continue

            for path in directory.glob("*.md"):
                if len(results) >= limit:
                    break

                try:
                    fm, content = self._parse_file(path)
                    full_text = f"{fm.get('title', '')} {content}".lower()

                    if query_lower in full_text:
                        results.append({
                            "entity_id": self._entity_id_from_path(path),
                            "entity_type": et,
                            "title": fm.get("title") or fm.get("name") or path.stem,
                            "path": str(path.relative_to(self.workspace_path)),
                            "frontmatter": fm,
                        })
                except Exception:
                    continue

        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
        }

    def get_schema_info(self) -> dict[str, Any]:
        """Get information about the workspace schema.

        Returns:
            Dict with schema details
        """
        return {
            "success": True,
            "entity_types": self.schema.list_entity_types(),
            "schema": self.schema._schema,
        }
