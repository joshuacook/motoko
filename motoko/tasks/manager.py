"""Task management for project workflows."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class TaskStatus(Enum):
    """Task status."""

    OPEN = "open"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"


@dataclass
class Task:
    """Represents a project task."""

    number: int
    name: str
    status: TaskStatus
    file_path: Path
    content: str | None = None

    @property
    def title(self) -> str:
        """Get formatted task title."""
        status_prefix = "✓ " if self.status == TaskStatus.COMPLETED else "  "
        return f"{status_prefix}{self.number:06d}: {self.name.replace('-', ' ').title()}"

    def __str__(self) -> str:
        """String representation."""
        return self.title


class TaskManager:
    """Manages tasks in a project workspace."""

    def __init__(self, workspace: Path):
        """Initialize task manager.

        Args:
            workspace: Project workspace directory
        """
        self.workspace = Path(workspace)
        self.tasks_dir = self.workspace / "data" / "tasks"

    def ensure_tasks_dir(self) -> None:
        """Create tasks directory if it doesn't exist."""
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def _parse_filename(self, filename: str) -> tuple[int, TaskStatus, str] | None:
        """Parse task filename into components.

        Args:
            filename: Task filename (e.g., "000001-COMPLETED-task-name.md")

        Returns:
            Tuple of (number, status, name) or None if invalid
        """
        # Pattern: 6 digits, optional -COMPLETED-, then name
        pattern = r"^(\d{6})(?:-COMPLETED)?-(.+)\.md$"
        match = re.match(pattern, filename)

        if not match:
            return None

        number = int(match.group(1))
        name = match.group(2)

        # Check if COMPLETED is in the filename
        status = TaskStatus.COMPLETED if "-COMPLETED-" in filename else TaskStatus.OPEN

        return number, status, name

    def list_tasks(
        self, status: TaskStatus | None = None, limit: int | None = None
    ) -> list[Task]:
        """List tasks in the workspace.

        Args:
            status: Filter by status (None = all tasks)
            limit: Maximum number of tasks to return

        Returns:
            List of Task objects, sorted by number
        """
        if not self.tasks_dir.exists():
            return []

        tasks = []
        for file_path in self.tasks_dir.glob("*.md"):
            parsed = self._parse_filename(file_path.name)
            if parsed:
                number, file_status, name = parsed

                # Filter by status if specified
                if status and file_status != status:
                    continue

                tasks.append(
                    Task(
                        number=number,
                        name=name,
                        status=file_status,
                        file_path=file_path,
                    )
                )

        # Sort by number
        tasks.sort(key=lambda t: t.number)

        # Apply limit
        if limit:
            tasks = tasks[:limit]

        return tasks

    def get_task(self, number: int, load_content: bool = True) -> Task | None:
        """Get a specific task by number.

        Args:
            number: Task number
            load_content: Whether to load file content

        Returns:
            Task object or None if not found
        """
        tasks = self.list_tasks()
        for task in tasks:
            if task.number == number:
                if load_content:
                    task.content = task.file_path.read_text()
                return task
        return None

    def create_task(self, name: str, description: str = "") -> Task:
        """Create a new task.

        Args:
            name: Task name (will be converted to kebab-case)
            description: Task description/content

        Returns:
            Created Task object
        """
        self.ensure_tasks_dir()

        # Get next task number
        existing_tasks = self.list_tasks()
        next_number = max([t.number for t in existing_tasks], default=0) + 1

        # Convert name to kebab-case
        kebab_name = name.lower().replace(" ", "-")
        kebab_name = re.sub(r"[^a-z0-9-]", "", kebab_name)

        # Create filename
        filename = f"{next_number:06d}-{kebab_name}.md"
        file_path = self.tasks_dir / filename

        # Create file with description
        content = description if description else f"# {name}\n\n## Description\n\n## Execution\n\n"
        file_path.write_text(content)

        return Task(
            number=next_number,
            name=kebab_name,
            status=TaskStatus.OPEN,
            file_path=file_path,
            content=content,
        )

    def update_task(self, number: int, content: str) -> Task | None:
        """Update task content.

        Args:
            number: Task number
            content: New content

        Returns:
            Updated Task object or None if not found
        """
        task = self.get_task(number, load_content=False)
        if not task:
            return None

        task.file_path.write_text(content)
        task.content = content
        return task

    def complete_task(self, number: int) -> Task | None:
        """Mark task as completed by renaming file.

        Args:
            number: Task number

        Returns:
            Updated Task object or None if not found
        """
        task = self.get_task(number, load_content=True)
        if not task:
            return None

        if task.status == TaskStatus.COMPLETED:
            # Already completed
            return task

        # Create new filename with COMPLETED
        new_filename = f"{task.number:06d}-COMPLETED-{task.name}.md"
        new_path = self.tasks_dir / new_filename

        # Rename file
        task.file_path.rename(new_path)

        # Update task object
        task.status = TaskStatus.COMPLETED
        task.file_path = new_path

        return task

    def reopen_task(self, number: int) -> Task | None:
        """Reopen a completed task.

        Args:
            number: Task number

        Returns:
            Updated Task object or None if not found
        """
        task = self.get_task(number, load_content=True)
        if not task:
            return None

        if task.status != TaskStatus.COMPLETED:
            # Not completed, nothing to do
            return task

        # Create new filename without COMPLETED
        new_filename = f"{task.number:06d}-{task.name}.md"
        new_path = self.tasks_dir / new_filename

        # Rename file
        task.file_path.rename(new_path)

        # Update task object
        task.status = TaskStatus.OPEN
        task.file_path = new_path

        return task

    def get_open_tasks_summary(self, limit: int = 10) -> str:
        """Get a formatted summary of open tasks.

        Args:
            limit: Maximum number of tasks to include

        Returns:
            Formatted string summary
        """
        open_tasks = self.list_tasks(status=TaskStatus.OPEN, limit=limit)

        if not open_tasks:
            return "No open tasks in this workspace."

        lines = [f"Open tasks in {self.workspace.name}:"]
        for task in open_tasks:
            lines.append(f"  {task.title}")

        if len(open_tasks) == limit:
            total_open = len(self.list_tasks(status=TaskStatus.OPEN))
            if total_open > limit:
                lines.append(f"\n  ... and {total_open - limit} more")

        return "\n".join(lines)
