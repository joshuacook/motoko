# Motoko: Rails for Context

**Context management framework for AI-powered workflows**

Motoko is to context management what Rails is to web applications - enforced conventions, smart querying, and safe operations for managing project context, tasks, and entities.

## Features

- **🔧 MCP Native**: Built for Claude Code via Model Context Protocol
- **📋 Smart Context Discovery**: Single tool call aggregates complete project state
- **✅ Task Management**: Full lifecycle with validation and atomic operations
- **🏢 Entity Management**: Projects, companies, journal entries, experiments
- **🛡️ Safe Operations**: Validation, auto-commit, atomic operations
- **🎭 Convention Enforcement**: Rails-like structure ensures consistency

## Architecture

```
┌─────────────────────────────────┐
│   Claude Code (MCP Client)      │
│   • Auto-discovers motoko tools │
│   • Calls tools with typed params│
└───────────────┬─────────────────┘
                │ MCP Protocol (stdio)
┌───────────────▼─────────────────┐
│   Motoko MCP Server             │
│   • 20+ tools for context mgmt  │
│   • Direct filesystem access    │
│   • Git auto-commit             │
├─────────────────────────────────┤
│   Data Lake (markdown + git)    │
│   • data/tasks/                 │
│   • data/projects/              │
│   • data/companies/             │
│   • context/README.md           │
└─────────────────────────────────┘
```

## Installation

```bash
# Clone and install
cd ~/working
git clone <repository-url> motoko
cd motoko
uv sync

# Verify installation
uv run motoko --help
```

## Configuration

### Claude Code Integration

Add motoko to Claude Code's MCP settings:

**`~/.config/claude-code/mcp_settings.json`:**
```json
{
  "mcpServers": {
    "motoko": {
      "command": "uv",
      "args": ["--directory", "/Users/YOUR_USERNAME/working/motoko", "run", "motoko", "serve-mcp"]
    }
  }
}
```

**Important:** Replace `/Users/YOUR_USERNAME/working/motoko` with your actual motoko installation path.

### Restart Claude Code

After configuring MCP settings, restart Claude Code. Motoko tools will be automatically discovered and available.

## Quick Start

### 1. Initialize a New Workspace

```bash
cd ~/working/my-project
```

In Claude Code:
```
User: "Initialize a motoko workspace here"
Claude: [Calls workspace_init tool]
```

This creates:
```
my-project/
├── data/
│   ├── tasks/
│   ├── projects/
│   ├── companies/
│   ├── journal/
│   └── ...
├── context/
│   └── README.md
├── roles/
└── img/
```

### 2. Get Project State

```
User: "What's the current state of this project?"
Claude: [Calls context_summary tool]
```

Returns complete workspace state in one call:
- Task counts (open, completed, cancelled)
- Available projects and companies
- Recent git activity
- Available roles

### 3. Manage Tasks

```
User: "Create a task to implement authentication for the API project"
Claude: [Calls task_create(title="Implement authentication", project="API")]

User: "Show me all open tasks"
Claude: [Calls task_list(status="open")]

User: "Mark tasks 11 and 12 as complete"
Claude: [Calls task_complete([11, 12])]
```

### 4. Manage Projects

```
User: "Create a project called NEW_APP for a startup"
Claude: [Calls project_create(code="NEW_APP", name="New App", type="startup")]

User: "List all active projects"
Claude: [Calls project_list(status="Active")]
```

## Available Tools

Motoko provides 20+ MCP tools organized by function:

### Context Discovery
- **context_summary** - Complete workspace state in one call
- **context_entities** - List all entities by type
- **context_validate** - Validate workspace conventions
- **context_recent** - Recently modified files

### Task Management
- **task_list** - List tasks with filters
- **task_show** - Show complete task details
- **task_create** - Create task with validation
- **task_complete** - Mark tasks complete (atomic + git)
- **task_cancel** - Cancel tasks
- **task_reopen** - Reopen completed tasks

### Project Management
- **project_list** - List all projects
- **project_show** - Show project details
- **project_create** - Create new project
- **project_update** - Update project metadata

### Company Management
- **company_list** - List all companies
- **company_show** - Show company details
- **company_create** - Create new company

### Workspace Management
- **workspace_init** - Initialize new workspace

## Conventions

Motoko enforces Rails-like conventions for consistency:

