# Motoko Conventions & Specifications

**Version:** 1.0
**Date:** 2025-01-18

## Philosophy

- **Convention over Configuration** - No config files, use file path conventions
- **Markdown as Code** - Everything is markdown files (self-documenting)
- **Git as History** - Always commit, working directory stays clean
- **Semantic Filenames** - Filenames are context clues
- **No Vector Stores** - Load entire markdown files into context
- **Conversational First** - Agent responds with text before using tools

## Directory Structure

```
./
├── tasks/                          # Task management
│   ├── 000001-task-name.md
│   └── 000001-COMPLETED-task-name.md
│
├── roles/                          # Role definitions and context
│   ├── artist-manager/
│   │   ├── description.md         # Role system prompt
│   │   └── context/
│   │       ├── music-between-overview.md
│   │       └── instagram-ad-strategy.md
│   ├── educator/
│   │   ├── description.md
│   │   └── context/
│   │       └── curriculum-framework.md
│   └── project-manager/
│       ├── description.md
│       └── context/
│           └── proposal-template.md
│
├── context/                        # Project-wide context
│   ├── README.md                  # Main project context (auto-loaded)
│   └── sessions/                  # Session summaries
│       ├── 2025-01-18-music-between-post-creation.md
│       └── 2025-01-19-instagram-ad-setup.md
│
└── .git/                          # Git history as record
```

## Task Management

### File Naming Convention

```
{6-digit-number}-{kebab-case-name}.md
{6-digit-number}-COMPLETED-{kebab-case-name}.md
```

**Examples:**
- `000001-fix-gemini-streaming-bug.md` (open)
- `000002-COMPLETED-build-cli-interface.md` (completed)

**Rules:**
- Use 6-digit zero-filled numbers: `000001`, `000002` (not `01`, `02`)
- Task names in kebab-case
- Completed tasks: Insert `-COMPLETED-` after number
- Files are markdown, structure is flexible

### Task Lifecycle

1. **Create** - Agent uses `write_file` to create numbered task file
2. **Work** - Read task, discuss approach, implement
3. **Complete** - Use `bash` to rename: `mv 000001-task.md 000001-COMPLETED-task.md`
4. **Commit** - Always commit task changes

### Loading on Startup

- Show top 10 open task **titles**
- Load **content** of last 5 open tasks for context
- Agent is aware of task system via system prompt

## Role System

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
