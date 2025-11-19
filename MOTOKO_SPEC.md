# Motoko Specification: Rails for Context

**Version:** 1.0
**Date:** 2025-01-19
**Philosophy:** Convention over Configuration + ActiveRecord for Data Lake

---

## Vision

Motoko is to context management what Rails is to web applications:
- **Enforced conventions** (like Rails migrations and models)
- **Smart querying** (like ActiveRecord)
- **Safe operations** (validation, transactions, auto-commit)
- **Scaffolding** (generate entities from templates)
- **MCP-first design** (native integration with Claude Code via Model Context Protocol)

### The Problem

When using Claude Code with complex projects:
1. **Manual context discovery** - ls, cat, grep across many files
2. **No enforcement** - easy to break conventions (wrong file naming, missing frontmatter)
3. **Unsafe operations** - rename files incorrectly, forget git commits
4. **Scattered state** - tasks, projects, journal entries with no unified view

### The Solution

Motoko provides:
1. **Smart discovery** - `context_summary` tool aggregates all project state
2. **Enforced conventions** - Tools validate and enforce CONVENTIONS.md spec
3. **Safe operations** - Atomic operations with validation and auto-commit
4. **Native integration** - MCP server exposes tools directly to Claude Code
5. **Zero configuration** - Claude discovers tools automatically on workspace open

---

## Architecture

### MCP Server Architecture

```
┌─────────────────────────────────────────┐
│   Claude Code (MCP Client)               │
│   • Discovers tools on workspace open   │
│   • Calls tools with typed parameters    │
└────────────────┬────────────────────────┘
                 │ MCP Protocol (stdio)
┌────────────────▼────────────────────────┐
│   MCP Server (long-running process)     │
│   • Exposes tools (functions)            │
│   • Exposes resources (context files)    │
│   • Validates operations                 │
├─────────────────────────────────────────┤
│   Entity Managers (business logic)      │  ← Enforce conventions
│   • TaskManager, ProjectManager, etc.   │
├─────────────────────────────────────────┤
│   Data Lake (markdown + git)            │  ← Source of truth
│   • Direct filesystem access            │
└─────────────────────────────────────────┘
```

### Entity Types (Universal)

Every motoko workspace has these entity types:

| Entity Type | Purpose | Lifecycle | Complexity |
|------------|---------|-----------|------------|
| tasks | Work items, todos | create → complete/cancel | High |
| projects | Project definitions | create → archive | Medium |
| companies | Organizations, clients | create → update | Low |
| journal | Narrative documentation | create → update | Low |
| sessions | Auto-generated summaries | auto-created only | N/A |
| experiments | Explorations, tests | create → validate/abandon | Medium |
| inbox | Quick captures | capture → process → delete | Low |
| img | Visual assets + metadata | add → annotate | Special |
| roles | Behavioral modes | create → load | Special |

---

## MCP Tools & Resources

### Tool Categories

Motoko exposes tools organized by entity type and function.

### 1. Context Discovery Tools (Smart Querying)

**Purpose:** Provide unified view of workspace state for Claude

#### `context_summary(format: str = "json") -> dict`
Aggregates complete project state: project context, roles, tasks, projects, git activity.

**Parameters:**
- `format`: "json" or "text"

**Returns:**
```json
{
  "workspace": {"name": "...", "path": "...", "git_clean": true},
  "project_context": {"exists": true, "summary": "..."},
  "roles": {"available": [...], "count": 2},
  "tasks": {"open": 6, "completed": 2, ...},
  "projects": {"available": [...], "count": 3},
  "recent_activity": {"last_commit": "...", ...}
}
```

#### `context_entities(type: str | None = None) -> dict`
Lists all entities by type with counts.

**Parameters:**
- `type`: Optional filter ("tasks", "projects", "companies", etc.)

**Returns:** Entity counts and filenames by type

#### `context_recent(days: int = 7) -> list`
Shows recently modified entities across all types.

**Returns:** List of recently modified files with timestamps

#### `context_validate(fix: bool = False) -> dict`
Validates workspace conventions, optionally fixes issues.

**Returns:** Validation results with errors/warnings

### 2. Task Management Tools (High Complexity)

**Purpose:** Enforce task lifecycle and conventions

#### `task_list(status: str | None = None, project: str | None = None) -> list`
Lists tasks with filters.

**Parameters:**
- `status`: "open", "completed", "cancelled", "in_progress"
- `project`: Project CODE to filter by

**Returns:** List of task objects with metadata

#### `task_show(task_id: int) -> dict`
Shows task with full content and metadata.

**Returns:** Complete task object including markdown content

#### `task_create(title: str, project: str | None = None, priority: str | None = None) -> dict`
Creates new task with validation.