### Task Naming
```
000001-PROJECT-task-name.md           # Open
000001-COMPLETED-PROJECT-task-name.md # Completed
000001-CANCELLED-PROJECT-task-name.md # Cancelled
```

- 6-digit zero-filled numbers (000001, 000002, ...)
- PROJECT CODE in uppercase
- Kebab-case slugs

### Project/Company Codes
```
DEMAND.md          # Project code
CHELLE.md          # Company code
GEORGIA_TECH.md    # Underscores allowed
```

- Uppercase letters, numbers, underscores only
- No spaces or special characters

### Frontmatter Schema

Tasks:
```yaml
---
title: Task Title
project: PROJECT_CODE
priority: high
status: To Do
---
# Task description
```

Projects:
```yaml
---
code: PROJECT_CODE
name: Full Project Name
type: startup|consulting|creative|academic|employment
status: Active|Paused|Archived
---
# Project context
```

## Benefits

### vs. Manual File Operations

**Before (manual):**
```bash
# 10+ commands to understand project
ls data/tasks/
cat data/tasks/000001-task.md
cat data/tasks/000002-task.md
# ... repeat for each file
git log --oneline -5
cat context/README.md
```

**After (motoko):**
```
Claude: [Calls context_summary()]
# Returns complete state in one call
```

**Result:** 10x faster context discovery

### vs. Unstructured Files

**Before:**
- Inconsistent naming (`task1.md`, `TODO_2.md`, `fix-bug.md`)
- Missing metadata
- No validation
- Manual git commits

**After:**
- Enforced naming conventions
- Validated frontmatter
- Auto-validation
- Auto-git commits

**Result:** Zero convention violations, consistent structure

## Development

### Project Structure

```
motoko/
├── motoko/
│   ├── cli/            # CLI commands
│   ├── mcp/            # MCP server
│   ├── tasks/          # Task manager
│   ├── projects/       # Project manager
│   ├── companies/      # Company manager
│   └── tools/          # Agent tools
├── MOTOKO_SPEC.md      # Complete specification
├── CONVENTIONS.md       # Entity conventions
└── README.md           # This file
```

### Testing

```bash
# Run tests
uv run pytest

# Test MCP server manually
cd ~/working/test-workspace
uv --directory ~/working/motoko run motoko serve-mcp
```

## Troubleshooting

### Tools Not Appearing in Claude Code

1. Check MCP settings path is correct
2. Restart Claude Code completely
3. Verify motoko installation: `uv run motoko --help`
4. Check Claude Code logs for MCP errors

### Git Auto-Commit Not Working

Motoko requires a git repository:
```bash
cd your-workspace
git init
git add .
git commit -m "Initial commit"
```

### Validation Errors

Run validation with auto-fix:
```
User: "Validate this workspace and fix issues"
Claude: [Calls context_validate(fix=true)]
```

## Roadmap

### Completed (MVP)
- ✅ MCP server with stdio transport
- ✅ Context discovery tools
- ✅ Complete task lifecycle management
- ✅ Project and company management
- ✅ Workspace validation and initialization

### Future
- 🚧 MCP resources for direct context file access
- 🚧 Journal and experiment management
- 🚧 Inbox workflow automation
- 🚧 Context graph visualization
- 🚧 Full-text search across entities
- 🚧 Multi-workspace support

## Documentation

- **MOTOKO_SPEC.md** - Complete technical specification
- **CONVENTIONS.md** - Entity schemas and naming patterns
- **Architecture diagrams** - See MOTOKO_SPEC.md

## Philosophy

> "Convention over Configuration + ActiveRecord for Data Lake"

Motoko brings Rails philosophy to AI context management:
1. **Conventions** enforce consistency (like Rails migrations)
2. **Smart querying** aggregates state (like ActiveRecord)
3. **Safe operations** prevent errors (like Rails validations)
4. **Scaffolding** bootstraps structure (like Rails generators)

The result: **Rails for Context Management**

## Name Origin

**Major Motoko Kusanagi** from *Ghost in the Shell* - an agent that dives into different contexts, switches roles, and interfaces seamlessly with systems.

## License

MIT

## Contributing

Contributions welcome! Please file issues or submit pull requests.

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Status**: MVP Complete
**Version**: 1.0.0
**Last Updated**: 2025-01-19
