# Context Lake Architecture

The Context Lake is Motoko's approach to personal knowledge management. Each workspace is a git repository with markdown entities, optional schema definitions, and async cleanup via Tachikoma.

## Core Principles

### 1. Filesystem as Source of Truth

All content lives as markdown files in a local git repository:

```
{workspace}/
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

Files are readable, portable markdown. No proprietary formats. Git provides version history.

### 2. Schema Defines Structure

Each workspace can define entity types in `.claude/schema.yaml`:

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
  journal:
    directory: journal
    naming: "{date}.md"
    frontmatter:
      required: [date]
```

**No schema?** Falls back to directory-based conventions. `tasks/*.md` = tasks.

### 3. Frontmatter as Metadata

Entity metadata lives in YAML frontmatter:

```yaml
---
title: Build landing page
status: open
priority: high
due: 2024-01-20
---

# Build landing page

Content here...
```

**Why frontmatter:**
- Extensible (add fields anytime)
- Standard format
- Readable without tooling
- Separate from content

### 4. Permissive Write, Resilient Read

**Write path accepts anything:**
- Create files however you want
- Use any naming scheme
- Include whatever frontmatter (or none)

**Read path handles messiness:**
```python
# Not this:
if status not in VALID_STATUSES:
    raise ValueError("Invalid status")

# This:
if status not in VALID_STATUSES:
    status = "open"  # sensible default
```

Tools never crash on malformed data. They infer, default, and continue.

### 5. Async Cleanup via Tachikoma

Tachikoma is a CLI tool (built on Claude Agent SDK) that proposes cleanup:

```
User runs: uv run tachikoma {mode} /path/to/workspace
    │
    ▼
Tachikoma reads .claude/schema.yaml and .claude/tachikoma-summary.yaml
    │
    ├── Schema mode: proposes schema improvements
    ├── Frontmatter mode: proposes field fixes
    └── Structure mode: proposes relocations/archives
    │
    ▼
Tachikoma updates .claude/tachikoma-summary.yaml
    │
    ▼
Decisions appear in decisions/
    │
    ▼
User reviews and approves/rejects
```

Tachikoma maintains a **summary file** (`.claude/tachikoma-summary.yaml`) that stores:
- Last scan timestamp
- Entity counts and classifications
- Observations about the workspace
- Pending decisions already proposed

This enables **incremental analysis** - Tachikoma only reads entities that changed since the last run.

Tachikoma is **read-only** (except for its summary file and decision files). All changes require human approval.

See [TACHIKOMA.md](TACHIKOMA.md) for details.

## One Workspace = One Repo

Each workspace is a self-contained git repository:

```
~/working/motoko/workspaces/
├── coyote/          # Music production workspace
├── escuela/         # Teaching/education workspace
├── personal/        # Personal tasks and notes
└── project-management/  # Project management workspace
```

