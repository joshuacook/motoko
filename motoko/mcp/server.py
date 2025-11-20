"""Motoko MCP Server - Model Context Protocol server for context management."""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from motoko.tasks import TaskManager, TaskStatus
from motoko.projects import ProjectManager, ProjectStatus, ProjectType
from motoko.companies import CompanyManager, CompanyRelationship


# Initialize server
app = Server("motoko")

# Workspace path (set on initialization)
workspace: Path | None = None


def get_workspace() -> Path:
    """Get current workspace path."""
    global workspace
    if workspace is None:
        workspace = Path.cwd()
    return workspace


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """Register available MCP tools."""
    return [
        # Context Discovery Tools
        Tool(
            name="context_summary",
            description="Get comprehensive workspace state including tasks, projects, roles, and git activity",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["json", "text"],
                        "description": "Output format",
                        "default": "json"
                    }
                }
            }
        ),
        Tool(
            name="context_entities",
            description="List all entities by type with counts",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["tasks", "projects", "companies", "journal", "sessions", "experiments", "inbox"],
                        "description": "Optional filter by entity type"
                    }
                }
            }
        ),
        Tool(
            name="task_list",
            description="List tasks with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "completed", "cancelled", "in_progress"],
                        "description": "Filter by task status"
                    },
                    "project": {
                        "type": "string",
                        "description": "Filter by project CODE"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tasks to return",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="context_validate",
            description="Validate workspace conventions and optionally fix issues",
            inputSchema={
                "type": "object",
                "properties": {
                    "fix": {
                        "type": "boolean",
                        "description": "Attempt to auto-fix issues",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="context_validate_relationships",
            description="Detect and report missing/broken entity relationships (task→project→company)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="context_recent",
            description="Show recently modified entities across workspace",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back",
                        "default": 7
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of files to return",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="workspace_init",
            description="Initialize a new motoko workspace with directory structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace path (defaults to current directory)"
                    }
                }
            }
        ),
        # Task Operation Tools
        Tool(
            name="task_show",
            description="Show complete task details including full markdown content",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task number"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="task_create",
            description="Create a new task with auto-assigned number and validation",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Task description (markdown content)"
                    },
                    "project": {
                        "type": "string",
                        "description": "Project CODE (uppercase)"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Task priority"
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="task_complete",
            description="Mark task(s) as completed (atomic operation with git commit)",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of task numbers to complete"
                    }
                },
                "required": ["task_ids"]
            }
        ),
        Tool(
            name="task_cancel",
            description="Mark task(s) as cancelled (atomic operation with git commit)",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of task numbers to cancel"
                    }
                },
                "required": ["task_ids"]
            }
        ),
        Tool(
            name="task_reopen",
            description="Reopen a completed or cancelled task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "Task number to reopen"
                    }
                },
                "required": ["task_id"]
            }
        ),
        # Project Management Tools
        Tool(
            name="project_list",
            description="List all projects with optional status filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Active", "Paused", "Archived"],
                        "description": "Filter by project status"
                    }
                }
            }
        ),
        Tool(
            name="project_show",
            description="Show complete project details",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Project CODE"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="project_create",
            description="Create a new project entity",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Project CODE (uppercase, letters/numbers/underscores)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Project name"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["startup", "consulting", "creative", "academic", "employment"],
                        "description": "Project type"
                    },
                    "company": {
                        "type": "string",
                        "description": "Company CODE reference"
                    },
                    "description": {
                        "type": "string",
                        "description": "Project description (markdown)"
                    }
                },
                "required": ["code", "name", "type"]
            }
        ),
        Tool(
            name="project_update",
            description="Update project metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Project CODE"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["Active", "Paused", "Archived"],
                        "description": "New status"
                    },
                    "name": {
                        "type": "string",
                        "description": "New name"
                    }
                },
                "required": ["code"]
            }
        ),
        # Company Management Tools
        Tool(
            name="company_list",
            description="List all companies",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="company_show",
            description="Show complete company details",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Company CODE"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="company_create",
            description="Create a new company entity",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Company CODE (uppercase)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Company name"
                    },
                    "relationship": {
                        "type": "string",
                        "enum": ["founder", "client", "employer", "institution"],
                        "description": "Relationship type"
                    },
                    "industry": {
                        "type": "string",
                        "description": "Industry"
                    },
                    "website": {
                        "type": "string",
                        "description": "Website URL"
                    },
                    "description": {
                        "type": "string",
                        "description": "Company description (markdown)"
                    }
                },
                "required": ["code", "name", "relationship"]
            }
        ),
    ]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "context_summary":
            result = await _context_summary(**arguments)
        elif name == "context_entities":
            result = await _context_entities(**arguments)
        elif name == "context_validate":
            result = await _context_validate(**arguments)
        elif name == "context_validate_relationships":
            result = await _context_validate_relationships(**arguments)
        elif name == "context_recent":
            result = await _context_recent(**arguments)
        elif name == "workspace_init":
            result = await _workspace_init(**arguments)
        elif name == "task_list":
            result = await _task_list(**arguments)
        elif name == "task_show":
            result = await _task_show(**arguments)
        elif name == "task_create":
            result = await _task_create(**arguments)
        elif name == "task_complete":
            result = await _task_complete(**arguments)
        elif name == "task_cancel":
            result = await _task_cancel(**arguments)
        elif name == "task_reopen":
            result = await _task_reopen(**arguments)
        elif name == "project_list":
            result = await _project_list(**arguments)
        elif name == "project_show":
            result = await _project_show(**arguments)
        elif name == "project_create":
            result = await _project_create(**arguments)
        elif name == "project_update":
            result = await _project_update(**arguments)
        elif name == "company_list":
            result = await _company_list()
        elif name == "company_show":
            result = await _company_show(**arguments)
        elif name == "company_create":
            result = await _company_create(**arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}

        # Return as TextContent
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        error_result = {"error": str(e), "tool": name}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


