# motoko

> A Python package for building role-based AI agents with model flexibility and tool execution

Named after Major Motoko Kusanagi (Ghost in the Shell) - an agent that dives into different contexts, switches roles, and interfaces seamlessly with systems.

## Overview

**motoko** replicates Claude Code's agent loop and tool execution patterns as a Python package, enabling model flexibility and better role control.

### What It Is

A Python package that:
- Provides Claude Code-style agent loop and tool usage patterns
- Supports multiple LLM providers through unified interface
- Gives direct control over agent behavior (no subprocess)
- Enables dynamic role switching and multiple roles per session
- Provides full toolset: files, web search, git, bash, skills framework

### What It's Not

- Not a subprocess wrapper around Claude Code CLI
- Not using Anthropic's Agentic SDK directly (building our own)
- Not RAG-based (prefers sharing entirety of context)
- Not opinionated about role format (apps control role loading)

## Goals

### Primary
1. **Model Flexibility**: Swap between Claude, Gemini, or other providers
2. **Role Control**: Mid-session switching, multiple roles, role-specific tool access
3. **Direct Control**: Pure Python, no subprocess management
4. **Tool Replication**: Match Claude Code's tool execution patterns
5. **Unified Backend**: One package used by all three existing apps

### Secondary
- Maintain markdown-first workflow
- Support skills framework like Claude Code
- Configurable and extensible tool system
- Clean API for app integration

## Current Applications

Three apps will use motoko:

1. **coyote** (port 8002): Artist management with role-based conversations
2. **escuela** (port 8003): Educational learning with teaching roles
3. **project-management** (port 8001): PM and task tracking

All share the same pattern:
```
Web UI → FastAPI → [Role Context] → LLM with tools → Markdown workspace
```

## Architecture Decisions

### Package Structure

**motoko** is a Python package that apps import:

```python
from motoko import Agent

agent = Agent(model="gemini-3-flash")
response = agent.chat(
    system_prompt=role_content,
    message=user_message,
    workspace="/workspace"
)
```

### Model Abstraction

**Unified interface** to multiple providers (LiteLLM-style):
- Anthropic Claude (Sonnet, Opus, Haiku)
- Google Gemini (3.0, 2.0, etc.)
- Future: OpenAI, open models, etc.

Apps specify model name, motoko handles provider differences.

### Tool System

**Expansive and configurable** - replicating Claude Code's toolset:

**Core Tools:**
- **Files**: Read, Write, Edit, Glob, Grep
- **Web**: WebSearch, WebFetch
- **Git**: Status, commit, push, pull, branch operations
- **Bash**: Command execution with sandboxing
- **Skills**: Framework for loading and executing skills

**Tool Configuration:**
- Tools are configurable per agent instance
- Roles can specify which tools they have access to (future)
- Custom Python tools can be added

### Role System

**Right for Now:**
- Package is **agnostic** about role format
- Apps pass `system_prompt` as string (load however they want)
- Role loading stays in each app (coyote, escuela, PM)
- Package focuses on: model abstraction + tool execution + agent loop

**Right for Future:**
- Package includes optional `RoleLoader` utilities
- Supports standardized role format (but not required)
- Role switching primitives built into agent
- Apps can use builtin utilities or roll their own

**Current Role Format (in apps):**
- Roles are numbered markdown files: `01-architect.md`, `02-writer.md`
- Apps parse them (extract ID, name, description)
- Role content becomes system prompt
- Different apps have different role sets

## Role Control Capabilities

Three key capabilities to enable:

### 1. Role Switching Mid-Session
Agent can change roles during a conversation:
```python
agent.switch_role(new_system_prompt)
```

### 2. Multiple Roles in One Session
Multiple roles can participate in a conversation:
```python
agent.add_role(role_name, system_prompt)
agent.chat_as(role_name, message)
```

### 3. Role-Specific Tool Access
Roles can have different tool permissions:
```python
agent = Agent(
    model="gemini-3",
    tools={
        "architect": [FileTools, GitTools],
        "writer": [FileTools, WebTools],
        "executor": [BashTools]
    }
)
```

## Agent Loop (Claude Code Pattern)

**Key Challenge:** Getting this right is critical.

### The Loop

