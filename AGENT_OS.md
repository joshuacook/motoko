# Tachi

Agent-native apps.

## Overview

Tachi is the substrate on which AI agents run. It's not a deployment platform—it's the environment agents live in. Users don't deploy apps to Tachi; they configure agents that run inside it.

The interface IS the agent. Configuration happens through conversation. The underlying architecture is invisible to end users.

## Architecture

### Core Components

| Component | OS Analogy | Purpose |
|-----------|------------|---------|
| **Major** | Kernel | Agent runtime (Claude Agent SDK) |
| **Batou** | Filesystem + Database | Context Lake operations via MCP |
| **Ishikawa** | Syscalls | External data lake access via MCP |
| **Tachikoma** | Daemon | Background workspace maintenance |

### The Context Lake

The Context Lake is both a filesystem AND a database. This is the key insight.

**As filesystem:**
- Markdown files in git
- grep, vim, any tool works
- Version controlled
- Human readable

**As database (via Batou):**
- Structured queries
- CRUD operations
- Schema validation
- Filtered lists

```
workspace/
├── PROMPT.md                    # Role definition
├── .claude/
│   ├── schema.yaml              # Ontology (explicit)
│   └── skills/                  # Available capabilities
├── tasks/                       # Entities (emergent ontology)
├── campaigns/
└── reports/
```

Schema on read, not write. Structure emerges through use. Tachikoma normalizes asynchronously—users are never blocked.

### MCP Layer

Two types of MCP servers:

**Batou** - Internal knowledge
- Context Lake operations
- Workspace-scoped
- Always available

**Ishikawa** - External data
- Medallion data lakes (Silver/Gold)
- Read-only
- ~10 supported connectors (Marketo, Salesforce, Databricks, etc.)
- Added by platform team as needed

### Skills

Skills are capabilities the agent can invoke. Python scripts in `.claude/skills/`.

The user thinks about skills ("I want to analyze deliverability").
The Major arbitrates when to use them.
The Major also helps configure what's possible.

```
User: "I need to be able to check our email deliverability"

Major: "I'll add that capability. I'm installing the
       marketo-deliverability skill. You'll need your
       Databricks connection configured—want me to
       connect you with a solution architect?"
```

## Roles

### Architect

Us. Builds and maintains Tachi itself.

Responsibilities:
- Core components (Major, Batou, Ishikawa, Tachikoma)
- Platform infrastructure
- Ishikawa connectors
- Skill standards

### Developer

Builds apps on Tachi using the DSL.

Responsibilities:
- Define role/prompt
- Define ontology/schema
- Select skills
- Configure data sources
- Choose interface layer(s)

### User

Uses the app. Doesn't know about Tachi.

Experience:
- An app that helps them do their job
- May or may not know AI is involved
- Never sees YAML, markdown, or architecture

## Interface Layers

Three ways to interact with the same substrate:

```
┌─────────────────────────────────────┬─────────────────────────────────────┬─────────────────────────────────────┐
│            CHAT MODE                │            LAKE MODE                │            CRUD MODE                │
├─────────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────────┤
│                                     │                                     │                                     │
│  You: How's deliverability?         │  ▼ tasks (12)    │ # Investigate   │  Tasks    Campaigns    Reports     │
│                                     │    ○ 000047-inv  │   Bounce Rates  │                                     │
│  Major: Running analysis...         │    ○ 000046-q1   │                 │  ┌─────────────────────────────────┐│
│                                     │    ○ 000045-upd  │ ---             │  │ Title          Status   Pri    ││
│  ┌─ deliverability ───────────┐     │                  │ status: open    │  ├─────────────────────────────────┤│
│  │ Bounce Rate: 3.2% ✓        │     │  ▶ campaigns (8) │ priority: high  │  │ Investigate..  ● Open   High   ││
│  │ Domains at Risk: 2 ⚠       │     │                  │ ---             │  │ Q1 review      ● Open   Med    ││
│  └────────────────────────────┘     │  ▶ reports (3)   │                 │  │ Update nurture ○ Done   Low    ││
│                                     │                  │ ## Description  │  │ Fix unsub flow ● Open   High   ││
│  Two domains have elevated          │  ▶ journal (24)  │                 │  └─────────────────────────────────┘│
│  bounce rates. Want me to           │                  │ Two domains     │                                     │
│  dig in?                            │                  │ showing issues: │  💡 3 tasks could be closed [View] │
│                                     │  ────────────────│ - acme.com      │                                     │
│  You: Yes, create a task            │  [+ New]         │ - bigcorp.net   │              1 of 3   [<] [>]      │
│                                     │                  │                 │                                     │
│  Major: Created task #000047        │                  │ [Edit] [Delete] │                       [+ New Task] │
│                                     │                  │                 │                                     │
│  ┌────────────────────────────┐     ├──────────────────┴─────────────────┤                                     │
│  │ Type a message...          │     │ Ask about this file...             │                                     │
│  └────────────────────────────┘     └─────────────────────────────────────┘                                     │
│                                     │                                     │                                     │
├─────────────────────────────────────┼─────────────────────────────────────┼─────────────────────────────────────┤
│  Conversation with agent            │  Browse + edit files directly       │  Tables and forms                   │
│  Agent CRUDs for you                │  Chat assists while you work        │  Agent invisible (magic behind)     │
└─────────────────────────────────────┴─────────────────────────────────────┴─────────────────────────────────────┘
```