async def _context_summary(format: str = "json") -> dict[str, Any]:
    """Get comprehensive workspace state.

    Args:
        format: Output format ("json" or "text")

    Returns:
        Dictionary with workspace state
    """
    ws = get_workspace()

    # Load project context
    context_file = ws / "context" / "README.md"
    project_context = None
    context_updated = None
    if context_file.exists():
        project_context = context_file.read_text()[:500] + "..."  # First 500 chars
        context_updated = datetime.fromtimestamp(context_file.stat().st_mtime).strftime("%Y-%m-%d")

    # Discover roles
    roles_dir = ws / "roles"
    available_roles = []
    if roles_dir.exists():
        for role_file in sorted(roles_dir.glob("*.md")):
            role_name = role_file.stem.lstrip("0123456789-")
            available_roles.append(role_name)

    # Load tasks
    tm = TaskManager(ws)
    all_tasks = tm.list_tasks()
    open_tasks = [t for t in all_tasks if t.status == TaskStatus.OPEN]
    in_progress_tasks = [t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]
    completed_tasks = [t for t in all_tasks if t.status == TaskStatus.COMPLETED]
    cancelled_tasks = [t for t in all_tasks if t.status == TaskStatus.CANCELLED]

    # Load projects
    projects_dir = ws / "data" / "projects"
    projects = []
    if projects_dir.exists():
        for project_file in sorted(projects_dir.glob("*.md"))[:10]:
            projects.append({
                "code": project_file.stem,
                "file": str(project_file.relative_to(ws))
            })

    # Git status
    git_clean = True
    last_commit = None
    last_commit_msg = None
    commits_today = 0

    try:
        # Check if git repo
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ws,
            check=True,
            capture_output=True,
        )

        # Check if clean
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws,
            capture_output=True,
            text=True,
        )
        git_clean = len(result.stdout.strip()) == 0

        # Get last commit
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ar|%s"],
            cwd=ws,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            parts = result.stdout.strip().split("|", 1)
            last_commit = parts[0] if len(parts) > 0 else "unknown"
            last_commit_msg = parts[1] if len(parts) > 1 else "unknown"

        # Count today's commits
        result = subprocess.run(
            ["git", "log", "--since=midnight", "--oneline"],
            cwd=ws,
            capture_output=True,
            text=True,
        )
        commits_today = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

    except subprocess.CalledProcessError:
        pass

    # Build summary
    summary = {
        "workspace": {
            "name": ws.name,
            "path": str(ws),
            "git_clean": git_clean,
        },
        "project_context": {
            "exists": project_context is not None,
            "preview": project_context,
            "last_updated": context_updated,
        },
        "roles": {
            "available": available_roles,
            "count": len(available_roles),
        },
        "tasks": {
            "open": len(open_tasks),
            "in_progress": len(in_progress_tasks),
            "completed": len(completed_tasks),
            "cancelled": len(cancelled_tasks),
            "total": len(all_tasks),
            "recent_open": [
                {
                    "number": t.number,
                    "name": t.name,
                    "file": str(t.file_path.relative_to(ws)),
                }
                for t in open_tasks[:10]
            ],
        },
        "projects": {
            "available": projects,
            "count": len(projects),
        },
        "recent_activity": {
            "last_commit": last_commit,
            "last_commit_message": last_commit_msg,
            "commits_today": commits_today,
        },
    }

    return summary


