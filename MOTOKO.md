# Motoko: The Context Lake System

## Overview

Motoko is a personal knowledge management system built on the Context Lake pattern - a filesystem-first approach where:

- **Workspaces are git repos** - Each domain of knowledge is a self-contained directory
- **Entities are markdown files** - Tasks, projects, notes stored as `.md` files with YAML frontmatter
- **Claude Code is the interface** - Interactive AI assistant for working with your knowledge
- **Tachikoma maintains hygiene** - Batch cleanup agent that proposes structural improvements

## Components

| Component | Role | Type |
|-----------|------|------|
| **Motoko** | The overall system and Claude Code persona | System |
| **Batou** | MCP server for structured entity operations | MCP Server |
| **Tachikoma** | Workspace maintenance agent | CLI Tool |

All names from Ghost in the Shell - Section 9 team.

## How It Works

```
You ←→ Claude Code (Motoko) ←→ Workspace (Git Repo)
                ↓
         Optional: Batou MCP
                ↓
    Periodic: Tachikoma cleanup
```

### Daily Workflow

1. **Open a workspace** in Claude Code
2. **Work naturally** - create tasks, write notes, update projects
3. **Claude (Motoko) understands** the workspace schema and conventions
4. **Periodically run Tachikoma** to propose cleanup
5. **Review and approve** structural improvements

### Workspace Structure

Each workspace follows this pattern:

```
{workspace}/
├── .claude/
│   ├── schema.yaml              # Entity type definitions
│   ├── tachikoma-summary.yaml   # Maintenance agent state
│   └── skills/                  # Workspace-specific skills
├── roles/                       # AI persona definitions
├── docs/                        # Documentation
├── tasks/                       # Task entities
├── projects/                    # Project entities
├── decisions/                   # Tachikoma proposals
└── {other}/                     # Per schema.yaml
```

## Entity Format

All entities are markdown files with YAML frontmatter:

```markdown
---
status: open
priority: high
due: 2024-01-20
---

# Build landing page

Content here...
```

The schema defines what fields are required/optional for each entity type.

## Why This Approach?

| Principle | Benefit |
|-----------|---------|
| **Filesystem-first** | Standard tools work (grep, git, any editor) |
| **Markdown + YAML** | Human-readable, portable, no lock-in |
| **Schema optional** | Structure when you want it, flexibility when you don't |
| **AI-native** | Claude Code understands and works with the structure |
| **Git-backed** | Version history, backup, sync built-in |

## Current Workspaces

- **project-management** - Tasks, projects, companies for work
- **personal** - Personal decisions and fitness tracking
- **escuela** - Homeschool curriculum and worksheets
- **coyote** - Music production, songs, ideas

## Getting Started

1. Clone or create a workspace directory
2. Add `.claude/schema.yaml` defining your entity types
3. Open in Claude Code
4. Start creating entities - Claude knows the conventions

## Documentation

- [CONTEXT_LAKE.md](CONTEXT_LAKE.md) - Architecture deep-dive
- [BATOU.md](BATOU.md) - MCP server specification
- [TACHIKOMA.md](TACHIKOMA.md) - Maintenance agent specification
- [CLAUDE.md](CLAUDE.md) - System prompt for Claude Code
- [ROADMAP.md](ROADMAP.md) - Project roadmap