Same data. Same Context Lake. Three windows into it.

### 1. Chat Mode

Conversation with the agent. Agent CRUDs for you.

For: Natural interaction, complex queries, multi-step workflows.

### 2. Lake Mode

Browse and edit files directly. Chat assists while you work.

For: Users who want to see the structure, direct editing.

### 3. CRUD Mode

Tables and forms. Looks like Airtable or Salesforce.

The agent is invisible. When you click "Analyze," skills run. When you add a record, a markdown file is created. When data looks wrong, Tachikoma already fixed it.

For: Users who want a familiar interface.

### Interfaces by Role

```
Architect    ───►  CLI + Code + Console
                   (builds platform)

Developer    ───►  Browser Editor + Preview
                   (configures apps)

User         ───►  Chat │ Lake │ CRUD
                   (uses app, developer chooses which)
```

Developer's browser editor:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Tachi                                      demand-strike    ○ Dev │
├─────────────────────────────────────────────────────────────────────┤
│  [Config]   Skills   Data   Preview                      [Publish] │
├───────────────────┬─────────────────────────────────────────────────┤
│                   │                                                 │
│  Files            │  ┌─ PROMPT.md ────────────────────────────────┐ │
│                   │  │                                            │ │
│  ● PROMPT.md      │  │  # Demand Strike                           │ │
│  ○ schema.yaml    │  │                                            │ │
│  ○ motoko.yaml    │  │  You are a marketing operations analyst    │ │
│                   │  │  specializing in email deliverability...   │ │
│                   │  │                                            │ │
│                   │  └────────────────────────────────────────────┘ │
│                   │                                                 │
│                   │  Auto-saved ✓                                   │
└───────────────────┴─────────────────────────────────────────────────┘
```

Edit. Save. Live. No deploy commands.

## Deployment

Edit in browser. Or git push. Either way, it's live.

**Browser path:**
```
┌─────────────────────────────────────────┐
│  demand-strike / Settings               │
├─────────────────────────────────────────┤
│  Role         [Edit PROMPT.md]          │
│  Ontology     [Edit schema.yaml]        │
│  Skills       [Configure...]            │
│  Data         [Connect...]              │
│  Domain       demand.joshuacook.work    │
└─────────────────────────────────────────┘
```

Edit. Save. Live.

**Git path:**
```
git commit -m "Updated role prompt"
git push
```

Same result. Platform watches either way.

No deploy commands. No infrastructure management. No CI/CD configuration.

### Runtime Model

**Cloud Run + Long-Running FastAPI**

```
Cloud Run instance (FastAPI)
    │
    ├── Clones workspace repo on first request
    │
    ├── Handles multiple requests
    │
    ├── Commits changes back to repo
    │
    └── Cloud Run manages lifecycle (reaping is a scale problem)
```

Long-running servers, not spin-up-per-request. Cloud Run handles scaling and instance management.

**Platform-managed Git**

Each user has 1-N workspaces. Each workspace is backed by a git repo.

Users never see git. They see "workspaces." The platform:
- Creates repos automatically
- Commits on every change
- Handles sync, versioning, backup
- Exposes workspace through UI/API

```
User perspective:          Platform perspective:

┌─────────────┐            ┌─────────────────────────┐
│ Workspaces  │            │ Git repos               │
│  - personal │     ═══>   │  - user_123/personal    │
│  - work     │            │  - user_123/work        │
│  - acme     │            │  - user_123/acme        │
└─────────────┘            └─────────────────────────┘
```

**Component Runtime:**

| Component | Runtime |
|-----------|---------|
| **Major** | Cloud Run (FastAPI, long-running) |
| **Batou** | Bundled with Major container |
| **Ishikawa** | Cloud Run (FastAPI per connector, shared across users) |
| **Tachikoma** | Cloud Run Jobs (scheduled, works on branches) |
| **Web App** | Vercel (static + API routes) |
| **CRUD App** | Vercel (generated from schema) |
| **Auth** | Clerk (shared) |
| **Git repos** | Cloud Source Repositories (native GCP) |

**Concurrency:**
- Optimistic concurrency for concurrent edits (user in CRUD while Major runs)

**Tachikoma Branches:**

Tachikoma proposes, never executes. Uses git branches:

```
main (user's workspace)
    │
    └── tachikoma/cleanup-2024-01-06
            │
            ├── Normalized 3 task filenames
            ├── Fixed broken YAML in 2 files
            └── Added missing frontmatter to 5 entities
```

Major knows about pending Tachikoma branches:

```
User: "Anything need my attention?"

Major: "Tachikoma has some cleanup suggestions:
       - 3 task filenames normalized
       - 2 YAML fixes
       - 5 files got frontmatter

       Want me to apply these changes?"

User: "Yes"

Major: [merges branch]
```

User never sees git. Just "apply" or "ignore."

**What this gives us:**
- No VM management
- Automatic scaling (Cloud Run handles load)
- Native GCP integration (CSR, IAM, logging)
- Persistence via git (every change is a commit)
- Versioning for free

## The DSL

Developers define apps with a declarative specification:

```yaml
# motoko.yaml

app:
  name: demand-strike

role: ./PROMPT.md

ontology:
  schema: ./.claude/schema.yaml

skills:
  - marketo-deliverability
  - marketo-engagement
  - marketo-email-decay
  - marketo-inactive-sunset

data:
  - ishikawa-marketo:
      provider: databricks
      profile: gptw

interfaces:
  web: true        # Chat + Lake
  crud: true       # Traditional app view
  cli: false       # No CLI for this app

auth:
  provider: clerk

domain: demand.joshuacook.work
```

### What the DSL Defines

| Section | What Developer Specifies |
|---------|-------------------------|
| `role` | Agent persona and purpose |
| `ontology` | Entity types and their fields |
| `skills` | Available capabilities |
| `data` | External data connections |
| `interfaces` | Which layers to expose |
| `auth` | Authentication provider |
| `domain` | Where it lives |

### What Tachi Provides

| DSL Section | Platform Provides |
|-------------|-------------------|
| `role` | Major runtime, prompt loading |
| `ontology` | Batou MCP, schema validation |
| `skills` | Execution environment, skill loading |
| `data` | Ishikawa connectors, credential management |
| `interfaces.web` | Next.js app, auth integration |
| `interfaces.crud` | Generated CRUD UI |
| `interfaces.cli` | Major CLI binary |
| `auth` | Clerk/auth integration |
| `domain` | DNS, SSL, hosting |

## What Users Think About

End users (not developers) think about four things:

1. **Role** - "What does my agent do?"
2. **Ontology** - "What things do I work with?"
3. **Skills** - "What can my agent do for me?"
4. **External Data** - "Where does my data come from?" (often needs solution architect)

They configure these through conversation with Major, not by editing files.

## What Users Don't Think About

- YAML files
- MCP servers
- Markdown
- Git
- Deployments
- Infrastructure
- The word "agent"

## Summary

```
┌─────────────────────────────────────────────────────────┐
│                        USERS                             │
│            (just use the app)                            │
├─────────────────────────────────────────────────────────┤
│                     INTERFACES                           │
│         CLI    │    Web App    │    CRUD App             │
│                │  (Chat+Lake)  │                         │
├─────────────────────────────────────────────────────────┤
│                       DSL                                │
│    (developers define apps)                              │
├─────────────────────────────────────────────────────────┤
│                     AGENT OS                             │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌───────────┐     │
│  │  Major  │ │  Batou  │ │ Ishikawa │ │ Tachikoma │     │
│  │ (kernel)│ │(fs + db)│ │(syscalls)│ │ (daemon)  │     │
│  └─────────┘ └─────────┘ └──────────┘ └───────────┘     │
├─────────────────────────────────────────────────────────┤
│                   CONTEXT LAKE                           │
│         (git-backed markdown files)                      │
└─────────────────────────────────────────────────────────┘
```

Tachi: Agent-native apps.