async def _context_entities(type: str | None = None) -> dict[str, Any]:
    """List all entities by type with counts.

    Args:
        type: Optional filter by entity type

    Returns:
        Dictionary with entity counts
    """
    ws = get_workspace()
    data_dir = ws / "data"

    if not data_dir.exists():
        return {"error": "No data/ directory found in workspace"}

    entity_types = ["tasks", "projects", "companies", "journal", "sessions", "experiments", "inbox"]
    results = {}

    if type:
        # Show specific type
        type_dir = data_dir / type
        if not type_dir.exists():
            return {"error": f"No {type}/ directory found"}

        files = sorted(type_dir.glob("*.md"))
        results[type] = {
            "count": len(files),
            "files": [f.name for f in files[:20]]  # Limit to 20
        }
    else:
        # Show all types
        for entity_type in entity_types:
            type_dir = data_dir / entity_type
            if type_dir.exists():
                files = list(type_dir.glob("*.md"))
                results[entity_type] = {
                    "count": len(files),
                    "files": [f.name for f in sorted(files)[:20]]
                }

    return {"entities": results}


async def _context_validate(fix: bool = False) -> dict[str, Any]:
    """Validate workspace conventions.

    Args:
        fix: Whether to attempt auto-fix

    Returns:
        Validation results with errors/warnings
    """
    ws = get_workspace()
    data_dir = ws / "data"

    errors = []
    warnings = []
    fixed = []

    # Check if data/ directory exists
    if not data_dir.exists():
        errors.append({
            "type": "missing_directory",
            "path": "data/",
            "message": "data/ directory does not exist"
        })
        if fix:
            data_dir.mkdir(parents=True, exist_ok=True)
            fixed.append("Created data/ directory")

    # Check for required entity directories
    required_dirs = ["tasks", "projects", "companies", "journal", "sessions", "experiments", "inbox"]
    for dir_name in required_dirs:
        dir_path = data_dir / dir_name
        if not dir_path.exists():
            warnings.append({
                "type": "missing_entity_dir",
                "path": f"data/{dir_name}/",
                "message": f"Entity directory data/{dir_name}/ does not exist"
            })
            if fix:
                dir_path.mkdir(parents=True, exist_ok=True)
                fixed.append(f"Created data/{dir_name}/ directory")

    # Validate task filenames
    tasks_dir = data_dir / "tasks"
    if tasks_dir.exists():
        tm = TaskManager(ws)
        for file_path in tasks_dir.glob("*.md"):
            parsed = tm._parse_filename(file_path.name)
            if not parsed:
                errors.append({
                    "type": "invalid_task_filename",
                    "path": str(file_path.relative_to(ws)),
                    "message": f"Task filename does not match pattern: {file_path.name}"
                })

    # Check for context/README.md
    context_readme = ws / "context" / "README.md"
    if not context_readme.exists():
        warnings.append({
            "type": "missing_context",
            "path": "context/README.md",
            "message": "Project context file does not exist"
        })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "fixed": fixed if fix else [],
        "summary": f"{len(errors)} errors, {len(warnings)} warnings" + (f", {len(fixed)} fixed" if fix else "")
    }


