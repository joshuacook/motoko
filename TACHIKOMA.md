# Tachikoma: Workspace Maintenance Agent

## Overview

Tachikoma is a **CLI maintenance tool** for the Context Lake. Built on the Claude Agent SDK, it analyzes workspace content and creates decision files for human review.

**Key Principles**:
- **Read-only observer**: Can only propose changes via decision files
- **Batch job, not chat**: Run command, outputs to `decisions/` only
- **Human approval required**: All changes require user action
- **Three cleanup modes**: Schema, frontmatter, structure (run in order)

## Scully vs Tachikoma

| | Scully | Tachikoma |
|---|--------|-----------|
| **Type** | Chat agent | Batch job |
| **Trigger** | User sends message | User runs CLI command |
| **Interaction** | Conversational | None |
| **Output** | Chat + file changes | Decision files only |
| **Access** | Full read/write | Read-only + decisions |
| **Infrastructure** | Claude Code CLI | Claude Agent SDK CLI |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     User runs Tachikoma                          │
│                                                                  │
│  uv run tachikoma {schema|frontmatter|structure} /path/to/ws     │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Tachikoma CLI                                │
│                                                                  │
│  - Built on Claude Agent SDK                                     │
│  - Reads workspace, analyzes content                             │
│  - Creates decision files in decisions/                          │
│  - Updates .claude/tachikoma-summary.yaml                        │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Workspace                                    │
│                                                                  │
│  .claude/schema.yaml           tasks/*.md                        │
│  .claude/tachikoma-summary     projects/*.md                     │
│  roles/*.md                    decisions/*.md  ◄── output        │
└─────────────────────────────────────────────────────────────────┘
```

## Workspace State

Tachikoma maintains a **summary** to enable incremental analysis:

```
{workspace}/.claude/
├── schema.yaml              # Entity type definitions
└── tachikoma-summary.yaml   # Tachikoma's workspace understanding
```

### Summary File

`.claude/tachikoma-summary.yaml`:

```yaml
last_scan: "2024-01-15T10:30:00Z"
entity_counts:
  tasks: 47
  notes: 23
  projects: 5
  journal: 89
observations:
  - "12 notes appear to be company profiles"
  - "15 tasks are missing status field"
  - "3 notes look like tasks based on content"
entities:
  task_001:
    updated_at: "2024-01-14T08:00:00Z"
    classification: task
    issues: []
  note_abc:
    updated_at: "2024-01-10T12:00:00Z"
    classification: company_profile
    issues: ["wrong_type"]
pending_decisions:
  - decision_xyz  # Already proposed, waiting for review
```

### Incremental Analysis

On subsequent runs, Tachikoma:

1. Reads existing summary
2. Compares file modification times with last_scan
3. Only reads changed entities from filesystem
4. Updates summary with new observations
5. Creates decisions only for new issues

This avoids re-reading hundreds of unchanged entities.

## Execution Flow

```
User runs: uv run tachikoma {mode} /path/to/workspace
    │
    ▼
CLI invokes Claude Agent SDK
    │
    ├── Reads .claude/schema.yaml
    ├── Reads .claude/tachikoma-summary.yaml (if exists)
    ├── Analyzes based on mode (schema/frontmatter/structure)
    ├── Creates decision files in decisions/
    └── Updates .claude/tachikoma-summary.yaml
    │
    ▼
CLI exits
    │
    ▼
User reviews decisions in decisions/
    │
    ▼
User approves/rejects (applies changes or deletes decision files)
```

## Cleanup Categories

Tachikoma proposes three types of cleanup (in dependency order):

### 1. Schema Updates

Changes to `.claude/schema.yaml`. Must be resolved first because other cleanup depends on knowing the correct schema.

**Examples:**
- Add new entity type: "Found 12 company profiles in notes → add `companies` type"
- Add field to existing type: "Tasks mention deadlines → add `due_date` field"
- Update field constraints: "Status should allow 'blocked' value"

**Decision type:** `schema_update`

### 2. Frontmatter Cleanup

Fix individual entities to match the schema. Per-entity.

**Examples:**
- Missing required field: "Task has no status → set to 'open'"
- Invalid value: "Status is 'DONE' → should be 'done'"
- Missing optional field: "Task mentions deadline → add due_date"

**Decision type:** `frontmatter_update`

### 3. Structure Cleanup

Files in wrong places or that shouldn't exist.

**Examples:**
- Wrong directory: "Note looks like a task → relocate to tasks/"
- Orphan files: "Random file outside schema → delete or relocate"
- Stale content: "No updates in 6 months → archive"
- Duplicates: "Two notes cover same topic → merge"

**Decision types:** `relocate`, `archive`, `delete`, `merge`

## Decision Files

Decisions are written to `decisions/`:

### schema_update
```yaml
---
title: "schema: add companies entity type"
status: pending
decision_type: schema_update
created_at: "2024-01-15T10:30:00Z"
---

## Suggested Changes

Add new entity type for company profiles.

```yaml
companies:
  directory: companies
  naming: "{slug}.md"
  frontmatter:
    required: [name]
```

## Reasoning

Found 12 notes that are company profiles. They have similar structure:
- Company name as title
- Industry, size, contact info in content
- Located in notes/ but don't fit note pattern
```

### frontmatter_update
```yaml
---
title: "fix: add status to build-landing-page task"
status: pending
decision_type: frontmatter_update
subject_path: tasks/build-landing-page.md
created_at: "2024-01-15T10:30:00Z"
---

## Current State

Task has no status field.

## Suggested Change

Add `status: open` to frontmatter.

## Reasoning

Task has no status but content indicates it's active (mentions "working on" and "need to").
```

### relocate
```yaml
---
title: "relocate: meeting-notes-jan-15 to journal"
status: pending
decision_type: relocate
subject_path: notes/meeting-notes-jan-15.md
suggested_path: journal/2024-01-15.md
confidence: 0.85
created_at: "2024-01-15T10:30:00Z"
---

## Current Location

`notes/meeting-notes-jan-15.md`

## Suggested Location

`journal/2024-01-15.md`

## Reasoning

This is clearly a dated entry (Jan 15 meeting notes). It has:
- Specific date in title
- Log/diary style content
- Timestamps throughout

Confidence: 85%
```

## System Prompt

The Tachikoma container uses this system prompt:

```
You are Tachikoma, a maintenance agent for the Scully Context Lake.

Your job is to analyze workspace content and create decision files for human review. You can READ everything but can only WRITE decisions and your summary file.

## Your Process

1. Read .claude/schema.yaml to understand entity types
2. Read .claude/tachikoma-summary.yaml (if exists) for previous observations
3. If summary exists:
   - Check file modification times against last_scan
   - Only read content for changed files
4. If no summary (first run):
   - Read all entities to build initial understanding
5. Analyze and identify issues:
   - Missing or incorrect frontmatter fields
   - Content that belongs in a different entity type
   - Patterns suggesting schema improvements
6. Create decision files in decisions/ for issues found
7. Update .claude/tachikoma-summary.yaml with:
   - New last_scan timestamp
   - Updated entity counts
   - Observations about the workspace
   - Per-entity classifications and issues
   - List of pending decisions created

## Cleanup Order

1. Schema updates first (other cleanup depends on correct schema)
2. Frontmatter cleanup (fix fields to match schema)
3. Structure cleanup (relocate, archive, delete)

## Guidelines

- Be conservative. Only propose changes you're confident about.
- Respect the workspace schema definitions.
- Consider context - a note about a "project" isn't necessarily a project entity.
- Focus on structural issues, not content quality.
- Group related changes when possible (e.g., all missing status fields).
- Provide clear reasoning for every decision.
- Don't re-propose issues that have pending decisions (check pending_decisions in summary).
- Update the summary even if you find no issues.

## File Access

You can read any file in the workspace.
You can only write to:
- .claude/tachikoma-summary.yaml
- decisions/*.md
```

## Usage

```bash
cd ~/working/motoko/tachikoma

# Run schema cleanup (do this first)
uv run tachikoma schema ~/working/motoko/workspaces/personal

# Run frontmatter cleanup (after schema is stable)
uv run tachikoma frontmatter ~/working/motoko/workspaces/personal

# Run structure cleanup (after frontmatter is fixed)
uv run tachikoma structure ~/working/motoko/workspaces/personal

# Check generated decisions
ls ~/working/motoko/workspaces/personal/decisions/

# Review a decision
cat ~/working/motoko/workspaces/personal/decisions/relocate-meeting-notes.md

# Approve: apply the change manually or with a script
# Reject: delete the decision file
```

## Future Considerations

1. **Scheduled runs**: Cron job to run Tachikoma periodically
2. **Multiple workspaces**: Batch run across all workspaces
3. **Decision application**: Script to apply approved decisions
4. **Dry run mode**: Show what would be proposed without creating files
5. **Web UI**: Review decisions in browser instead of filesystem
