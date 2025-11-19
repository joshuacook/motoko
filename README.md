# motoko

> A Python package for building role-based AI agents with model flexibility and tool execution

Named after **Major Motoko Kusanagi** from *Ghost in the Shell* - an agent that dives into different contexts, switches roles, and interfaces seamlessly with systems.

## Overview

**motoko** replicates Claude Code's agent loop and tool execution patterns as a pure Python package, enabling:

- 🔄 **Model Flexibility**: Swap between Claude, Gemini, or other LLM providers
- 🎭 **Role Management**: Dynamic role switching and multi-role conversations
- 🛠️ **Rich Toolset**: Files, web, git, bash, and custom Python tools
- ⚡ **Streaming**: Real-time responses across all providers
- 📦 **Pure Python**: Direct control, no subprocess management

## Status

🚧 **In Development** - Currently implementing Epic 1: Foundation

See [SPEC.md](SPEC.md) for detailed specifications and [EPICS.md](EPICS.md) for development roadmap.

## Installation

```bash
# Development installation
cd motoko
pip install -e ".[dev]"
```

## Quick Start

```python
from motoko import Agent, create_model, ReadFileTool, GlobTool

# Example 1: Agent with tools
model = create_model("claude-3-5-sonnet-20241022")

tools = [
    ReadFileTool(workspace="/path/to/project"),
    GlobTool(workspace="/path/to/project"),
]

agent = Agent(
    model=model,
    tools=tools,
    workspace="/path/to/project"
)

# Agent will use tools automatically to answer questions
response = agent.chat(
    message="How many Python files are in this project?",
    system_prompt="You are a helpful coding assistant"
)
print(response.text)

# Example 2: Direct model usage (no tools)
from motoko import Message, MessageRole

model = create_model("gemini-2.0-flash-exp")
messages = [Message(role=MessageRole.USER, content="Hello!")]
response = model.chat(messages=messages, system="You are helpful")
print(response.text)

# Example 3: Model switching
for model_name in ["claude-3-5-sonnet-20241022", "gemini-2.0-flash-exp"]:
    model = create_model(model_name)
    response = model.chat(messages=messages)
    print(f"{model_name}: {response.text}")

# Example 4: Using Skills
from motoko import Agent, create_model, ReadFileTool, GlobTool

model = create_model("claude-3-5-sonnet-20241022")
tools = [ReadFileTool(workspace="/path/to/project"), GlobTool(workspace="/path/to/project")]

agent = Agent(
    model=model,
    tools=tools,
    workspace="/path/to/project",
    skills_dir="/path/to/skills"  # Directory containing skill .md files
)

# List available skills
print("Available skills:", [s['name'] for s in agent.list_skills()])

# Invoke a skill with parameters
response = agent.invoke_skill(
    skill_name="code-review",
    file_pattern="*.py",
    focus="security"
)
print(response.text)

# Example 5: Role Management
from motoko import Agent, create_model, ReadFileTool, WriteFileTool

model = create_model("claude-3-5-sonnet-20241022")
agent = Agent(model=model, tools=[ReadFileTool(), WriteFileTool()])

# Add roles with different capabilities
agent.add_role(
    "researcher",
    "You gather and analyze information",
    tools=[ReadFileTool()]
)

agent.add_role(
    "writer",
    "You create documentation",
    tools=[ReadFileTool(), WriteFileTool()]
)

# Chat as specific roles
research = agent.chat_as("researcher", "Analyze the codebase")
doc = agent.chat_as("writer", f"Document this: {research.text}")

# Or switch roles mid-conversation
agent.switch_role("You are a code reviewer", role_name="reviewer")
response = agent.chat("Review the code quality")
```

## Architecture

```
┌─────────────────────────────────────────┐
│           Agent (Core Loop)             │
│  • Message management                   │
│  • Tool orchestration                   │
│  • Role switching                       │
└─────────────┬───────────────────────────┘
              │
      ┌───────┴────────┐
      │                │
┌─────▼─────┐    ┌────▼─────┐
│  Models   │    │  Tools   │
│           │    │          │
│ Anthropic │    │  Files   │
│  Gemini   │    │   Web    │
│  OpenAI   │    │   Git    │
│   ...     │    │   Bash   │
└───────────┘    └──────────┘
```