async def _context_validate_relationships() -> dict[str, Any]:
    """Validate entity relationships (task→project→company).

    Detects:
    - Tasks referencing non-existent projects
    - Projects referencing non-existent companies
    - Tasks without project references
    - Projects without company references

    Returns:
        Dictionary with detected relationship issues
    """
    import yaml

    ws = get_workspace()
    data_dir = ws / "data"

    issues = {
        "orphaned_tasks": [],          # Tasks referencing non-existent projects
        "orphaned_projects": [],       # Projects referencing non-existent companies
        "tasks_without_project": [],   # Tasks with no project reference
        "projects_without_company": [], # Projects with no company reference
        "broken_task_companies": []    # Tasks referencing non-existent companies
    }

    # Get all existing entities
    existing_projects = set()
    existing_companies = set()

    # Load all projects
    projects_dir = data_dir / "projects"
    if projects_dir.exists():
        for project_file in projects_dir.glob("*.md"):
            code = project_file.stem
            existing_projects.add(code)

            # Check if project references a company
            try:
                content = project_file.read_text()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1])
                        company_ref = fm.get("company")
                        if not company_ref:
                            issues["projects_without_company"].append({
                                "project": code,
                                "file": str(project_file.relative_to(ws)),
                                "suggestion": "Add company reference in frontmatter"
                            })
            except Exception:
                pass

    # Load all companies
    companies_dir = data_dir / "companies"
    if companies_dir.exists():
        for company_file in companies_dir.glob("*.md"):
            code = company_file.stem
            existing_companies.add(code)

    # Check all tasks
    tasks_dir = data_dir / "tasks"
    if tasks_dir.exists():
        for task_file in tasks_dir.glob("*.md"):
            try:
                content = task_file.read_text()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1])

                        # Check project reference
                        project_ref = fm.get("project")
                        if project_ref:
                            if project_ref not in existing_projects:
                                issues["orphaned_tasks"].append({
                                    "task": task_file.name,
                                    "file": str(task_file.relative_to(ws)),
                                    "references_project": project_ref,
                                    "project_exists": False,
                                    "suggestion": f"Create project {project_ref} or update task reference"
                                })
                        else:
                            # Task has no project reference
                            # Extract project code from filename if it follows convention
                            # Format: 000001-PROJECT-task-name.md
                            filename_parts = task_file.stem.split("-", 2)
                            if len(filename_parts) >= 3:
                                potential_project = filename_parts[1]
                                if potential_project != "COMPLETED" and potential_project != "CANCELLED":
                                    issues["tasks_without_project"].append({
                                        "task": task_file.name,
                                        "file": str(task_file.relative_to(ws)),
                                        "potential_project": potential_project,
                                        "suggestion": f"Add project: {potential_project} to frontmatter"
                                    })

                        # Check company reference
                        company_ref = fm.get("company")
                        if company_ref and company_ref not in existing_companies:
                            issues["broken_task_companies"].append({
                                "task": task_file.name,
                                "file": str(task_file.relative_to(ws)),
                                "references_company": company_ref,
                                "company_exists": False,
                                "suggestion": f"Create company {company_ref} or update task reference"
                            })
            except Exception:
                # Skip files with parse errors
                continue

    # Count issues
    total_issues = sum(len(v) for v in issues.values())

    return {
        "valid": total_issues == 0,
        "total_issues": total_issues,
        "issues": issues,
        "summary": f"Found {total_issues} relationship issues across {len(issues)} categories",
        "existing_entities": {
            "projects": len(existing_projects),
            "companies": len(existing_companies)
        }
    }