**Parameters:**
- `title`: Task title
- `project`: Project CODE (validated)
- `priority`: "low", "medium", "high", "urgent"

**Returns:** Created task object with auto-assigned number

#### `task_complete(task_ids: list[int]) -> dict`
Marks task(s) as complete (atomic operation).

**Parameters:**
- `task_ids`: List of task numbers to complete

**Returns:** `{"completed": [...], "errors": [...]}`

#### `task_cancel(task_ids: list[int]) -> dict`
Marks task(s) as cancelled (atomic operation).

**Returns:** `{"cancelled": [...], "errors": [...]}`

#### `task_reopen(task_id: int) -> dict`
Reopens completed task with validation.

**Enforcement:**
- Auto-assigns next number (finds max + 1)
- Validates filename format `{number:06d}-{PROJECT}-{slug}.md`
- Validates status transitions (open → in_progress → done)
- Atomic operations (all succeed or all fail)
- Auto-commits after operations
- Validates frontmatter schema

### 3. Project Management (Medium Complexity)

**Purpose:** Manage project entities and references

```bash
motoko project list [--status active|paused|archived]
# Lists projects

motoko project show DEMAND
# Shows project with associated tasks/companies

motoko project create --code DEMAND --name "Demand Project" --type consulting
# Creates project entity (validates CODE format)

motoko project update DEMAND --status paused
# Updates project status

motoko project archive DEMAND
# Archives project (updates frontmatter, doesn't delete)

motoko project tasks DEMAND
# Lists all tasks for project
```

**Enforcement:**
- Validates CODE format (uppercase, underscores)
- Validates type enum (startup, consulting, creative, academic, employment)
- Validates status enum (Active, Paused, Archived)
- Checks frontmatter schema
- Auto-commits

### 4. Company Management (Low Complexity)

**Purpose:** Manage company/organization entities

```bash
motoko company list
motoko company show CHELLE
motoko company create --code CHELLE --name "Chelle LLC" --relationship founder
motoko company update CHELLE --website "https://chelle.ai"
motoko company projects CHELLE  # Show associated projects
```

**Enforcement:**
- Validates CODE format
- Validates relationship enum (founder, client, employer, institution)
- Checks frontmatter schema

### 5. Journal Management (Low Complexity)

**Purpose:** Manage narrative entries

```bash
motoko journal list [--since 2025-01-01]
motoko journal show 2025-01-19
motoko journal create [--title "Day one"] [--project MUSIC_BETWEEN]
# Auto-generates YYYY-MM-DD-{slug}.md from title

motoko journal today
# Opens today's journal entry (creates if not exists)
```

**Enforcement:**
- Validates date format in filename
- Checks frontmatter schema
- Auto-commits

### 6. Experiment Management (Medium Complexity)

**Purpose:** Track explorations and trials

```bash
motoko experiment list [--status exploring|validated|abandoned]
motoko experiment create --name "Magazine collage technique"
# Creates {number:03d}-{slug}.md

motoko experiment update 42 --status validated
motoko experiment abandon 42
```

**Enforcement:**
- Auto-assigns 3-digit number
- Validates status enum
- Checks frontmatter schema

### 7. Inbox Management (Low Complexity)

**Purpose:** Quick capture and processing workflow

```bash
motoko inbox list [--unprocessed]
motoko inbox capture "Meeting notes from client call"
# Creates YYYY-MM-DD-HHMM-{slug}.md

motoko inbox process 2025-01-19-1430
# Interactive: convert to task/journal/experiment

motoko inbox clear [--processed]
# Deletes processed items
```

**Enforcement:**
- Auto-generates timestamp filename
- Tracks processed status in frontmatter

### 8. Image Management (Special Case)

**Purpose:** Manage binary assets and metadata

```bash
motoko img list
motoko img add ~/Downloads/screenshot.png [--project MUSIC_BETWEEN]
# Copies to img/, optionally creates metadata .md

motoko img annotate ceuta_000012.png
# Opens editor for metadata markdown

motoko img reference ceuta_000012.png
# Returns markdown reference: ![desc](../img/ceuta_000012.png)
```

**Special handling:**
- Binary files + optional markdown metadata
- Not in data/ directory (in img/)

### 9. Role Management (Special Case)

**Purpose:** Manage behavioral mode definitions

```bash
motoko role list
motoko role show creative-sherpa
motoko role create --name project-manager [--template]
# Creates roles/{name}.md from template

motoko role edit creative-sherpa
# Opens role definition in editor
```

**Special handling:**
- Not in data/ directory (in roles/)
- No frontmatter (pure system prompt)

### 10. Generation (Scaffolding)