**Benefits:**
- Git for version history and persistence
- GitHub for backup and sync
- Claude Code works directly on filesystem
- Standard tools (grep, find, etc.) just work
- Optional Motoko MCP server for structured entity operations

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     User's Laptop                                │
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  Claude Code    │    │   Tachikoma     │                     │
│  │  (Motoko)       │    │   (CLI)         │                     │
│  │                 │    │                 │                     │
│  │  - Chat agent   │    │  - Batch job    │                     │
│  │  - Read/write   │    │  - Read-only    │                     │
│  │  - Interactive  │    │  - Creates      │                     │
│  └────────┬────────┘    │    decisions    │                     │
│           │             └────────┬────────┘                     │
│           │                      │                              │
│     ┌─────┴─────┐                │                              │
│     │           │                │                              │
│     ▼           ▼                ▼                              │
│  ┌──────┐  ┌──────────┐                                         │
│  │ Raw  │  │ Batou    │  (MCP Server - optional)                │
│  │ File │  │ Entity   │                                         │
│  │ Ops  │  │ Tools    │                                         │
│  └──┬───┘  └───┬──────┘                                         │
│     │          │                                                │
│     └────┬─────┘                                                │
│          ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Workspace (Git Repo)                  │   │
│  │                                                          │   │
│  │  .claude/schema.yaml         tasks/*.md                  │   │
│  │  .claude/tachikoma-summary   projects/*.md               │   │
│  │  roles/*.md                  decisions/*.md              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                             │                                   │
│                             ▼                                   │
│                      Git → GitHub                               │
│                      (backup/sync)                              │
└─────────────────────────────────────────────────────────────────┘
```

**Two access modes:**
- **Raw File Ops**: Claude Code's built-in Read, Write, Glob, Grep. Full flexibility.
- **Batou Entity Tools**: Schema-aware operations via MCP. `list_entities`, `create_entity`, etc.

## Agents

### Motoko (Claude Code)

Interactive chat agent for working with the workspace.

- **Trigger:** User sends message in Claude Code
- **Mode:** Conversational
- **Access:** Full read/write via filesystem
- **Tools:** Built-in Claude Code tools + optional Batou MCP tools

**Without Batou:** Claude uses Read, Write, Glob, Grep directly. CLAUDE.md teaches it workspace conventions.

**With Batou:** Claude also has `list_entities`, `create_entity`, `update_entity`, etc. Schema-aware operations that enforce frontmatter, apply defaults, and use correct paths.

See [batou/README.md](batou/README.md) for setup and tool documentation.

### Tachikoma

CLI tool for maintenance proposals. Built on Claude Agent SDK.

- **Trigger:** User runs `uv run tachikoma {mode} /path/to/workspace`
- **Mode:** Headless batch
- **Access:** Read-only + create decisions
- **Output:** Decision files in `decisions/`

## Entity Types

### Tasks

Action items with status tracking.

```yaml
---
title: Build landing page
status: open
priority: high
due: 2024-01-20
project: webapp
---
```

**Status values:** `open`, `in_progress`, `done`, `blocked`, `cancelled`

### Projects

Named initiatives that group related work.

```yaml
---
title: Web Application Redesign
status: active
---
```

### Journal

Date-based entries for logs, standups, reflections.

```yaml
---
date: 2024-01-15
type: standup
---
```

### Notes

Freeform documents. Minimal structure.

```yaml
---
title: Random thoughts
tags: [ideas, brainstorm]
---
```

### Decisions

Tachikoma cleanup proposals. Special entity type.

```yaml
---
title: "relocate: My Task"
status: pending
decision_type: relocate
subject_entity_id: note_abc123
suggested_type: tasks
confidence: 0.85
---
```

**Status values:** `pending`, `approved`, `rejected`

## Resilience Patterns

### Unknown Fields
```yaml
---
status: open
my_custom_field: whatever  # ignored, not rejected
---
```

### Invalid Enums
```python
status = frontmatter.get("status", "open")
if status not in VALID_STATUSES:
    status = "open"  # default, don't crash
```

### Missing Frontmatter
```python
if not has_frontmatter(content):
    frontmatter = {"title": infer_title_from_content(content)}
```

### Broken YAML
```python
try:
    fm = yaml.safe_load(frontmatter_text)
except yaml.YAMLError:
    fm = {}  # empty, Tachikoma will propose fix
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | Local filesystem + git | Simple, portable, standard tools work |
| Format | Markdown + YAML frontmatter | Portable, readable, standard |
| Schema | Optional `.claude/schema.yaml` | Structure when you want it |
| Validation | On read, lenient | Don't block users |
| Entity tools | Optional Motoko MCP | Structure when you want it, flexibility when you don't |
| Cleanup | Async (Tachikoma) + human approval | Safety over automation |
| Cleanup trigger | Human (run container) | No surprise changes |

---

*The Context Lake: your content, your structure, your approval.*