## Features

### Model Abstraction
- Unified interface across providers
- Automatic tool format conversion
- Consistent streaming API
- Error handling abstraction

### Tool System
- Class-based tool implementation
- JSON schema definitions
- Verbosity control (minimal, normal, verbose)
- Parallel execution support

### Agent Loop
- Claude Code-style tool calling
- Multi-turn conversations
- Context management
- Error recovery

### Skills Framework
- Reusable capabilities defined in markdown
- YAML frontmatter for metadata
- Parameter substitution in prompts
- Tool requirements validation
- Sync and streaming skill execution

### Role Management
- Dynamic role switching mid-conversation
- Multiple roles in one session
- Role-specific tool access and permissions
- Role state and history tracking
- Streaming support for roles

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy motoko

# Linting
ruff check motoko
```

## Project Structure

```
motoko/
├── motoko/              # Main package
│   ├── agent.py         # Agent class
│   ├── types.py         # Core types
│   ├── models/          # Model implementations
│   │   ├── base.py      # BaseModel
│   │   ├── anthropic.py # Anthropic Claude
│   │   ├── gemini.py    # Google Gemini
│   │   └── factory.py   # Model factory
│   ├── tools/           # Tool implementations
│   │   ├── base.py      # BaseTool
│   │   ├── files.py     # File tools
│   │   ├── web.py       # Web tools
│   │   ├── git.py       # Git tools
│   │   └── bash.py      # Bash tool
│   ├── skills/          # Skills framework
│   │   ├── skill.py     # Skill class
│   │   └── loader.py    # SkillLoader
│   └── streaming.py     # SSE utilities
├── skills/              # Example skill definitions
│   ├── code-review.md
│   ├── summarize-file.md
│   ├── search-and-explain.md
│   └── refactor-suggestions.md
├── tests/               # Test suite
├── examples/            # Usage examples
├── SPEC.md              # Technical specification
├── EPICS.md             # Development epics
└── README.md            # This file
```

## Roadmap

### Phase 1: Foundation ✅
- [x] Epic 1: Package structure and base classes
- [x] Epic 2: Model abstraction layer
- [x] Epic 3: Tool system
- [x] Epic 4: Agent loop
- [x] Epic 5: Skills framework
- [x] Epic 6: Streaming & real-time updates
- [x] Epic 7: Role management

### Phase 2: Testing & Integration
- [ ] Epic 9: Testing & QA ← **Next**

### Phase 4: Production
- [ ] Epic 8: Integration with existing apps
- [ ] Epic 9: Testing & QA (performance, CI/CD)

**Note**: Epic 9 (Testing) runs in parallel with development, with checkpoints after each phase.

See [EPICS.md](EPICS.md) for detailed breakdown.

## Use Cases

**motoko** is designed for applications that need:

- **Domain-specific assistants** with specialized roles
- **Multi-model support** to leverage different LLM strengths
- **Tool-based interactions** with files, web, git, etc.
- **Role-based workflows** with context switching
- **Production deployments** requiring model flexibility

### Current Applications

Three production apps will use motoko:

1. **coyote** - Artist management with role-based conversations
2. **escuela** - Educational learning with teaching roles
3. **project-management** - PM and task tracking

## Philosophy

- **Model Agnostic**: Don't lock into one provider
- **Role Focused**: Domain expertise through role context
- **Tool Powered**: Capabilities through tool execution
- **Markdown First**: Simple, readable, version-controlled data
- **Pure Python**: Direct control and maintainability

## Inspiration

- **Claude Code**: Agent loop and tool patterns
- **Ghost in the Shell**: Role flexibility and system integration
- **Unix Philosophy**: Do one thing well, compose simply

## License

MIT

## Contributing

This is currently a personal project. Contributions welcome once core implementation is complete.

## Name Origin

**Major Motoko Kusanagi** is the protagonist of *Ghost in the Shell*. She:

- Dives into different systems and contexts (like switching roles)
- Questions identity and consciousness (like multi-role agents)
- Interfaces seamlessly with technology (like tool execution)
- Adapts to any situation (like model flexibility)

A fitting namesake for an agent that embodies these qualities.

---

**Status**: Epic 1 Complete
**Version**: 0.1.0
**Last Updated**: 2025-01-18
