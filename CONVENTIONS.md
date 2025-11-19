# Motoko Conventions & Specifications

**Version:** 2.0
**Date:** 2025-01-18

## Philosophy

- **Convention over Configuration** - No config files, use file path conventions
- **Data Lake Model** - Directories are tables, frontmatter is schema, markdown is context
- **Universal Structure** - Same entity types across all repositories
- **Markdown as Code** - Everything is markdown files (self-documenting)
- **Git as History** - Always commit, working directory stays clean
- **Semantic Filenames** - Filenames are context clues
- **No Vector Stores** - Load entire markdown files into context
- **Conversational First** - Agent responds with text before using tools
- **Role + Context Separation** - Role = behavioral mode, Context = current focus

## Architecture: Three Orthogonal Dimensions

### 1. Entity Type (Table) - WHAT the data is
Universal schema defined by directory. Same across all repositories.

### 2. Role (Behavior) - HOW to interact
Behavioral mode: communication style, validation strictness, emphasis.

### 3. Context (Focus) - WHERE you're working
Current focus: which projects/areas are active right now.

## Universal Directory Structure (Entity Types)

Every motoko workspace uses these "tables":

```
./
├── tasks/              # Work items, todos, tickets
├── projects/           # Project definitions and context
├── companies/          # Companies, clients, organizations
├── journal/            # Narrative documentation, logs
├── sessions/           # Auto-generated session summaries
├── experiments/        # Explorations, tests, trials
├── inbox/              # Unprocessed items, quick captures
├── roles/              # Role definitions (behavioral modes)
├── img/                # Visual assets (special case)
└── .git/               # Git history as record
```

**Key Principle:**
- Directory name = Entity type (table name)
- Each file = Entity (table row)
- Frontmatter = Structured data (schema/columns)
- Markdown body = Unstructured context (narrative)

## Entity Pattern (Universal)

Every entity follows this pattern:

```yaml
---
# STRUCTURED DATA (schema defined by entity type)
# Required and optional fields based on entity type
field1: value
field2: value
---
# UNSTRUCTURED CONTEXT (markdown)
# Can be bullet points or rich narrative
# Style determined by role, not structure
```

## Entity Type Schemas (Universal)

### tasks/

**Purpose:** Work items, todos, tickets (renamed from "tickets" for consistency)

**Schema:**
```yaml
---
number: string          # Auto-assigned, zero-filled (000001, 000002)
title: string           # Required
status: enum            # Required: To Do, In Progress, Blocked, Done
priority: enum          # Optional: Low, Medium, High, Urgent
project: string         # Optional: Reference to projects/{code}.md
company: string         # Optional: Reference to companies/{code}.md
created: date           # Auto-set
updated: date           # Auto-update
tags: list[string]      # Optional
blocker: string         # Optional: Description of what's blocking
due_date: date          # Optional
---
# Task description, context, decisions, next steps
```

**File Naming:**
```
{number:06d}-{project}-{kebab-case-slug}.md
{number:06d}-COMPLETED-{project}-{kebab-case-slug}.md
```

**Examples:**
- `000001-MERCHANTS-databricks-provisioning.md`
- `000002-COMPLETED-MUSIC_BETWEEN-instagram-ad-setup.md`

**Lifecycle:**
1. **Create** - Auto-assign next number, create file
2. **Work** - Update status, add context
3. **Complete** - Rename file to add `-COMPLETED-`
4. **Commit** - Always commit changes

### projects/

**Purpose:** Project definitions, goals, and context

**Schema:**
```yaml
---
code: string            # Required: SHORT_IDENTIFIER (all caps, underscores)
name: string            # Required: Full project name
type: enum              # Required: startup, consulting, creative, academic, employment
status: enum            # Required: Active, Paused, Archived
company: string         # Optional: Reference to companies/{code}.md
start_date: date        # Optional
end_date: date          # Optional
tags: list[string]      # Optional
---
# Project background, goals, current state, key context
```

**File Naming:**
```
{code}.md
```

**Examples:**
- `MERCHANTS.md`
- `MUSIC_BETWEEN.md`
- `GEORGIA_TECH.md`

