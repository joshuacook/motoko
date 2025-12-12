# Batou: Entity MCP Server

## Overview

Batou is an MCP (Model Context Protocol) server that provides **structured entity operations** for Context Lake workspaces. While Claude Code can read/write files directly, Batou adds a semantic layer:

- **Schema-aware** - Knows entity types and their fields
- **Default application** - Applies frontmatter defaults from schema
- **Validation** - Checks required fields
- **Path generation** - Creates correct filenames from schema patterns

Named after Batou from Ghost in the Shell - Section 9's field operative who goes out and gets things done.

## When to Use

**Use Batou** for:
- Creating/updating entities with proper frontmatter
- Listing entities by type with filtering
- Schema-enforced operations

**Use raw file ops** for:
- Full flexibility
- Non-entity files
- Bulk operations
- Custom structures

Both coexist - Batou doesn't replace file access, it adds entity semantics on top.

## Installation

```bash
cd ~/working/motoko/batou
uv sync
```

## Configuration

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

If `WORKSPACE_PATH` is not set, uses current working directory.

Note: Claude Code will prompt you to approve project-scoped MCP servers the first time.

## Tools

| Tool | Description |
|------|-------------|
| `list_entities` | List entities of a type with optional filtering |
| `get_entity` | Get a specific entity by type and ID |
| `create_entity` | Create entity with frontmatter and content |
| `update_entity` | Update existing entity |
| `delete_entity` | Delete an entity |
| `search_entities` | Search by text content |
| `get_schema` | Get workspace schema information |

### list_entities

```python
list_entities(entity_type="tasks", status="open", limit=20)
```

Returns: entity IDs, titles, status, paths, frontmatter

### get_entity

```python
get_entity(entity_type="tasks", entity_id="build-landing-page")
```

Returns: frontmatter and full content

### create_entity

```python
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

```python
update_entity(
    entity_type="tasks",
    entity_id="build-landing-page",
    frontmatter={"status": "done"}
)
```

- Merges frontmatter with existing
- Optionally replaces content

### delete_entity

```python
delete_entity(entity_type="tasks", entity_id="build-landing-page")
```

### search_entities

```python
search_entities(query="landing page", entity_type="tasks", limit=10)
```

Simple case-insensitive substring match across title and content.

### get_schema

```python
get_schema()
```

Returns: defined entity types and their configuration

## Schema Integration

Batou reads `.claude/schema.yaml`:

```yaml
entities:
  tasks:
    directory: tasks
    naming: "{slug}.md"
    frontmatter:
      required: [status]
      defaults:
        status: open

  projects:
    directory: projects
    naming: "{code}.md"
    frontmatter:
      required: [code, name, status]
```

**No schema?** Falls back to:
- Directory: `{entity_type}/`
- Naming: `{slug}.md`
- No required fields or defaults

## Architecture

```
Claude Code (Motoko)
    │
    ├── Raw file ops (Read, Write, Glob, Grep)
    │
    └── Batou MCP ──→ Schema-aware entity operations
                          │
                          ▼
                    Workspace files
                    (tasks/*.md, projects/*.md, etc.)
```

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
    content="# Review the PR\n\nReview and approve..."
)

Result: Created tasks/review-the-pr.md with status: open (from default)
```

## See Also

- [batou/README.md](batou/README.md) - Implementation details
- [CONTEXT_LAKE.md](CONTEXT_LAKE.md) - Architecture overview
- [CLAUDE.md](CLAUDE.md) - System prompt that teaches entity conventions