async def _context_recent(days: int = 7, limit: int = 20) -> dict[str, Any]:
    """Show recently modified entities.

    Args:
        days: Number of days to look back
        limit: Maximum number of files to return

    Returns:
        List of recently modified files
    """
    ws = get_workspace()
    data_dir = ws / "data"

    if not data_dir.exists():
        return {"error": "No data/ directory found in workspace"}

    # Collect all markdown files with modification times
    now = datetime.now().timestamp()
    cutoff = now - (days * 86400)

    recent_files = []
    for md_file in data_dir.glob("**/*.md"):
        mtime = md_file.stat().st_mtime
        if mtime >= cutoff:
            time_ago_seconds = now - mtime
            # Format time ago
            if time_ago_seconds < 60:
                time_ago = "just now"
            elif time_ago_seconds < 3600:
                minutes = int(time_ago_seconds / 60)
                time_ago = f"{minutes}m ago"
            elif time_ago_seconds < 86400:
                hours = int(time_ago_seconds / 3600)
                time_ago = f"{hours}h ago"
            else:
                days_ago = int(time_ago_seconds / 86400)
                time_ago = f"{days_ago}d ago"

            recent_files.append({
                "path": str(md_file.relative_to(data_dir)),
                "modified": time_ago,
                "timestamp": int(mtime),
            })

    # Sort by modification time (newest first)
    recent_files.sort(key=lambda x: x["timestamp"], reverse=True)

    # Apply limit
    recent_files = recent_files[:limit]

    return {
        "count": len(recent_files),
        "files": recent_files,
        "days": days,
    }


async def _workspace_init(path: str | None = None) -> dict[str, Any]:
    """Initialize a new motoko workspace.

    Args:
        path: Workspace path (defaults to current directory)

    Returns:
        Initialization results
    """
    ws_path = Path(path) if path else get_workspace()

    created = []
    errors = []

    # Create directory structure
    dirs_to_create = [
        "data/tasks",
        "data/projects",
        "data/companies",
        "data/journal",
        "data/sessions",
        "data/experiments",
        "data/inbox",
        "context",
        "roles",
        "img",
    ]

    for dir_path_str in dirs_to_create:
        dir_path = ws_path / dir_path_str
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            created.append(dir_path_str)
        except Exception as e:
            errors.append({
                "path": dir_path_str,
                "error": str(e)
            })

    # Create context/README.md if it doesn't exist
    context_readme = ws_path / "context" / "README.md"
    if not context_readme.exists():
        context_readme.write_text(f"""# {ws_path.name}

## Overview

Project overview and goals.

## Current State

Current project status and context.

## Key Information

Important information and links.
""")
        created.append("context/README.md")

    # Create .gitignore if it doesn't exist
    gitignore = ws_path / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(""".venv/
__pycache__/
*.pyc
.DS_Store
""")
        created.append(".gitignore")

    # Initialize git if not already
    git_dir = ws_path / ".git"
    if not git_dir.exists():
        try:
            import subprocess
            subprocess.run(
                ["git", "init"],
                cwd=ws_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "add", "."],
                cwd=ws_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initialize motoko workspace"],
                cwd=ws_path,
                check=True,
                capture_output=True,
            )
            created.append(".git (initialized)")
        except Exception as e:
            errors.append({
                "path": ".git",
                "error": str(e)
            })

    return {
        "success": len(errors) == 0,
        "workspace": str(ws_path),
        "created": created,
        "errors": errors,
        "message": f"Initialized motoko workspace at {ws_path}" if len(errors) == 0 else "Initialization completed with errors"
    }


async def _task_list(
    status: str | None = None,
    project: str | None = None,
    limit: int = 50
) -> dict[str, Any]:
    """List tasks with filters.

    Args:
        status: Filter by status
        project: Filter by project CODE
        limit: Maximum number of tasks

    Returns:
        Dictionary with task list
    """
    ws = get_workspace()
    tm = TaskManager(ws)

    # Parse status filter
    status_filter = None
    if status:
        status_map = {
            "open": TaskStatus.OPEN,
            "in_progress": TaskStatus.IN_PROGRESS,
            "completed": TaskStatus.COMPLETED,
            "cancelled": TaskStatus.CANCELLED,
        }
        status_filter = status_map.get(status)

    # Get tasks
    tasks = tm.list_tasks(status=status_filter, limit=limit)

    # Filter by project if specified
    if project:
        tasks = [t for t in tasks if project.upper() in t.name.upper()]

    # Format results
    task_list = []
    for task in tasks:
        task_list.append({
            "number": task.number,
            "name": task.name,
            "status": task.status.value,
            "file": str(task.file_path.relative_to(ws)),
            "title": task.title,
        })

    return {
        "count": len(task_list),
        "tasks": task_list,
    }