**Purpose:** Create entities from templates

```bash
motoko generate task --project DEMAND --template feature
motoko generate project --code NEW_PROJECT
motoko generate role --name technical-writer
motoko generate experiment --name "Test new library"

motoko generate workspace [--name my-project]
# Scaffolds entire workspace structure
```

**Scaffolding creates:**
- Directory structure
- Template files with frontmatter
- Initial git commit

### 11. Validation (Quality Control)

**Purpose:** Verify workspace follows conventions

```bash
motoko validate all [--fix]
# Validates entire workspace

motoko validate tasks [--fix]
# Validates task files (numbering, naming, frontmatter)

motoko validate schema
# Checks all frontmatter against schemas

motoko validate git
# Checks for uncommitted changes in data/

motoko doctor
# Comprehensive health check with suggestions
```

**Validation checks:**
- Filename conventions (patterns, numbering)
- Frontmatter schema (required fields, types, enums)
- Entity references (project codes exist, etc.)
- Git status (clean working directory)
- Directory structure (all entity dirs present)

---

## Data Model (Entity Schemas)

### Universal Entity Pattern

```yaml
---
# STRUCTURED DATA (schema)
field1: value
field2: value
---
# UNSTRUCTURED CONTEXT (markdown)
Free-form narrative, bullets, tables, etc.
```

### Task Schema

```yaml
---
number: string          # Auto: 000001, 000002...
title: string           # Required
status: enum            # To Do, In Progress, Blocked, Done
priority: enum          # Low, Medium, High, Urgent
project: string         # Reference: projects/{code}.md
company: string         # Reference: companies/{code}.md
created: date           # Auto
updated: date           # Auto
tags: list[string]
blocker: string
due_date: date
---
# Description, context, decisions, next steps
```

**Filename:** `{number:06d}-{project}-{slug}.md` or `{number:06d}-COMPLETED-{project}-{slug}.md`

### Project Schema

```yaml
---
code: string            # SHORT_IDENTIFIER (UPPER_CASE)
name: string
type: enum              # startup, consulting, creative, academic, employment
status: enum            # Active, Paused, Archived
company: string         # Reference: companies/{code}.md
start_date: date
end_date: date
tags: list[string]
---
# Background, goals, current state, key context
```

**Filename:** `{code}.md`

### Company Schema

```yaml
---
code: string            # SHORT_IDENTIFIER
name: string
relationship: enum      # founder, client, employer, institution
industry: string
website: string
contact: string
---
# Background, relationship context, key people
```

**Filename:** `{code}.md`

### Journal Schema

```yaml
---
date: date              # YYYY-MM-DD
title: string
tags: list[string]
project: string         # Reference
---
# Free-form narrative entry
```

**Filename:** `YYYY-MM-DD-{slug}.md`

### Session Schema (Auto-generated)

```yaml
---
date: date              # YYYY-MM-DD
topic: string           # Auto-extracted
projects: list[string]  # Auto-detected
duration: string
participants: list[string]
---
# Auto-generated summary: summary, decisions, context, next steps
```

**Filename:** `YYYY-MM-DD-{topic-slug}.md`

### Experiment Schema

```yaml
---
name: string
date: date              # When started
status: enum            # exploring, validated, abandoned
project: string         # Reference
tags: list[string]
---
# Experiment notes, process, results, learnings
```

**Filename:** `{number:03d}-{slug}.md`

### Inbox Schema

```yaml
---
date: date              # When captured
processed: boolean      # false initially
source: string
---
# Quick capture content
```

**Filename:** `YYYY-MM-DD-HHMM-{slug}.md`

---

## Integration with Claude Code (MCP)

### Configuration

User configures motoko MCP server once:

**`~/.config/claude-code/mcp_settings.json`:**
```json
{
  "mcpServers": {
    "motoko": {
      "command": "uv",
      "args": ["run", "motoko", "serve-mcp"]
    }
  }
}
```

### Automatic Discovery

When Claude Code opens a workspace:

1. **Server Launch:**
   Claude Code spawns: `cd /path/to/workspace && uv run motoko serve-mcp`

2. **Tool Discovery:**
   Server returns available tools: `context_summary`, `task_list`, `task_complete`, etc.

3. **Claude Sees Tools:**
   Tools appear in Claude's tool palette automatically

### Usage Pattern

**Before (manual bash):**
```
Claude: "Let me check the tasks..."
[Uses bash: ls data/tasks/]
[Uses bash: cat data/tasks/000001-DEMAND-chat-interface.md]
[Uses bash: cat data/tasks/000002-DEMAND-marketo-objects.md]
...10+ commands to understand workspace
```