### companies/

**Purpose:** Companies, clients, organizations, institutions

**Schema:**
```yaml
---
code: string            # Required: SHORT_IDENTIFIER
name: string            # Required: Full company name
relationship: enum      # Required: founder, client, employer, institution
industry: string        # Optional
website: string         # Optional
contact: string         # Optional
---
# Company background, relationship context, key people
```

**File Naming:**
```
{code}.md
```

**Examples:**
- `CHELLE.md` (relationship: founder)
- `MERCHANTS.md` (relationship: client)
- `CALTECH.md` (relationship: institution)

### journal/

**Purpose:** Narrative documentation, daily logs, creative reflection

**Schema:**
```yaml
---
date: date              # Required: YYYY-MM-DD
title: string           # Optional: Entry title
tags: list[string]      # Optional
project: string         # Optional: Reference to projects/
---
# Free-form narrative entry
# Can be technical notes, creative reflection, daily log
# Style determined by role
```

**File Naming:**
```
YYYY-MM-DD-{kebab-case-slug}.md
```

**Examples:**
- `2025-01-18-day-one-studio-session.md`
- `2025-01-19-merchants-infrastructure-review.md`

### sessions/

**Purpose:** Auto-generated session summaries (created during auto-compact)

**Schema:**
```yaml
---
date: date              # Required: YYYY-MM-DD
topic: string           # Required: Auto-generated topic slug
projects: list[string]  # Optional: Projects discussed
duration: string        # Optional: Session length
participants: list[string]  # Optional: For multi-user sessions
---
# Auto-generated session summary
# Includes: summary, key decisions, context added, next steps
```

**File Naming:**
```
YYYY-MM-DD-{topic-slug}.md
```

**Examples:**
- `2025-01-18-music-between-post-creation.md`
- `2025-01-19-merchants-databricks-troubleshooting.md`

**Generation:**
- Triggered during auto-compact (when context window fills)
- Agent summarizes conversation
- Extracts topic from discussion
- Commits to git automatically

### experiments/

**Purpose:** Explorations, tests, trials, creative experiments

**Schema:**
```yaml
---
name: string            # Required
date: date              # Required: When started
status: enum            # Required: exploring, validated, abandoned
project: string         # Optional: Reference to projects/
tags: list[string]      # Optional
---
# Experiment notes, process, results, learnings
```

**File Naming:**
```
{number:03d}-{kebab-case-name}.md
```

**Examples:**
- `001-magazine-collage-technique.md`
- `002-tx6-recording-chain.md`

### inbox/

**Purpose:** Unprocessed items, quick captures, temporary storage

**Schema:**
```yaml
---
date: date              # Required: When captured
processed: boolean      # Required: false initially
source: string          # Optional: Where it came from
---
# Quick capture content
# To be processed and moved to appropriate entity type
```

**File Naming:**
```
YYYY-MM-DD-HHMM-{short-slug}.md
```

**Examples:**
- `2025-01-18-1430-meeting-notes.md`
- `2025-01-19-0900-idea-for-ad-copy.md`

**Workflow:**
1. Quick capture to inbox/
2. Process: move to tasks/, journal/, experiments/
3. Mark as processed or delete file

### img/

**Purpose:** Visual assets with optional metadata/analysis

**Special Case:** Binary assets + optional markdown metadata

**Structure:**
- Binary files (.png, .jpg, .webp, .pdf) - The actual images
- Optional .md files - Metadata and analysis (follows entity pattern)

**Metadata Schema (Optional):**
```yaml
---
image: string           # Required: Reference to binary file
analyzed: string        # Optional: Who/what analyzed it
date: date              # Optional: When created/captured
tags: list[string]      # Optional
project: string         # Optional: Reference to projects/
---
# Analysis, description, context
# Can include interpretation, elements, choices, actions
```

**File Naming:**
```
{asset-name}.{ext}          # Binary asset
{asset-name}.md             # Optional metadata (same name as asset)
```

