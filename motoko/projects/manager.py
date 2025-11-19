"""Project management for motoko workspaces."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ProjectType(Enum):
    """Project type."""

    STARTUP = "startup"
    CONSULTING = "consulting"
    CREATIVE = "creative"
    ACADEMIC = "academic"
    EMPLOYMENT = "employment"


class ProjectStatus(Enum):
    """Project status."""

    ACTIVE = "Active"
    PAUSED = "Paused"
    ARCHIVED = "Archived"


@dataclass
class Project:
    """Represents a project entity."""

    code: str
    name: str
    type: ProjectType
    status: ProjectStatus
    file_path: Path
    content: str | None = None


class ProjectManager:
    """Manages projects in a motoko workspace."""

    def __init__(self, workspace: Path):
        """Initialize project manager.

        Args:
            workspace: Project workspace directory
        """
        self.workspace = Path(workspace)
        self.projects_dir = self.workspace / "data" / "projects"

    def ensure_projects_dir(self) -> None:
        """Create projects directory if it doesn't exist."""
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def _validate_code(self, code: str) -> bool:
        """Validate project CODE format.

        Args:
            code: Project CODE

        Returns:
            True if valid
        """
        # Must be uppercase letters, numbers, and underscores only
        return bool(re.match(r"^[A-Z0-9_]+$", code))

    def list_projects(self, status: ProjectStatus | None = None) -> list[Project]:
        """List projects in the workspace.

        Args:
            status: Filter by status (None = all projects)

        Returns:
            List of Project objects, sorted by code
        """
        if not self.projects_dir.exists():
            return []

        projects = []
        for file_path in self.projects_dir.glob("*.md"):
            code = file_path.stem

            # Read file to get status (from frontmatter)
            try:
                content = file_path.read_text()

                # Parse frontmatter for status and type
                import yaml

                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1])
                        project_status = ProjectStatus(fm.get("status", "Active"))
                        project_type = ProjectType(fm.get("type", "consulting"))
                        project_name = fm.get("name", code)

                        # Filter by status if specified
                        if status and project_status != status:
                            continue

                        projects.append(
                            Project(
                                code=code,
                                name=project_name,
                                type=project_type,
                                status=project_status,
                                file_path=file_path,
                            )
                        )
            except Exception:
                # Skip files with parse errors
                continue

        # Sort by code
        projects.sort(key=lambda p: p.code)
        return projects

    def get_project(self, code: str, load_content: bool = True) -> Project | None:
        """Get a specific project by code.

        Args:
            code: Project CODE
            load_content: Whether to load file content

        Returns:
            Project object or None if not found
        """
        file_path = self.projects_dir / f"{code.upper()}.md"
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text()

            # Parse frontmatter
            import yaml

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1])
                    project = Project(
                        code=code.upper(),
                        name=fm.get("name", code),
                        type=ProjectType(fm.get("type", "consulting")),
                        status=ProjectStatus(fm.get("status", "Active")),
                        file_path=file_path,
                        content=content if load_content else None,
                    )
                    return project
        except Exception:
            return None

        return None

    def create_project(
        self,
        code: str,
        name: str,
        type: ProjectType,
        company: str | None = None,
        description: str = "",
    ) -> Project:
        """Create a new project.

        Args:
            code: Project CODE (uppercase)
            name: Project name
            type: Project type
            company: Company CODE reference
            description: Project description

        Returns:
            Created Project object
        """
        self.ensure_projects_dir()

        # Validate code
        code = code.upper()
        if not self._validate_code(code):
            raise ValueError(f"Invalid project CODE: {code}. Must be uppercase letters, numbers, and underscores.")

        # Check if already exists
        file_path = self.projects_dir / f"{code}.md"
        if file_path.exists():
            raise ValueError(f"Project {code} already exists")

        # Build frontmatter
        fm_parts = [
            f"code: {code}",
            f"name: {name}",
            f"type: {type.value}",
            f"status: Active",
        ]
        if company:
            fm_parts.append(f"company: {company.upper()}")

        # Build content
        content = "---\n" + "\n".join(fm_parts) + "\n---\n\n"
        if description:
            content += description
        else:
            content += f"# {name}\n\n## Background\n\n## Goals\n\n## Current State\n\n"

        # Write file
        file_path.write_text(content)

        # Auto-commit
        self._auto_commit(file_path, f"Create project {code}: {name}")

        return Project(
            code=code,
            name=name,
            type=type,
            status=ProjectStatus.ACTIVE,
            file_path=file_path,
            content=content,
        )

    def update_project(
        self,
        code: str,
        status: ProjectStatus | None = None,
        name: str | None = None,
    ) -> Project | None:
        """Update project metadata.

        Args:
            code: Project CODE
            status: New status
            name: New name

        Returns:
            Updated Project or None if not found
        """
        project = self.get_project(code, load_content=True)
        if not project or not project.content:
            return None

        # Parse and update frontmatter
        import yaml

        parts = project.content.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1])

            if status:
                fm["status"] = status.value
                project.status = status
            if name:
                fm["name"] = name
                project.name = name

            # Rebuild content
            import yaml

            new_fm = yaml.dump(fm, default_flow_style=False, sort_keys=False)
            new_content = f"---\n{new_fm}---{parts[2]}"

            # Write file
            project.file_path.write_text(new_content)

            # Auto-commit
            self._auto_commit(project.file_path, f"Update project {code}")

            project.content = new_content
            return project

        return None

    def _auto_commit(self, file_path: Path, commit_message: str) -> None:
        """Auto-commit a file to git.

        Args:
            file_path: Path to file to commit
            commit_message: Git commit message
        """
        import subprocess

        try:
            # Add file to git
            subprocess.run(
                ["git", "add", str(file_path)],
                cwd=self.workspace,
                check=True,
                capture_output=True,
            )

            # Commit with message
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.workspace,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            # Git command failed - silently continue
            pass