```python
messages = [{"role": "user", "content": user_message}]

while True:
    # 1. Call model with tools available
    response = model.chat(
        messages=messages,
        tools=tool_definitions,
        system=system_prompt
    )

    # 2. Check if model wants to use tools
    if response.has_tool_calls:
        # 3. Execute tools (parallel if independent)
        tool_results = execute_tools(response.tool_calls)

        # 4. Add assistant response to history
        messages.append({
            "role": "assistant",
            "content": response.content  # includes tool calls
        })

        # 5. Add tool results
        messages.append({
            "role": "user",
            "content": tool_results
        })

        # 6. Loop back - model sees results and decides next step
        continue

    else:
        # Model is done, return final response
        return response.content
```

### Key Aspects

1. **Tool Decisions**: Model decides which tools, what parameters, what order
2. **Parallel Execution**: Independent tools run concurrently
3. **Tool Results**: Returned as user message with tool_result blocks
4. **Iteration**: Model can call tools multiple times based on results
5. **Completion**: Model returns text when it has enough information

### Tool Calling Flow

**Tool Definition** (JSON Schema):
```python
{
    "name": "read_file",
    "description": "Read contents of a file",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to file"}
        },
        "required": ["file_path"]
    }
}
```

**Tool Use** (Model Response):
```python
{
    "type": "tool_use",
    "id": "toolu_123abc",
    "name": "read_file",
    "input": {"file_path": "/path/to/file.py"}
}
```

**Tool Result** (Execution Response):
```python
{
    "type": "tool_result",
    "tool_use_id": "toolu_123abc",
    "content": "file contents here...",
    "is_error": false
}
```

### Multi-Tool Calls

Model can request multiple tools in one turn:
```python
response.content = [
    {"type": "text", "text": "Let me check both files"},
    {"type": "tool_use", "id": "tool_1", "name": "read_file",
     "input": {"file_path": "main.py"}},
    {"type": "tool_use", "id": "tool_2", "name": "read_file",
     "input": {"file_path": "utils.py"}}
]
```

Execute all tools and return all results in next message.

## Skills Framework

**Replicate Claude Code's skill system exactly:**
- Skills are reusable capabilities
- Loaded from skill definitions
- Can be invoked by the agent
- Provide specialized functionality

Details TBD after studying Claude Code's implementation.

## Integration Pattern

Apps use motoko like this:

```python
# App's role loader (stays in app code)
from roles import get_role

# motoko package
from motoko import Agent

# Load role (app-specific)
role = get_role("01")

# Create agent
agent = Agent(
    model="gemini-3-flash",
    workspace="/workspace"
)

# Chat with role context
response = agent.chat(
    system_prompt=role.content,
    message=user_message,
    session_id=session_id
)
```

## Technical Considerations

### Streaming
- Support streaming responses like Claude Code
- Server-Sent Events (SSE) for web UI
- Progressive tool execution feedback

### State Management
- Session state across multiple turns
- Role switching without losing context
- Tool execution history

### Error Handling
- Tool failures
- Model API errors
- Graceful degradation

### Performance
- Parallel tool execution where possible
- Efficient context management
- Streaming for responsiveness

## Implementation Decisions

### Model Abstraction Layer

**Decision**: Abstract model API differences in the model layer (not leaked to agent).

**Rationale**: Different providers (Anthropic, Gemini, OpenAI) use different:
- Function calling formats
- Streaming protocols
- Response structures
- Tool result formats

**Approach**:
```python
class BaseModel(ABC):
    @abstractmethod
    def chat(self, messages, tools, stream=False):
        """Unified interface across all providers"""
        pass

    @abstractmethod
    def format_tools(self, tools):
        """Convert our tool format to provider-specific format"""
        pass

    @abstractmethod
    def parse_response(self, response):
        """Convert provider response to our unified format"""
        pass

class AnthropicModel(BaseModel):
    # Anthropic-specific implementation
    pass

class GeminiModel(BaseModel):
    # Gemini-specific implementation
    pass
```

Agent code never sees provider differences.

### Tool Implementation

**Decision**: Tools are classes (best practice for maintainability).

**Rationale**:
- Easier to maintain and extend
- Clear interface and contract
- Encapsulation of tool logic
- Type safety and documentation

