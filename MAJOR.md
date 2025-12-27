# Major: Chat Agent Architecture

> Discussion document for the Major chat agent - consolidating Claude Agent SDK usage into motoko.

## Context

We have two repositories interfacing with the deployed application:

- **claude-code-apps** - Application layer (API, web, mobile, auth, infra)
- **motoko** - Knowledge layer (Batou MCP, Tachikoma cleanup, Context Lake)

Race conditions and debugging difficulties have emerged from unclear separation of concerns.

## Ontology

The system has five layers:

| Layer | What | Examples |
|-------|------|----------|
| **Interface** | How users interact | Web, Mobile, Motoko CLI (future) |
| **Agent** | AI that processes | Major (chat), Tachikoma (batch) |
| **Tools** | What agents use | Raw file ops, Batou MCP |
| **Workspace** | Knowledge data | Git repo with entities |
| **Infrastructure** | Supporting services | Auth, Notifications, Storage, API |

**Why this matters:** Claude Code CLI conflates interface + agent, creating ontological bleed. We separate them:

- **Motoko CLI** = pure interface (future, not yet built) → talks to Major
- **Web/Mobile** = pure interfaces → talk to Major via API
- **Major** = pure chat agent (no interface concerns)
- **Tachikoma** = pure batch agent

## Summary Tables

### Current State

| Component | Layer | Repo |
|-----------|-------|------|
| Web | Interface | claude-code-apps |
| Mobile | Interface | claude-code-apps |
| Claude Code CLI | Interface + Agent (blended) | - |
| Chat Agent (AgentManager) | Agent | claude-code-apps |
| Tachikoma | Agent | motoko |
| Batou MCP | Tools | motoko |
| Context Lake Entities | Workspace | **Both** (duplicate) |
| Agent Gateway API | Infrastructure | claude-code-apps |
| Entity API | Infrastructure | claude-code-apps |
| Auth API | Infrastructure | claude-code-apps |
| Conversation API | Infrastructure | claude-code-apps |
| Workspace API | Infrastructure | claude-code-apps |
| File API | Infrastructure | claude-code-apps |
| Device API | Infrastructure | claude-code-apps |
| Tracing (Langfuse) | Infrastructure | claude-code-apps |
| File Processor (Cloud Run) | Infrastructure | claude-code-apps |
| Push Notifications (FCM) | Infrastructure | claude-code-apps |
| Firestore | Infrastructure | claude-code-apps |

### Future State

| Component | Layer | Sub-layer | Repo | Runtime |
|-----------|-------|-----------|------|---------|
| Web | Interface | | claude-code-apps | Browser |
| Mobile | Interface | | claude-code-apps | Mobile App |
| Motoko CLI | Interface | | motoko (future) | Local |
| **Major** | Agent | | **motoko** | Local / VM |
| Tachikoma | Agent | | motoko | Local / VM |
| Batou MCP | Tools | | motoko | Local / VM |
| Context Lake Entities | Workspace | | **motoko** | Local / VM |
| Session API | Infrastructure | Agent Infra | claude-code-apps | VM |
| Event Relay | Infrastructure | Agent Infra | claude-code-apps | VM |
| Push Notifications | Infrastructure | Agent Infra | claude-code-apps | VM |
| Entity API | Infrastructure | Entity Infra | claude-code-apps | VM |
| Conversation API | Infrastructure | Conversation Infra | claude-code-apps | VM |
| Firestore | Infrastructure | Conversation Infra | claude-code-apps | GCP (managed) |
| Auth API | Infrastructure | Auth Infra | claude-code-apps | VM |
| File API | Infrastructure | File Infra | claude-code-apps | VM |
| File Processor | Infrastructure | File Infra | claude-code-apps | Cloud Run |
| Tracing | Infrastructure | Observability | claude-code-apps | Langfuse (managed) |
| Workspace API | Infrastructure | Ad hoc | claude-code-apps | VM |

**Infrastructure Sub-layers:**
- **Agent Infra** - Control + observe agents (Session API, Event Relay, Push)
- **Entity Infra** - Deterministic entity queries for clients
- **Conversation Infra** - Conversation persistence (Firestore)
- **Auth Infra** - Clerk integration
- **File Infra** - Upload + processing
- **Observability** - Tracing/logging