async def _task_show(task_id: int) -> dict[str, Any]:
    """Show complete task details.

    Args:
        task_id: Task number

    Returns:
        Complete task details with markdown content
    """
    ws = get_workspace()
    tm = TaskManager(ws)

    task = tm.get_task(task_id, load_content=True)
    if not task:
        return {"error": f"Task {task_id} not found"}

    return {
        "number": task.number,
        "name": task.name,
        "status": task.status.value,
        "file": str(task.file_path.relative_to(ws)),
        "title": task.title,
        "content": task.content,
    }


async def _task_create(
    title: str,
    description: str = "",
    project: str | None = None,
    priority: str | None = None
) -> dict[str, Any]:
    """Create a new task.

    Args:
        title: Task title
        description: Task description
        project: Project CODE
        priority: Task priority

    Returns:
        Created task details
    """
    ws = get_workspace()
    tm = TaskManager(ws)

    # Build task name from title and project
    import re
    name = title.lower().replace(" ", "-")
    name = re.sub(r"[^a-z0-9-]", "", name)

    if project:
        name = f"{project.upper()}-{name}"

    # Build description with frontmatter
    frontmatter_parts = [f"title: {title}"]
    if project:
        frontmatter_parts.append(f"project: {project.upper()}")
    if priority:
        frontmatter_parts.append(f"priority: {priority}")

    full_description = "---\n" + "\n".join(frontmatter_parts) + "\n---\n\n"
    if description:
        full_description += description
    else:
        full_description += f"# {title}\n\n## Description\n\n## Execution\n\n"

    # Create task
    task = tm.create_task(name, full_description)

    return {
        "number": task.number,
        "name": task.name,
        "file": str(task.file_path.relative_to(ws)),
        "title": title,
        "message": f"Created task {task.number:06d}: {name}"
    }


async def _task_complete(task_ids: list[int]) -> dict[str, Any]:
    """Mark tasks as completed (atomic operation).

    Args:
        task_ids: List of task numbers

    Returns:
        Results with completed and errors
    """
    ws = get_workspace()
    tm = TaskManager(ws)

    completed = []
    errors = []

    for task_id in task_ids:
        try:
            task = tm.complete_task(task_id)
            if task:
                completed.append({
                    "number": task.number,
                    "name": task.name,
                    "file": str(task.file_path.relative_to(ws))
                })
            else:
                errors.append({
                    "task_id": task_id,
                    "error": "Task not found"
                })
        except Exception as e:
            errors.append({
                "task_id": task_id,
                "error": str(e)
            })

    return {
        "completed": completed,
        "errors": errors,
        "count": len(completed)
    }


async def _task_cancel(task_ids: list[int]) -> dict[str, Any]:
    """Mark tasks as cancelled (atomic operation).

    Args:
        task_ids: List of task numbers

    Returns:
        Results with cancelled and errors
    """
    ws = get_workspace()
    tm = TaskManager(ws)

    cancelled = []
    errors = []

    for task_id in task_ids:
        try:
            task = tm.cancel_task(task_id)
            if task:
                cancelled.append({
                    "number": task.number,
                    "name": task.name,
                    "file": str(task.file_path.relative_to(ws))
                })
            else:
                errors.append({
                    "task_id": task_id,
                    "error": "Task not found"
                })
        except Exception as e:
            errors.append({
                "task_id": task_id,
                "error": str(e)
            })

    return {
        "cancelled": cancelled,
        "errors": errors,
        "count": len(cancelled)
    }