**Approach**:
```python
class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    def get_schema(self) -> dict:
        """Return JSON schema for tool parameters"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute tool and return result"""
        pass

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read contents of a file"

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to file"
                }
            },
            "required": ["file_path"]
        }

    def execute(self, file_path: str) -> ToolResult:
        with open(file_path) as f:
            content = f.read()
        return ToolResult(
            content=content,
            verbosity="normal"
        )
```

### Streaming

**Decision**: Support streaming for ALL models.

**Rationale**: Streaming provides better UX regardless of provider.

**Requirements**:
- Abstract streaming differences across providers
- Anthropic: native SSE streaming
- Gemini: streaming API with different format
- OpenAI: streaming with data chunks
- Unified streaming interface in Agent

**Approach**:
```python
# Agent provides consistent streaming interface
async for chunk in agent.stream(message, system_prompt):
    yield chunk  # Normalized format regardless of provider
```

### Tool Result Verbosity

**Decision**: Tiers of verbosity for tool results.

**Rationale**:
- Different contexts need different detail levels
- Control context window usage
- Allow debugging vs production modes

**Tiers**:
1. **minimal**: Summary only (e.g., "Read 150 lines from main.py")
2. **normal**: Standard output (e.g., first 50 lines + summary)
3. **verbose**: Full output (e.g., entire file contents + metadata)

**Approach**:
```python
class ToolResult:
    def __init__(self, content, metadata=None):
        self.content = content
        self.metadata = metadata or {}

    def format(self, verbosity="normal") -> str:
        if verbosity == "minimal":
            return self.summary()
        elif verbosity == "normal":
            return self.standard()
        elif verbosity == "verbose":
            return self.detailed()

    def summary(self) -> str:
        """Brief summary of result"""
        return f"{self.metadata.get('action')} {self.metadata.get('target')}"

    def standard(self) -> str:
        """Standard output (default)"""
        return self.content[:1000] + "..." if len(self.content) > 1000 else self.content

    def detailed(self) -> str:
        """Full output with metadata"""
        return f"{self.content}\n\nMetadata: {self.metadata}"
```

Verbosity can be:
- Set globally on Agent
- Overridden per tool
- Adjusted based on context window pressure

## Open Questions

1. **Skills Implementation**: What's the interface for skills?
2. **Model Context Management**: How to handle different context window sizes?
3. **Concurrency**: How to handle parallel tool execution?
4. **Session Persistence**: How to save/restore agent state?
5. **Tool Security**: Sandboxing for bash, file access controls?

## Success Criteria

motoko is successful when:

1. ✓ Can swap Claude for Gemini in existing apps with minimal code changes
2. ✓ Role switching works seamlessly mid-conversation
3. ✓ Tool execution matches Claude Code's intelligence and patterns
4. ✓ All three apps (coyote, escuela, PM) use it as unified backend
5. ✓ Skills framework supports custom capabilities
6. ✓ Performance is acceptable (streaming, responsiveness)
7. ✓ Code is maintainable and extensible

## Next Steps

1. **Study Claude Code's agent loop** - understand tool execution patterns
2. **Design core Agent class** - API surface and responsibilities
3. **Implement model abstraction** - unified provider interface
4. **Build tool system** - file, web, git, bash tools
5. **Create agent loop** - tool selection, execution, iteration
6. **Add skills framework** - replicating Claude Code's system
7. **Test with one app** - integrate with coyote or escuela
8. **Extend to all apps** - roll out to remaining applications

## References

- Claude Code: Anthropic's official CLI for Claude
- Agentic SDK: Anthropic's Python SDK for building agents
- Ghost in the Shell: Source of package name (Major Motoko Kusanagi)
- Current apps: coyote, escuela, project-management (all at `/Users/joshuacook/working/`)

---

**Status**: Specification phase
**Created**: 2025-01-18
**Last Updated**: 2025-01-18

## Agent Loop Understanding

See "Agent Loop (Claude Code Pattern)" section above for detailed explanation of:
- Tool-use conversation loop
- Tool definitions, calls, and results
- Multi-tool execution
- Streaming patterns

### Key Decisions Made

1. ✓ Model API differences abstracted in model layer
2. ✓ Tools implemented as classes (best practice)
3. ✓ Streaming required for all models
4. ✓ Tool results have verbosity tiers (minimal, normal, verbose)
