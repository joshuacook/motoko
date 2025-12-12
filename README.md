# Motoko

Personal knowledge management using the Context Lake pattern.

## Overview

Motoko is a filesystem-first approach to personal knowledge management:

- **Workspaces are git repos** - Each workspace is a self-contained directory with its own schema and history
- **Entities are markdown files** - Tasks, notes, projects, journal entries stored as `.md` files with YAML frontmatter
- **Claude Code as the interface** - Use Claude Code directly on your filesystem to work with entities
- **Tachikoma for maintenance** - A batch job that proposes cleanup via decision files

All names from Ghost in the Shell - Section 9 team.

## Structure

```
~/working/motoko/
├── README.md              # This file
├── MOTOKO.md              # System overview
├── CONTEXT_LAKE.md        # Architecture documentation
├── BATOU.md               # MCP server specification
├── TACHIKOMA.md           # Maintenance agent specification
├── CLAUDE.md              # System prompt (for Claude Code)
├── ROADMAP.md             # Project roadmap
├── batou/                 # MCP server (structured entity tools)
│   ├── pyproject.toml
│   ├── README.md
│   └── src/batou/
├── tachikoma/             # Maintenance agent CLI
│   ├── pyproject.toml
│   └── src/tachikoma/
└── workspaces/            # Your workspaces
    ├── coyote/            # Music production
    ├── escuela/           # Teaching/education
    ├── personal/          # Personal tasks
    └── project-management/
```

## Workspace Structure

Each workspace follows this pattern:

```
{workspace}/
├── .mcp.json                    # Batou MCP server config
├── .claude/
│   ├── schema.yaml              # Entity type definitions
│   └── tachikoma-summary.yaml   # Tachikoma's workspace understanding
├── roles/                       # Role definitions
├── docs/                        # Documentation
├── tasks/                       # Task entities
├── projects/                    # Project entities
├── journal/                     # Journal entries (if applicable)
├── decisions/                   # Tachikoma cleanup proposals
└── {other}/                     # Per schema.yaml
```

## Usage

### Working with Claude Code (Motoko)

Open a workspace in Claude Code:

```bash
cd ~/working/motoko/workspaces/personal
claude
```

Claude Code can work with entities two ways:

1. **Unstructured** - Direct file operations (Read, Write, Glob). Full flexibility.
2. **Structured** - Batou MCP tools (`list_entities`, `create_entity`, etc.). Schema-aware.

### Setting up Batou

Install the Batou MCP server:

```bash
cd ~/working/motoko/batou
uv sync
```

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

Now Claude Code has both raw file access AND structured entity tools.

### Running Tachikoma

Tachikoma is a CLI tool built on the Claude Agent SDK. Run cleanup on a workspace:

```bash
cd ~/working/motoko/tachikoma
uv run tachikoma schema /path/to/workspace
uv run tachikoma frontmatter /path/to/workspace
uv run tachikoma structure /path/to/workspace
```

Review generated decisions:

```bash
ls /path/to/workspace/decisions/
```

## Entity Types

Each workspace defines its own entity types in `.claude/schema.yaml`. Common patterns:

### Tasks
```yaml
---
status: open  # open, in_progress, done, blocked, cancelled
---
```

### Projects
```yaml
---
code: PROJ
name: Project Name
status: Active
---
```

### Journal
```yaml
---
date: 2024-01-15
---
```

## Documentation

- [MOTOKO.md](MOTOKO.md) - System overview
- [CONTEXT_LAKE.md](CONTEXT_LAKE.md) - Architecture documentation
- [BATOU.md](BATOU.md) - MCP server specification
- [TACHIKOMA.md](TACHIKOMA.md) - Maintenance agent specification
- [CLAUDE.md](CLAUDE.md) - System prompt for Claude Code
- [ROADMAP.md](ROADMAP.md) - Project roadmap
