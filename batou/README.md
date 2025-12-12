# Batou - Entity MCP Server

MCP server providing structured entity operations for Context Lake workspaces.

## Overview

Batou provides a semantic layer over filesystem operations. While Claude Code can read/write files directly, Batou offers **typed entity operations** that are schema-aware:

- Knows entity types (tasks, notes, projects, etc.)
- Applies frontmatter defaults from schema
- Validates required fields
- Generates correct file paths/names

**Use both together:**
- Raw file operations for flexibility
- Batou for structured entity work

## Installation

```bash
cd ~/working/motoko/batou
uv sync
```

## Claude Code Configuration

Add `.mcp.json` to your workspace root:

```json
{
  "mcpServers": {
    "batou": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/motoko/batou", "batou"],
      "env": {
        "WORKSPACE_PATH": "/path/to/workspace"
      }
    }
  }
}
```

If `WORKSPACE_PATH` is not set, Batou uses the current working directory.

Note: Claude Code will prompt you to approve project-scoped MCP servers the first time.

## Tools

### list_entities

List entities of a given type with optional filtering.

```
list_entities(entity_type="tasks", status="open", limit=20)
```

Returns: entity IDs, titles, status, paths, frontmatter

### get_entity

Get a specific entity by type and ID.

```
get_entity(entity_type="tasks", entity_id="build-landing-page")
```

Returns: frontmatter and full content

### create_entity

Create a new entity with frontmatter and content.

```
create_entity(
    entity_type="tasks",
    frontmatter={"title": "Build landing page", "slug": "build-landing-page"},
    content="# Build landing page\n\nDesign and implement..."
)
```

- Applies schema defaults (e.g., `status: open`)
- Validates required fields
- Generates filename from schema pattern

### update_entity

Update an existing entity.

```
update_entity(
    entity_type="tasks",
    entity_id="build-landing-page",
    frontmatter={"status": "done"}
)
```

- Merges frontmatter with existing
- Optionally replaces content

### delete_entity

Delete an entity.

```
delete_entity(entity_type="tasks", entity_id="build-landing-page")
```

### search_entities

Search entities by text content.

```
search_entities(query="landing page", entity_type="tasks", limit=10)
```

Simple case-insensitive substring match across title and content.

### get_schema

Get workspace schema information.

```
get_schema()
```

Returns: defined entity types and their configuration

## Schema

Batou reads `.claude/schema.yaml` from the workspace:

```yaml
entities:
  tasks:
    directory: tasks
    naming: "{slug}.md"
    frontmatter:
      required: [status]
      defaults:
        status: open

  journal:
    directory: journal
    naming: "{date}.md"
    frontmatter:
      required: [date]
```

**No schema?** Batou uses sensible defaults:
- Directory: `{entity_type}/`
- Naming: `{slug}.md`
- No required fields or defaults

## Example Session

```
User: Create a task to review the PR

Claude (using Batou):
create_entity(
    entity_type="tasks",
    frontmatter={
        "title": "Review the PR",
        "slug": "review-the-pr",
        "priority": "high"
    },
    content="# Review the PR\n\nReview and approve the pending pull request."
)

Result: Created tasks/review-the-pr.md with status: open (from default)
```

```
User: What tasks are open?

Claude (using Batou):
list_entities(entity_type="tasks", status="open")

Result: 3 open tasks - review-the-pr, build-landing-page, fix-auth-bug
```

## Why Batou + Raw Files?

**Batou** when you want:
- Schema enforcement
- Frontmatter defaults
- Entity-level operations
- List/filter by type and status

**Raw Read/Write/Glob** when you want:
- Full flexibility
- Non-entity files
- Bulk operations
- Custom file structures

They coexist. Batou doesn't take away file access - it adds entity semantics on top.