**Examples:**
```
img/
├── ceuta_000012.png                    # Binary image
├── ceuta_000012.md                     # Metadata + analysis
├── arabic-singing-diaspora.jpg         # Binary image (no metadata)
└── DALL·E-2023-logo-concept.webp      # Binary image (no metadata)
```

**Usage:**
- Not all images need .md files
- .md files provide context when needed
- Reference from other entities: `![desc](../img/file.png)`

**Metadata Example:**
```markdown
# ceuta_000012

**Image:** ceuta_000012.png
**Analyzed:** coyote

---

# Analysis

This album cover embodies...

# Elements

## Choices
1. Rejecting naturalistic color schemes...
```

**Key Difference from Other Entities:**
- Binary assets don't follow frontmatter pattern (they're not markdown)
- Metadata is optional (not all images need it)
- .md file describes the asset, doesn't replace it

## Role System (Behavioral Definitions)

### Structure

Each role is a directory with:
- `description.md` - Role definition (system prompt)
- `context/` - Project-specific context files

**Example: `./roles/artist-manager/`**
```
artist-manager/
├── description.md                 # "You are an artist management assistant..."
└── context/
    ├── music-between-overview.md  # What Music Between is
    ├── instagram-ad-strategy.md   # How we monitor ads
    └── booking-workflow.md        # Booking process
```

### Role Definition Format

**`description.md`** contains:
- System prompt for the role
- Role-specific instructions
- Communication style
- Workflows and processes

### Context Files

**Naming:** Use semantic, descriptive filenames
- ✅ `music-between-overview.md` - Clear what it contains
- ✅ `instagram-ad-strategy.md` - Topic is obvious
- ❌ `context-1.md` - Not descriptive
- ❌ `notes.md` - Too generic

**Content:** Project-specific knowledge
- Overviews and background
- Strategies and approaches
- Templates and examples
- Workflows and processes

### Role Loading

**Auto-detection:**
1. Check `./roles/` directory for available roles
2. Match role to workspace name, task content, or existing role files
3. Proactively suggest: "I see this is artist work. Should I use the artist-manager role?"

**Loading strategy:**
1. Load `description.md` (always)
2. Load all `context/*.md` files (full content)
3. Add to system prompt context

**Role switching:**
- User can switch roles mid-session: `/role educator`
- Agent can suggest role switches based on task content

## Context Management

### Project Context

**`./context/README.md`** - Main project context
- Auto-loaded on session start
- Contains project overview, goals, key information
- Agent can suggest updates during conversation

**Loading:** Read entire file into context

### Session Summaries

**Location:** `./context/sessions/`

**Naming Convention:**
```
YYYY-MM-DD-topic-slug.md
```

**Examples:**
- `2025-01-18-music-between-post-creation.md`
- `2025-01-19-instagram-ad-monitoring-setup.md`
- `2025-01-20-persona-development-discussion.md`

**Generation:**
- Triggered during **auto-compact** (when context gets too large)
- Agent generates summary of conversation
- Topic slug extracted from conversation focus
- Summary committed to git

**Content structure:**
```markdown
# Session: Music Between Post Creation

**Date:** 2025-01-18
**Topics:** Music Between, content creation, task management

## Summary

[Agent-generated summary of the session]

## Key Decisions

- Created task for first Music Between post
- Decided to focus on Instagram format first

## Context Added

- Explained Music Between concept
- Discussed post workflow
```

**Loading strategy:**
- Show last 5 session filenames on startup
- Auto-load sessions from last 7 days
- Load sessions matching current task topics (filename matching)

### Context Window Management

**Auto-Compact triggers:**
- When conversation history exceeds token threshold
- Generate session summary
- Save to `./context/sessions/YYYY-MM-DD-topic.md`
- Trim conversation history
- Keep summary in context
- Commit summary

**No vector stores:**
- Load entire markdown files
- Rely on LLM context window
- Use semantic filenames for discovery
- Keep files focused and concise

## Git Workflow

### Always Commit

**Agent behavior:**
- After any `write_file` operation → commit
- After completing task → commit
- After creating session summary → commit
- Keep working directory clean