**After (MCP tools):**
```
Claude: "Let me check the workspace state..."
[Calls tool: context_summary()]
[Gets: complete project state in one call]

Claude: "I see 6 open tasks, 3 active projects. Let me complete tasks 11 and 12..."
[Calls tool: task_complete([11, 12])]
[Gets: {"completed": [11, 12]}]
Claude: "Done! Tasks 11 and 12 are now complete."
```

### Benefits

- **Zero friction:** No bash command construction
- **Typed parameters:** task_complete([11, 12]) not "11 12"
- **Structured results:** JSON responses, not text parsing
- **Atomic operations:** All-or-nothing with validation
- **Auto-discovery:** Claude sees all tools on workspace open

---

## MVP Scope (MCP-First)

### Phase 1: MCP Server + Core Discovery (Week 1)
**Goal:** Get MCP server running with basic context discovery

**Implementation:**
- MCP server bootstrap (`motoko serve-mcp` command)
- MCP protocol implementation (stdio transport)
- `context_summary()` tool (aggregates all workspace state)
- `context_entities()` tool (list entity types)
- `task_list()` tool (with filters)

**Testing:**
- Manual MCP client testing
- Integration with Claude Code Desktop
- Verify tool discovery and calling

**Deliverable:** Claude Code can discover motoko tools and call `context_summary()`

### Phase 2: Task Operations (Week 2)
**Goal:** Complete task lifecycle with validation

**Implementation:**
- `task_create()` tool (with number assignment)
- `task_complete()` tool (atomic renames + git commit)
- `task_cancel()` tool (atomic operation)
- `task_show()` tool (full task details)
- Validation layer (frontmatter schema, filename patterns)
- Error handling and rollback

**Testing:**
- Multi-task atomic operations
- Validation edge cases
- Git integration

**Deliverable:** Claude can safely manage complete task lifecycle

### Phase 3: Project & Company Management (Week 3)
**Goal:** Additional entity types

**Implementation:**
- `project_list()`, `project_create()`, `project_update()` tools
- `company_list()`, `company_create()` tools
- CODE validation (uppercase, underscores)
- Enum validation (type, status, relationship)

**Deliverable:** Full management of projects and companies

### Phase 4: Resources & Advanced Discovery (Week 4)
**Goal:** Expose resources and advanced querying

**Implementation:**
- MCP resources: `context://README`, `context://tasks/open`
- `context_validate()` tool (with auto-fix)
- `context_recent()` tool (recent activity)
- Generate tools: `task_generate()`, `workspace_init()`

**Deliverable:** Complete MVP with resources and scaffolding

### Phase 5: Advanced Features (Future)
- Journal and experiment management tools
- Inbox workflow tools
- Context graph visualization
- Full-text search across entities
- Session summary generation (auto-compact integration)
- Multi-workspace support

---

## Success Metrics

### For Claude Code
- **10x context discovery speed:** ~10 bash commands → 1 tool call
- **Zero command construction:** Direct tool calls with typed parameters
- **Structured responses:** JSON results, not text parsing
- **Atomic operations:** Multi-task operations in single call
- **Auto-discovery:** All tools visible on workspace open

### For Users
- **One-time setup:** Configure MCP server once, works everywhere
- **Consistent workspaces:** Same conventions across all projects
- **Safe operations:** Validation prevents broken state
- **Clear visibility:** context_summary() shows complete project state
- **No manual git:** Auto-commits handle version control

---

## Technical Implementation Notes

### Language & Tools
- Python 3.11+
- **mcp** (Model Context Protocol SDK)
- pydantic (schema validation + MCP tool schemas)
- PyYAML (frontmatter parsing)
- pathlib (file operations)
- subprocess (git operations)
- asyncio (MCP async handlers)

### Architecture Patterns
- Entity managers (TaskManager, ProjectManager, etc.)
- Schema validation (pydantic models for frontmatter)
- Atomic operations (transaction-like behavior)
- Auto-commit hooks (after successful operations)

### Testing Strategy
- Unit tests for entity managers
- Integration tests for CLI commands
- Validation tests for schema enforcement
- End-to-end tests with sample workspaces

---

## Open Questions

1. **Context graph:** How to visualize entity relationships?
2. **Search:** Full-text search implementation (ripgrep? sqlite fts?)
3. **Inbox processing:** Interactive vs automated?
4. **Session generation:** Integration with agent auto-compact?
5. **Multi-workspace:** Support for workspace collections?
6. **Sync:** Cloud sync for mobile capture?

---

## References

- **CONVENTIONS.md** - Core specification for entity types and patterns
- **Rails Guides** - Inspiration for convention over configuration
- **ActiveRecord** - Pattern for entity querying
- **Claude Code** - Target integration platform
