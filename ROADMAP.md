# Motoko Roadmap

## Current State

The Context Lake system is functional for local use:
- 7 workspaces (project-management, personal, escuela, coyote, stormwreck-isle, ai-assisted-coding, madelon)
- Tachikoma maintenance agent with 3 cleanup modes
- Batou MCP server for structured entity operations
- Skills for Tachikoma cleanup (schema, frontmatter, structure)

All components named after Ghost in the Shell - Section 9 team:
- **Motoko** - System identity (Major Kusanagi)
- **Batou** - MCP server (field operative)
- **Tachikoma** - Maintenance agent (AI assistants)

## Near-term

### Naming Consistency
- [x] Resolve mixed sci-fi universes - chose Ghost in the Shell
- [x] Rename Scully → Motoko (system)
- [x] Rename MCP server → Batou (field operative)

### Documentation Polish
- [x] Fix `lake/` references in all docs
- [x] Create MOTOKO.md overview
- [x] Create BATOU.md reference
- [x] Fix MCP config location (`.mcp.json` at project root, not `.claude/mcp_settings.json`)
- [ ] Review and update CONTEXT_LAKE.md examples
- [ ] Add troubleshooting section

### Global Skills
- [ ] Move Tachikoma skills to motoko-level `.claude/skills/`
- [ ] Skills inherit to all workspaces
- [ ] Workspace-specific skills can override globals
- [ ] Document skill inheritance pattern

## Mid-term

### Remote Deployment
- [ ] Host workspaces beyond local laptop
- [ ] Options to evaluate:
  - Git remote + local clone (current)
  - Cloud storage mount (Google Drive, Dropbox)
  - Self-hosted (VPS with git server)
  - GitHub as source of truth
- [ ] Remote Tachikoma runs (GitHub Actions, scheduled job)

### MCP Data Sources
- [ ] Connect external data via MCP servers
- [ ] Potential integrations:
  - Databricks data lake
  - Google Calendar
  - Linear/GitHub issues
  - Notion
- [ ] Pattern: MCP server per data source, Claude orchestrates

### Decision Automation
- [ ] Script to apply approved decisions
- [ ] Archive applied decisions automatically
- [ ] Batch approval workflow

### Ingest
- [ ] Pipeline for getting knowledge into the lake
- [ ] Source types to support:
  - Web pages / articles (URL → entity)
  - PDFs / documents
  - Emails / conversations
  - Voice memos / transcripts
  - Screenshots / images with OCR
- [ ] Ingest agent (another Section 9 member?)
- [ ] Configurable extraction: what frontmatter to pull, where to route
- [ ] Deduplication / linking to existing entities
- [ ] Batch ingest from folders

## Long-term

### Multi-user
- [ ] Shared workspaces with multiple users
- [ ] Conflict resolution for concurrent edits
- [ ] Permission model (who can approve decisions)

### Web Interface
- [ ] View and search entities in browser
- [ ] Review Tachikoma decisions via web UI
- [ ] Mobile-friendly access

### Workspace Templates
- [ ] Starter schemas for common use cases
- [ ] `motoko init --template=project-management`
- [ ] Community templates

### Analytics
- [ ] Task completion trends
- [ ] Workspace health metrics
- [ ] Tachikoma effectiveness tracking

## Ideas (Unscheduled)

- **Cross-workspace linking** - Reference entities across workspaces
- **Entity versioning** - Track changes to individual entities beyond git
- **AI summaries** - Auto-generated workspace summaries
- **Natural language queries** - "What did I work on last week?"
- **Offline-first sync** - Work offline, sync when connected
- **Plugin system** - Custom entity types with behaviors

## Non-goals

- **Proprietary formats** - Markdown + YAML frontmatter only
- **Heavy infrastructure** - No required databases or servers
- **Forced structure** - Schema remains optional
- **Lock-in** - Export is just `cp -r`

---

*Last updated: 2025-12-11*