**Key changes:**
- Chat agent moves from claude-code-apps → motoko (as Major)
- Context Lake entities consolidated in motoko (single implementation)
- Motoko CLI added as future local interface
- Claude Code CLI removed (no longer used)
- Agent Gateway API split into Session API + Event Relay + Push
- Entity API stays (clients need deterministic entity queries)
- Workspace API is ad hoc, not priority
- claude-code-apps becomes pure infrastructure + interfaces

---

## Discussion: Agent Gateway Model

This is the critical architectural question. We're experiencing race conditions and don't have clarity on the right model.

### Claude Agent SDK Capabilities

The SDK provides more than we're currently using. Here's what's available:

#### Event Stream

Clients can observe the full stream of events:

| Event Type | What it Contains |
|------------|------------------|
| `SDKSystemMessage` | Init metadata (tools, mcp_servers, model, permissionMode) |
| `SDKAssistantMessage` | Model output (TextBlock, ThinkingBlock, ToolUseBlock) |
| `SDKUserMessage` | User input and tool results |
| `SDKPartialAssistantMessage` | Streaming incremental updates (opt-in via `includePartialMessages`) |
| `SDKResultMessage` | Completion (success/error, duration, cost, usage) |
| `SDKCompactBoundaryMessage` | Conversation compaction |

Plus 12 hook events: PreToolUse, PostToolUse, PermissionRequest, SessionStart, SessionEnd, etc.

#### Session Management

Two models available:

| Model | Behavior | Use Case |
|-------|----------|----------|
| `query()` | Fresh per request, no memory | One-off tasks |
| `ClaudeSDKClient` | Persistent sessions, maintains conversation state | Multi-turn conversations |

**We should use `ClaudeSDKClient`** - it maintains conversation history across exchanges.

#### Interaction Points

The SDK defines explicit interaction points:

1. **`AskUserQuestion` tool** - Agent presents structured questions with options
   - Header (short label)
   - Question text
   - Options with descriptions
   - Multi-select support
   - User responds with choice or "Other"

2. **Permission prompts** - When tool needs approval (configurable via `permissionMode`)

**Key insight:** Interaction points are NOT empty prompts. They're explicit, structured requests from the agent.

#### Execution Model

```
Your App → spawns subprocess → Claude Code CLI → streams JSON → Your App
```

- Per-request subprocess spawning
- Streaming JSON protocol (newline-delimited)
- Sequential within session, parallel across sessions
- Each `query()` call launches CLI subprocess

#### Control Points

| Control | Method | Effect |
|---------|--------|--------|
| Interrupt | `client.interrupt()` | Stop mid-execution |
| Rewind | `client.rewind_files(uuid)` | Restore file state |
| Permission mode | Options | Auto-accept, plan mode, bypass |
| Hooks | PreToolUse, PostToolUse, etc. | Intercept and modify execution |
| Budget | `maxBudgetUsd` | Hard cost limit |
| Turns | `maxTurns` | Limit conversation depth |

### SDK Message Types (Official Documentation)

**Base Message Types:**
```python
Message = UserMessage | AssistantMessage | SystemMessage | ResultMessage
```

| Message Type | When | Contains |
|--------------|------|----------|
| `SystemMessage` | Session start, compaction | `subtype` (init, compact_boundary), `data` dict with session_id, tools, model, etc. |
| `AssistantMessage` | Model response | `content: list[ContentBlock]`, `model` |
| `UserMessage` | User input, tool results | `content: str \| list[ContentBlock]` |
| `ResultMessage` | Session end | success/error, duration_ms, duration_api_ms, cost, usage, session_id, result |

**Streaming Type (enable with `include_partial_messages=True`):**

`StreamEvent` - Contains raw streaming events:
| Event Type | What |
|------------|------|
| `message_start` | Beginning of message with model info, initial usage |
| `content_block_start` | Start of content block |
| `content_block_delta` | Incremental updates (text_delta, tool_use_delta) |
| `content_block_stop` | End of content block |
| `message_delta` | Stop reason, final usage |

**Content Block Types:**
```python
ContentBlock = TextBlock | ThinkingBlock | ToolUseBlock | ToolResultBlock
```

**Hook Events (Python SDK):**
- `PreToolUse` - Before tool execution
- `PostToolUse` - After tool execution
- `UserPromptSubmit` - When user submits prompt
- `Stop` - When stopping execution
- `SubagentStop` - When subagent completes
- `PreCompact` - Before message compaction