**Commit messages:**
- Descriptive and specific
- Include what changed and why
- Example: "Create task 000004 for Music Between post"
- Example: "Complete task 000001: Fix Gemini streaming bug"

**Commands:**
```bash
git add {file}
git commit -m "descriptive message"
```

**Never:**
- Leave uncommitted changes
- Use vague commit messages
- Skip committing after file operations

**Git as historical record:**
- Clean working directory always
- Git log shows project evolution
- Commits document decisions and progress

## Agent Behaviors

### Conversational First

**IMPORTANT:** Always respond with text before using tools

**Pattern:**
1. Acknowledge request
2. Ask clarifying questions if needed
3. Discuss approach
4. Use tools
5. Explain what was done

**Example:**
```
User: "Create a task for X"
Agent: "Sure! Let me ask a few questions:
        - What's the scope of this task?
        - Any specific requirements?
        I'll create task 000004-x.md once I understand better."
[After discussion]
Agent: "Perfect! Creating the task now..."
[Uses write_file]
Agent: "Done! I've created task 000004-x.md and committed it."
```

### Proactive Suggestions

**Context updates:**
- "Should I update ./context/README.md with this info about Music Between?"
- "Would you like me to add this to the artist-manager role context?"

**Task management:**
- "This sounds like trackable work. Should I create a task?"
- "We've completed the work for task 3. Should I mark it as complete?"

**Role switching:**
- "I see you're working on curriculum now. Should I switch to the educator role?"

**Git commits:**
- Always commit automatically after file changes
- Use descriptive commit messages

### Role Awareness

**Auto-detect and enable:**
- Check workspace for role directories
- Match task content to roles
- Proactively suggest role switches
- Load role context automatically

**Role-specific behavior:**
- Follow role definition instructions
- Use role context for informed responses
- Maintain role consistency throughout session

## Startup Behavior

**When session starts:**

1. **Load project context**
   - Read `./context/README.md` (full content)

2. **Load tasks**
   - Show top 10 open task titles
   - Load content of last 5 open tasks

3. **Detect and load role**
   - Check `./roles/` directory
   - Auto-detect based on workspace/tasks
   - Load `description.md` + all `context/*.md` files
   - Proactively enable role

4. **Load recent sessions** (optional)
   - Show last 5 session summaries (by filename)
   - Auto-load sessions from last 7 days if relevant

5. **Display to user**
   - Show active role (if any)
   - Show open tasks summary
   - Ready for interaction

## File Naming Principles

**All filenames are semantic context clues:**

✅ **Good:**
- `music-between-overview.md` - Clear topic
- `2025-01-18-music-between-post-creation.md` - Date + topic
- `000001-fix-gemini-streaming-bug.md` - Number + descriptive name
- `instagram-ad-strategy.md` - Specific and clear

❌ **Bad:**
- `context-1.md` - Not descriptive
- `notes.md` - Too generic
- `file.md` - No meaning
- `2025-01-18.md` - No topic

**Rules:**
- Use kebab-case for all filenames
- Be specific and descriptive
- Include dates when temporal context matters
- Make filenames grep-able and discoverable

## Design Principles

1. **Convention over Configuration** - File paths, not config files
2. **Markdown as Infrastructure** - Everything is readable, editable files
3. **Git as Source of Truth** - History is in commits
4. **Semantic Filenames** - Filenames convey meaning
5. **Context Window, Not Vector Store** - Load full files, no embeddings
6. **Collaborative, Not Autonomous** - Work with user, not for user
7. **Conversational First** - Talk before acting
8. **Proactive Suggestions** - Suggest, don't assume

## Implementation Status

- ✅ Task management system
- ✅ Basic CLI with conversational interface
- ✅ Model abstraction (Gemini, Claude)
- ✅ Tool system (read, write, glob, grep, bash)
- 🚧 Role system (to be implemented)
- 🚧 Context loading (partial)
- 🚧 Git auto-commit (to be implemented)
- 🚧 Auto-compact & session summaries (to be implemented)

## Future Considerations

- Session summary generation logic
- Auto-compact triggers and thresholds
- Role switching UX
- Context relevance scoring (simple filename matching)
- Multi-workspace support