async def _task_reopen(task_id: int) -> dict[str, Any]:
    """Reopen a completed or cancelled task.

    Args:
        task_id: Task number

    Returns:
        Reopened task details
    """
    ws = get_workspace()
    tm = TaskManager(ws)

    task = tm.reopen_task(task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

    return {
        "number": task.number,
        "name": task.name,
        "status": task.status.value,
        "file": str(task.file_path.relative_to(ws)),
        "message": f"Reopened task {task.number:06d}"
    }


async def _project_list(status: str | None = None) -> dict[str, Any]:
    """List projects with optional status filter."""
    ws = get_workspace()
    pm = ProjectManager(ws)

    status_filter = None
    if status:
        status_filter = ProjectStatus(status)

    projects = pm.list_projects(status=status_filter)

    project_list = []
    for project in projects:
        project_list.append({
            "code": project.code,
            "name": project.name,
            "type": project.type.value,
            "status": project.status.value,
            "file": str(project.file_path.relative_to(ws)),
        })

    return {
        "count": len(project_list),
        "projects": project_list,
    }


async def _project_show(code: str) -> dict[str, Any]:
    """Show complete project details."""
    ws = get_workspace()
    pm = ProjectManager(ws)

    project = pm.get_project(code, load_content=True)
    if not project:
        return {"error": f"Project {code} not found"}

    return {
        "code": project.code,
        "name": project.name,
        "type": project.type.value,
        "status": project.status.value,
        "file": str(project.file_path.relative_to(ws)),
        "content": project.content,
    }


async def _project_create(
    code: str,
    name: str,
    type: str,
    company: str | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Create a new project."""
    ws = get_workspace()
    pm = ProjectManager(ws)

    try:
        project_type = ProjectType(type)
        project = pm.create_project(
            code=code,
            name=name,
            type=project_type,
            company=company,
            description=description,
        )

        return {
            "code": project.code,
            "name": project.name,
            "type": project.type.value,
            "file": str(project.file_path.relative_to(ws)),
            "message": f"Created project {code}: {name}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _project_update(
    code: str,
    status: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Update project metadata."""
    ws = get_workspace()
    pm = ProjectManager(ws)

    try:
        status_enum = ProjectStatus(status) if status else None
        project = pm.update_project(code=code, status=status_enum, name=name)

        if not project:
            return {"error": f"Project {code} not found"}

        return {
            "code": project.code,
            "name": project.name,
            "status": project.status.value,
            "file": str(project.file_path.relative_to(ws)),
            "message": f"Updated project {code}"
        }
    except Exception as e:
        return {"error": str(e)}


async def _company_list() -> dict[str, Any]:
    """List all companies."""
    ws = get_workspace()
    cm = CompanyManager(ws)

    companies = cm.list_companies()

    company_list = []
    for company in companies:
        company_list.append({
            "code": company.code,
            "name": company.name,
            "relationship": company.relationship.value,
            "industry": company.industry,
            "file": str(company.file_path.relative_to(ws)),
        })

    return {
        "count": len(company_list),
        "companies": company_list,
    }


async def _company_show(code: str) -> dict[str, Any]:
    """Show complete company details."""
    ws = get_workspace()
    cm = CompanyManager(ws)

    company = cm.get_company(code, load_content=True)
    if not company:
        return {"error": f"Company {code} not found"}

    return {
        "code": company.code,
        "name": company.name,
        "relationship": company.relationship.value,
        "industry": company.industry,
        "website": company.website,
        "file": str(company.file_path.relative_to(ws)),
        "content": company.content,
    }


async def _company_create(
    code: str,
    name: str,
    relationship: str,
    industry: str | None = None,
    website: str | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Create a new company."""
    ws = get_workspace()
    cm = CompanyManager(ws)

    try:
        rel_enum = CompanyRelationship(relationship)
        company = cm.create_company(
            code=code,
            name=name,
            relationship=rel_enum,
            industry=industry,
            website=website,
            description=description,
        )

        return {
            "code": company.code,
            "name": company.name,
            "relationship": company.relationship.value,
            "file": str(company.file_path.relative_to(ws)),
            "message": f"Created company {code}: {name}"
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# SERVER ENTRY POINT
# =============================================================================

def serve():
    """Start MCP server via stdio."""
    global workspace

    # Set workspace from environment or cwd
    import os
    workspace_path = os.environ.get("MOTOKO_WORKSPACE", str(Path.cwd()))
    workspace = Path(workspace_path)

    # Run server
    async def run_server():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )

    asyncio.run(run_server())


if __name__ == "__main__":
    serve()