Note: Python SDK doesn't support `SessionStart`, `SessionEnd`, `Notification`, `PostToolUseFailure`, `PermissionRequest` (TypeScript only).

**Source:** [Agent SDK reference - Python](https://platform.claude.com/docs/en/agent-sdk/python)

### SDK Investigation Results (2025-12-26)

**Confirmed from testing:**
- `session_id` in SystemMessage init data
- Resume works via `resume=session_id` option
- Session correctly maintains conversation history (remembered "42")
- Tool use appears as `ToolUseBlock` in AssistantMessage
- Tool results appear as `ToolResultBlock` in UserMessage
- `StreamEvent` with `include_partial_messages=True` provides real-time text deltas

**Event sequence observed (streaming):**
```
SystemMessage (init) → StreamEvent (message_start) → StreamEvent (content_block_start)
→ StreamEvent (content_block_delta)* → AssistantMessage → StreamEvent (content_block_stop)
→ StreamEvent (message_delta) → ResultMessage
```

**Default tools (Claude Code CLI 2.0.62):**
```
Task, AgentOutputTool, Bash, Glob, Grep, ExitPlanMode, Read, Edit, Write,
NotebookEdit, WebFetch, TodoWrite, WebSearch, BashOutput, KillShell, Skill,
SlashCommand, EnterPlanMode
```

**AskUserQuestion:** Not in defaults - must be explicitly added to `tools` list.
Requires SDK 0.1.18+ (not available in 0.1.14).

**Test script:** `scripts/sdk_investigation.py`

### Major Implementation Specification

Based on SDK capabilities, Major should:

1. **Use `ClaudeSDKClient`** for persistent sessions across exchanges
2. **Pass through the full event stream** to clients (with client-side toggles)
3. **Handle `AskUserQuestion`** as the interaction point for human feedback
4. **Use hooks** for logging, validation, and custom behavior
5. **Expose control methods**: interrupt, budget limits, permission modes

### Event Flow

```
Major (ClaudeSDKClient)
    │
    ├── SDKSystemMessage ──────→ Client (init metadata)
    ├── SDKAssistantMessage ───→ Client (text, thinking, tool use)
    ├── SDKPartialAssistantMessage → Client (streaming increments)
    ├── SDKUserMessage ────────→ Client (tool results)
    ├── AskUserQuestion ───────→ Client (structured question)
    │                              ↓
    │                          User responds
    │                              ↓
    ├── ←──────────────────────── Client (answer)
    └── SDKResultMessage ──────→ Client (completion)
```

### Decisions

1. **Event passthrough** - Full SDK event stream passthrough with client-side toggles per event type.

2. **Multi-client coordination** - Assume user won't answer same question from two places simultaneously. No complex coordination needed.

### Open Questions

1. **Interaction flow (`AskUserQuestion`)** - RESOLVED: Works in SDK 0.1.18+

   **Investigation result (2025-12-26):**
   - AskUserQuestion was NOT available in SDK 0.1.14 (filtered out)
   - **SDK 0.1.18+**: Available when explicitly included in `tools` list
   - Must use `can_use_tool` callback to handle user answers

   **Working implementation:**
   ```python
   from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
   from claude_agent_sdk.types import PermissionResultAllow

   async def can_use_tool_handler(tool_name, tool_input, context=None):
       if tool_name == 'AskUserQuestion':
           questions = tool_input.get('questions', [])

           # Collect answers from user (via event relay in Major)
           answers = {}
           for q in questions:
               question_text = q.get('question', '')
               # Get user's answer somehow
               answers[question_text] = await get_user_answer(question_text)

           return PermissionResultAllow(
               updated_input={
                   'questions': questions,
                   'answers': answers
               }
           )
       return PermissionResultAllow(updated_input=tool_input)

   options = ClaudeAgentOptions(
       tools=['AskUserQuestion', 'Bash', 'Read', ...],  # Must explicitly include
       can_use_tool=can_use_tool_handler,
   )
   ```

   **Event flow:**
   1. Agent calls AskUserQuestion tool with structured questions
   2. SDK invokes `can_use_tool` callback
   3. Major pauses, emits question event to client
   4. Client presents UI, user selects answer
   5. Major receives answer, returns `PermissionResultAllow` with answers
   6. Agent receives `ToolResultBlock` with user's answers
   7. Agent continues with knowledge of user's choices

2. **Session persistence** - RESOLVED: SDK handles this natively.
   - SDK returns `session_id` in initial system message (type: 'system', subtype: 'init')
   - Sessions can be resumed via `resume=session_id` option
   - SDK automatically loads full conversation history when resuming
   - Sessions survive server restarts if session_id is preserved
   - `fork_session=True` creates a branch without modifying original

   **Firestore's role:** Store `session_id` mapped to conversation. Not full message history.

   ```
   Client sends message
       ↓
   Session API looks up session_id in Firestore
       ↓
   Major calls SDK with resume=session_id
       ↓
   SDK loads full history automatically
       ↓
   Events stream back
   ```

---

## Current State (Detailed)

### Application Concerns

| Concern | Location | Implementation | Domain |
|---------|----------|----------------|--------|
| Claude Agent SDK | claude-code-apps | `platform/src/agent.py` | AI |
| Batou (MCP) | motoko | `batou/src/batou/server.py` | AI |
| Tachikoma | motoko | `tachikoma/src/tachikoma/agent.py` | AI |
| Context Lake | Both | `platform/src/entities.py` + `batou/.../entities.py` | Data |
| API | claude-code-apps | `platform/src/main.py` | Data |
| Tracing | claude-code-apps | `platform/src/tracing.py` | Data |
| Web Client | claude-code-apps | `web/` | Client |
| Mobile Client | claude-code-apps | `mobile/` | Client |
| Auth | claude-code-apps | `platform/src/auth.py` | Client |
| File Processing | claude-code-apps | `file-processor/` | Client |
| Notifications | claude-code-apps | `platform/src/push.py` | Client |

### Three Domains

1. **AI** - Claude Agent SDK, MCP servers, autonomous agents
2. **Data** - Context Lake entities, API, persistence, tracing
3. **Client** - Web, mobile, auth, notifications

### Problem

- Context Lake has duplicate `entities.py` implementations
- Claude Agent SDK is used in both repos (Tachikoma in motoko, AgentManager in claude-code-apps)
- No shared agent code despite similar patterns
- Race conditions across clients difficult to debug due to scattered concerns

## Proposal: Major Agent

Move the chat agent implementation to motoko as **Major**, consolidating all AI domain concerns in one repo.

### After

```
motoko/
├── batou/      → MCP server (tools for AI)
├── tachikoma/  → Batch agent (cleanup)
└── major/      → Chat agent (new)

claude-code-apps/
└── platform/src/
    ├── main.py     → API routes, Firestore, streaming
    └── agent.py    → Thin wrapper importing major
```

### Ownership

| Domain | Owner | Responsibilities |
|--------|-------|------------------|
| AI | motoko | SDK usage, MCP servers, agent logic, system prompts |
| Data | claude-code-apps | Firestore, API routes, tracing, file storage |
| Client | claude-code-apps | Web, mobile, auth, push notifications |

## Current AgentManager Analysis

The existing `platform/src/agent.py` (688 lines) has these responsibilities:

| Responsibility | Move to major | Stay in claude-code-apps |
|----------------|---------------|--------------------------|
| SDK client management (per-conversation) | Yes | |
| MCP config loading (platform/user/workspace hierarchy) | Yes | |
| Skills syncing to workspace | Yes | |
| Workspace path validation | Yes | |
| System prompt building (Context Lake + history + attachments) | Yes | |
| Message streaming + delta calculation | Yes | |
| Event type conversion (SDK → app events) | Yes | |
| Firestore reads (get_conversation, get_messages) | | Yes |
| Langfuse tracing integration | | Yes |

## Major Interface Design

### Core Classes

```python
class MajorAgent:
    """Chat agent using Claude Agent SDK."""

    async def create_session(
        self,
        workspace_path: str,
        conversation_history: list[dict] = None,
        attached_entities: list[dict] = None,
    ) -> str:
        """Create a new chat session. Returns session_id."""

    async def send_message(
        self,
        session_id: str,
        message: str,
    ) -> AsyncGenerator[Event, None]:
        """Send message and stream response events."""

    async def interrupt(self, session_id: str) -> None:
        """Interrupt current response."""

    async def close_session(self, session_id: str) -> None:
        """Close session and cleanup resources."""
```

### Event Types

```python
@dataclass
class TextDelta:
    text: str

@dataclass
class ToolUse:
    name: str
    input: dict
    id: str

@dataclass
class ToolResult:
    tool_use_id: str
    output: str

@dataclass
class Done:
    usage: dict  # {input_tokens, output_tokens}
    cost: float
    is_error: bool
    result: str | None

@dataclass
class Error:
    message: str

Event = TextDelta | ToolUse | ToolResult | Done | Error
```

### Usage in claude-code-apps

```python
from major import MajorAgent, TextDelta, ToolUse, ToolResult, Done, Error

agent = MajorAgent()

# Create session with context from Firestore
conversation = firestore.get_conversation(conversation_id)
history = firestore.get_messages(conversation_id)

session_id = await agent.create_session(
    workspace_path=conversation['workspace_path'],
    conversation_history=history,
    attached_entities=conversation.get('attached_entities'),
)

# Stream response and wire to infrastructure
async for event in agent.send_message(session_id, message):
    match event:
        case TextDelta(text):
            # Update Firestore streaming_content
            firestore.update_streaming(conversation_id, text)
        case ToolUse(name, input, id):
            # Log to Langfuse, save to Firestore
            tracing.log_tool_use(trace, name, input, id)
            firestore.save_tool_use(conversation_id, name, input, id)
        case ToolResult(tool_use_id, output):
            # Log to Langfuse, save to Firestore
            tracing.log_tool_result(trace, tool_use_id, output)
            firestore.save_tool_result(conversation_id, tool_use_id, output)
        case Done(usage, cost, is_error, result):
            # Finalize conversation
            firestore.complete_conversation(conversation_id, usage, cost)
            push.notify(user_id, conversation_id)
        case Error(message):
            firestore.set_error(conversation_id, message)
```

## MCP Configuration

Major loads MCP configs from a hierarchy (later overrides earlier):

1. **Platform level**: `/opt/claude-code-apps/platform/.mcp.json`
2. **User level**: `/opt/workspaces/{username}/.mcp.json`
3. **Workspace level**: `/opt/workspaces/{username}/{workspace}/.mcp.json`

Batou MCP server gets `WORKSPACE_PATH` injected automatically.

## System Prompt

Major builds the system prompt from:

1. **Base prompt** - Context Lake explanation, tool guidance, workspace boundaries
2. **Conversation history** - For session restoration (optional)
3. **Attached entities** - User-selected documents as primary context (optional)

The base prompt (CONTEXT_LAKE_SYSTEM_PROMPT) explains:
- Chelle's purpose as a knowledge production platform
- Context Lake structure (root files, roles/, docs/, lake/)
- Two tool modes: Batou MCP (semantic) vs direct file tools
- Workspace boundary restrictions

## Skills

Major syncs skills from platform/user levels to workspace `.claude/skills/` directory so the SDK can discover them. Workspace-level skills take precedence.

## Open Questions

1. **Session persistence**: Should Major persist sessions to disk, or is in-memory sufficient with claude-code-apps handling restoration via conversation_history?

2. **MCP config paths**: Hardcoded `/opt/` paths work for deployment but not local dev. Should Major accept config paths as parameters?

3. **Workspace validation**: Currently validates paths are under `/opt/workspaces/`. Should this be configurable?

4. **Delta calculation**: Major calculates text deltas (SDK sends accumulated text). Should this be Major's responsibility or claude-code-apps'?

5. **Rate limiting**: Current implementation updates Firestore every 0.5s to avoid rate limits. This logic should stay in claude-code-apps, not Major.

6. **Tracing hooks**: Should Major emit more granular events for tracing (generation start/end, spans), or just the core events above?

## Race Condition Investigation

Known issues to investigate once separation is complete:

1. **Multi-client streaming** - Same conversation accessed from web + mobile simultaneously
2. **Conversation state** - Status transitions (idle → streaming → idle) across clients
3. **Entity writes during streaming** - Batou tool writes while Firestore updates happening
4. **Git operations** - Multiple entity operations triggering concurrent git commits

Separation should help isolate whether issues are in:
- AI domain (Major/Batou/SDK)
- Data domain (Firestore/API)
- Client domain (polling/state management)

## Next Steps

1. Create `major/` directory structure in motoko
2. Extract core agent logic from claude-code-apps AgentManager
3. Implement clean event-based interface
4. Create thin wrapper in claude-code-apps that imports major
5. Test with single client first, then multi-client
6. Instrument and debug race conditions with clear domain boundaries
