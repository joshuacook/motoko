# motoko - Development Epics

Breaking down motoko development into epics (large deliverable chunks of work).

---

## Epic 1: Foundation & Package Structure ✅ **COMPLETE**

**Goal**: Create the basic package structure and core abstractions.

**Status**: Complete (pending test verification - see TODO.md)

**Deliverables**:
- [x] Package directory structure
- [x] `pyproject.toml` with dependencies
- [x] Base classes and interfaces
- [x] Core types and data structures
- [x] Development environment setup

**Tasks**:
1. ✅ Create package layout (`motoko/`, `tests/`, `examples/`)
2. ✅ Set up `pyproject.toml` with:
   - Dependencies: anthropic, google-generativeai, httpx, etc.
   - Package metadata
   - Build configuration
3. ✅ Define `BaseModel` abstract class
4. ✅ Define `BaseTool` abstract class
5. ✅ Define `ToolResult` class with verbosity support
6. ✅ Define core types (Message, ToolCall, ToolDefinition)
7. ✅ Set up pytest and basic test structure
8. ✅ Create README with project overview

**Success Criteria**:
- ✅ Package installs with `pip install -e .` (verified: imports successfully)
- ⏳ Tests can be run with `pytest` (blocked by network - see TODO.md)
- ✅ Base classes define clear contracts
- ✅ Type hints throughout (Python 3.9+ compatible)

**Completed**: 2025-01-18

---

## Epic 2: Model Abstraction Layer ✅ **COMPLETE**

**Goal**: Unified interface to multiple LLM providers.

**Status**: Complete (tests in Epic 9)

**Deliverables**:
- [x] Model abstraction that hides provider differences
- [x] Anthropic Claude implementation
- [x] Google Gemini implementation
- [x] Model factory/registry
- [x] Streaming support for all models

**Tasks**:
1. ✅ Implement `BaseModel` interface (done in Epic 1)
2. ✅ Implement `AnthropicModel`:
   - Regular chat with Anthropic SDK
   - Streaming chat
   - Tool calling (function calling API)
   - Error handling
3. ✅ Implement `GeminiModel`:
   - Regular chat with Google SDK
   - Streaming chat
   - Tool calling (Gemini function calling)
   - Error handling
4. ✅ Create `ModelFactory`:
   - Auto-detect provider from model name
   - Convenience methods (`create_anthropic`, `create_gemini`)
   - Handle API keys from environment
5. ✅ Create unified response format (done in Epic 1)
6. ⏳ Write tests (moved to Epic 9)

**Success Criteria**:
- ✅ Can swap models with single string change (via ModelFactory)
- ✅ Streaming works consistently across providers
- ✅ Tool calling format is abstracted
- ✅ Error handling is consistent
- ✅ Example code demonstrates usage

**Completed**: 2025-01-18

---

## Epic 3: Tool System ✅ **COMPLETE**

**Goal**: Complete tool ecosystem matching Claude Code's capabilities.

**Status**: Complete (tests in Epic 9)

**Deliverables**:
- [x] File tools (Read, Write, Edit, Glob, Grep)
- [x] Web tools (WebSearch, WebFetch)
- [x] Git tools (Status, Diff, Commit)
- [x] Bash tool (command execution)
- [x] Tool exports and examples

**Tasks**:

### File Tools
1. `ReadFileTool`: Read file contents with offset/limit
2. `WriteFileTool`: Write/overwrite files
3. `EditFileTool`: Edit file with exact string replacement
4. `GlobTool`: Pattern matching for files
5. `GrepTool`: Search file contents with regex

### Web Tools
6. `WebSearchTool`: Web search with query
7. `WebFetchTool`: Fetch and parse web pages

### Git Tools
8. `GitStatusTool`: Get git status
9. `GitDiffTool`: Show git diff
10. `GitCommitTool`: Create commits
11. `GitPushTool`: Push to remote
12. `GitBranchTool`: Branch operations

### Bash Tool
13. `BashTool`: Execute bash commands
14. Add sandboxing/security considerations
15. Timeout handling

### Tool Registry
16. `ToolRegistry`: Register and discover tools
17. Tool schemas generation
18. Tool validation

**Success Criteria**:
- Each tool has comprehensive schema
- Tools return `ToolResult` with proper verbosity
- Error handling for all failure cases
- Tools match Claude Code behavior
- Security considerations documented

---

## Epic 4: Agent Loop ✅ **COMPLETE**

**Goal**: Core agent execution loop with tool calling.

**Status**: Complete (streaming in Epic 6)

**Deliverables**:
- [x] Agent class with conversation loop
- [x] Tool execution orchestration
- [x] Sequential tool execution (parallel in future)
- [x] Message history management
- [x] Error handling and recovery

**Tasks**:
1. Implement `Agent` class:
   - `__init__(model, tools, workspace)`
   - `chat(message, system_prompt, session_id)`
   - `stream(message, system_prompt, session_id)`
2. Implement agent loop:
   - While loop for tool iteration
   - Tool call detection
   - Tool execution
   - Result formatting
   - Continuation logic
3. Implement message management:
   - Build conversation history
   - Add assistant messages with tool calls
   - Add user messages with tool results
   - Context window management
4. Implement parallel tool execution:
   - Detect independent tools
   - Execute concurrently with asyncio
   - Collect results
5. Implement error handling:
   - Tool execution errors
   - Model API errors
   - Timeout handling
   - Graceful degradation
6. Add verbosity control:
   - Global agent verbosity setting
   - Dynamic adjustment based on context
7. Write comprehensive tests:
   - Single tool calls
   - Multiple tool calls
   - Error scenarios
   - Long conversations

**Success Criteria**:
- Agent successfully executes tool loops
- Parallel execution works correctly
- Errors are handled gracefully
- Message history is well-formed
- Works with both Anthropic and Gemini

---

## Epic 5: Skills Framework ✅ **COMPLETE**

**Goal**: Replicate Claude Code's skill system.

**Status**: Complete

**Deliverables**:
- [x] Skill definition format
- [x] Skill loader
- [x] Skill execution in agent
- [x] Standard skills library

**Tasks**:
1. ✅ Study Claude Code's skill format:
   - How are skills defined? → Markdown with YAML frontmatter
   - What's the invocation mechanism? → Direct method call on agent
   - How do they integrate with tools? → Skills declare tool requirements
2. ✅ Define skill specification:
   - Skill metadata (name, description) → YAML frontmatter
   - Skill prompts/instructions → Markdown content with parameter substitution
   - Tool permissions → Listed in frontmatter, validated on invocation
3. ✅ Implement `SkillLoader`:
   - Load skills from directory → Recursive .md file discovery
   - Parse skill definitions → YAML + markdown parsing
   - Validate skills → Tool requirement validation
4. ✅ Implement `Skill` class:
   - Skill metadata → Dataclass with all metadata fields
   - Skill execution → format_prompt() for parameter substitution
   - Tool access → Validated by SkillLoader
5. ✅ Integrate skills with Agent:
   - Skill invocation → invoke_skill() and invoke_skill_stream()
   - Skill context → Uses agent's existing system prompt
   - Skill-specific tool sets → Tool validation before execution
6. ✅ Create standard skills:
   - code-review.md → Review code for issues and best practices
   - summarize-file.md → Summarize file contents
   - search-and-explain.md → Search and explain code patterns
   - refactor-suggestions.md → Suggest refactoring improvements
7. ✅ Write skill examples and documentation → examples/skills_usage.py

**Success Criteria**:
- ✅ Skills can be loaded and invoked
- ✅ Skills match Claude Code behavior (markdown + YAML format)
- ✅ Custom skills can be easily created (simple .md file format)
- ✅ Skills are well-documented (README, examples, docstrings)

**Completed**: 2025-01-18

---

## Epic 6: Streaming & Real-time Updates ✅ **COMPLETE**

**Goal**: Streaming responses and progressive feedback.

**Status**: Complete

**Deliverables**:
- [x] Streaming response handling
- [x] SSE integration for web apps
- [x] Progressive tool execution feedback
- [x] Unified streaming interface

**Tasks**:
1. Implement streaming in Agent:
   - Async generator for streaming
   - Yield text chunks as they arrive
   - Yield tool execution notifications
2. Create streaming event types:
   - `TextChunk`: Incremental text
   - `ToolStart`: Tool execution starting
   - `ToolEnd`: Tool execution complete
   - `Error`: Error occurred
   - `Done`: Response complete
3. Implement SSE formatting:
   - Convert events to SSE format
   - Proper event structure
4. Add streaming to both model implementations:
   - Anthropic streaming
   - Gemini streaming
5. Handle streaming with tool calls:
   - Stream text before tools
   - Notify when tools start
   - Stream continued text after tools
6. Write streaming examples:
   - FastAPI integration
   - SSE endpoint
7. Test streaming thoroughly:
   - Large responses
   - Multiple tools
   - Error scenarios

**Success Criteria**:
- Streaming works consistently across models
- Tool execution provides feedback
- SSE integration is straightforward
- No blocking during long operations

---

## Epic 7: Role Management ✅ **COMPLETE**

**Goal**: Dynamic role switching and multi-role support.

**Status**: Complete

**Deliverables**:
- [x] Role switching mid-conversation
- [x] Multiple roles in one session
- [x] Role-specific tool access
- [x] Role state management

**Tasks**:
1. ✅ Design role switching API:
   - `agent.switch_role(new_system_prompt, role_name)` → Implemented
   - Preserve conversation context → Message history maintained
   - Clear role transition → Role history tracking added
2. ✅ Design multi-role API:
   - `agent.add_role(role_name, system_prompt, tools)` → Implemented
   - `agent.chat_as(role_name, message)` → Implemented with state restoration
   - `agent.stream_as(role_name, message)` → Streaming support added
   - Role coordination → Save/restore pattern for clean switching
3. ✅ Implement role state:
   - Track current role(s) → `current_role` field
   - Role history → `role_history` list of (name, prompt) tuples
   - Role-specific context → `roles` dictionary with Role objects
4. ✅ Implement role-specific tools:
   - Different tool sets per role → `role.tools` list of tool names
   - Tool access validation → Filter `_tool_registry` per role
   - Permission checking → Validate before chat_as/stream_as
5. ✅ Add role to message metadata:
   - Track which role said what → `message.role_name` field
   - Role attribution in history → Tagged in chat_as/stream_as
6. ✅ Handle role transitions:
   - Clean context switching → Save/restore original state in try/finally
   - Preserve necessary context → Conversation history maintained
   - Clear boundaries → Tool registry restored after role execution
7. ✅ Write examples → examples/role_management.py (400+ lines, 7 examples):
   - Basic role switching
   - Multi-role collaboration
   - Role-specific tool access
   - Streaming with roles
   - Role state tracking
   - Real-world artist management workflow
   - Complete API demonstration

**Success Criteria**:
- ✅ Roles can switch seamlessly (switch_role, chat_as, stream_as)
- ✅ Multiple roles can participate (add_role, role registry)
- ✅ Tool access is correctly scoped (per-role tool filtering)
- ✅ Role context is maintained (role_history, current_role tracking)

**Completed**: 2025-01-18

---

## Epic 8: Integration & Testing

**Goal**: Integrate with existing apps and comprehensive testing.

**Deliverables**:
- [ ] Integration with coyote
- [ ] Integration with escuela
- [ ] Integration with project-management
- [ ] End-to-end testing
- [ ] Performance benchmarks
- [ ] Documentation

**Tasks**:

### Coyote Integration
1. Replace current agent with motoko
2. Update role loading to work with motoko
3. Test all artist management workflows
4. Verify streaming works
5. Deploy and validate

### Escuela Integration
6. Replace current agent with motoko
7. Update role loading to work with motoko
8. Test all educational workflows
9. Verify streaming works
10. Deploy and validate

### Project Management Integration
11. Replace current agent with motoko
12. Update role loading to work with motoko
13. Test all PM workflows
14. Verify streaming works
15. Deploy and validate

### Testing
16. Write end-to-end tests for each app
17. Write integration tests
18. Write performance benchmarks
19. Test with both Claude and Gemini
20. Load testing

### Documentation
21. API documentation
22. Integration guide
23. Examples and tutorials
24. Migration guide from current implementation
25. Troubleshooting guide

**Success Criteria**:
- All three apps use motoko successfully
- Can swap models in production
- Performance is acceptable
- Documentation is comprehensive
- Code is maintainable

---

## Epic 9: Testing & Quality Assurance

**Goal**: Comprehensive testing infrastructure and validation.

**Deliverables**:
- [ ] All existing tests running and passing
- [ ] Test coverage reporting
- [ ] CI/CD pipeline
- [ ] Performance benchmarks
- [ ] Testing documentation

**Tasks**:

### Environment Setup
1. Install dev dependencies with uv
2. Verify pytest runs successfully
3. Set up coverage reporting (pytest-cov)
4. Configure mypy for type checking
5. Configure ruff for linting

### Unit Tests
6. Run and verify Epic 1 tests (test_types.py, test_agent.py)
7. Write tests for Epic 2 (model implementations):
   - **AnthropicModel**: chat, stream, format_tools, format_messages, parse_response
   - **GeminiModel**: chat, stream, format_tools, format_messages, parse_response
   - **ModelFactory**: create, auto-detection, error handling
   - **Requirements**: ANTHROPIC_API_KEY and GOOGLE_API_KEY env vars
   - **Mock tests**: Use mocked responses for unit tests (no API calls)
   - **Integration tests**: Real API calls (separate test file, slower)
   - **Test files**:
     - `tests/test_models/test_anthropic.py` (unit + integration)
     - `tests/test_models/test_gemini.py` (unit + integration)
     - `tests/test_models/test_factory.py` (unit)
8. Write tests for Epic 3 (tool implementations)
9. Write tests for Epic 4 (agent loop)
10. Achieve >80% code coverage

### Integration Tests
11. Test model switching (Claude ↔ Gemini)
12. Test tool execution across models
13. Test agent loop with real API calls
14. Test streaming across providers
15. Test role switching scenarios

### Performance Testing
16. Benchmark response times
17. Benchmark streaming performance
18. Measure context window usage
19. Test parallel tool execution
20. Memory usage profiling

### CI/CD
21. Set up GitHub Actions workflow
22. Run tests on push/PR
23. Run linting and type checking
24. Generate coverage reports
25. Automated release process

### Quality Gates
26. All tests pass before merge
27. Coverage >80% required
28. Type checking passes (mypy)
29. Linting passes (ruff)
30. No security vulnerabilities

**Success Criteria**:
- All tests passing consistently
- Coverage >80% across all modules
- CI/CD pipeline running on GitHub
- Performance benchmarks documented
- Clear testing documentation

**Testing Strategy**:

```python
# Unit tests - fast, isolated
tests/
├── test_types.py          # Core types
├── test_agent.py          # Agent class
├── test_models/
│   ├── test_anthropic.py  # Anthropic model
│   └── test_gemini.py     # Gemini model
└── test_tools/
    ├── test_files.py      # File tools
    ├── test_web.py        # Web tools
    ├── test_git.py        # Git tools
    └── test_bash.py       # Bash tools

# Integration tests - slower, real APIs
tests/integration/
├── test_model_switching.py
├── test_tool_execution.py
├── test_streaming.py
└── test_role_management.py

# Performance tests
tests/performance/
├── test_response_times.py
├── test_streaming_perf.py
└── test_context_usage.py
```

**Testing Commands**:
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=motoko --cov-report=html --cov-report=term

# Run specific test file
uv run pytest tests/test_agent.py -v

# Run integration tests (slower)
uv run pytest tests/integration/ -v

# Type checking
uv run mypy motoko

# Linting
uv run ruff check motoko

# Format code
uv run ruff format motoko
```

**Notes**:
- Can run in parallel with development epics
- Should be revisited after each epic completion
- Integration tests require API keys (ANTHROPIC_API_KEY, GOOGLE_API_KEY)
- Performance tests should establish baselines

---

## Epic Sequencing

**Phase 1: Foundation** (Epics 1-2)
- Epic 1: Package structure and base classes ✅
- Epic 2: Model abstraction layer
- Epic 9: Testing & QA (initial setup)

**Phase 2: Core Functionality** (Epics 3-4)
- Epic 3: Tool system
- Epic 4: Agent loop
- Epic 9: Testing & QA (unit tests)

**Phase 3: Advanced Features** (Epics 5-7)
- Epic 5: Skills framework
- Epic 6: Streaming
- Epic 7: Role management
- Epic 9: Testing & QA (integration tests)

**Phase 4: Production** (Epic 8)
- Epic 8: Integration with apps
- Epic 9: Testing & QA (performance tests, CI/CD)

---

## Success Metrics

**Technical**:
- [ ] Package is pip installable
- [ ] All tests pass
- [ ] Type checking passes (mypy)
- [ ] Linting passes (ruff)
- [ ] Code coverage > 80%

**Functional**:
- [ ] Works with Claude (Sonnet, Opus, Haiku)
- [ ] Works with Gemini (3.0, 2.0)
- [ ] All core tools implemented
- [ ] Streaming works reliably
- [ ] Role switching works

**Integration**:
- [ ] coyote uses motoko
- [ ] escuela uses motoko
- [ ] project-management uses motoko
- [ ] No regressions in functionality
- [ ] Performance is acceptable

**Documentation**:
- [ ] README is comprehensive
- [ ] API docs are complete
- [ ] Examples are clear
- [ ] Migration guide exists

---

## Epic 10: CLI Interface

**Goal**: Interactive command-line interface for using motoko agents.

**Status**: Planned

**Deliverables**:
- [ ] Interactive chat CLI
- [ ] Model and tool configuration
- [ ] Role management from CLI
- [ ] Conversation history management
- [ ] Configuration file support
- [ ] Streaming output display
- [ ] Skills invocation from CLI

**Tasks**:

### Core CLI
1. Create `motoko` CLI entrypoint
2. Implement argument parsing (click or typer)
3. Add version command
4. Add help documentation

### Interactive Chat Mode
5. Implement `motoko chat` command:
   - Interactive REPL-style chat
   - Multi-line input support
   - Streaming output with rich formatting
   - Exit commands (/exit, /quit)
6. Add special commands:
   - `/model <name>` - Switch model
   - `/role <name>` - Switch role
   - `/tools` - List available tools
   - `/history` - Show conversation history
   - `/save <file>` - Save conversation
   - `/load <file>` - Load conversation
   - `/clear` - Clear conversation
   - `/help` - Show CLI help

### Model Configuration
7. Support `--model` flag (default: claude-sonnet-4-5-20250929)
8. Support `--provider` flag (anthropic/gemini)
9. Auto-detect from model name
10. Configuration for temperature, top_p, etc.

### Tool Management
11. Support `--tools` flag to enable specific tools
12. Support `--all-tools` to enable all tools
13. Support `--workspace` for file tool workspace
14. Display tool calls in real-time

### Role Management
15. Support `--role` flag to load initial role
16. Support `--role-file` to load role from file
17. Support role switching during chat
18. Display current role in prompt

### History & Sessions
19. Auto-save conversations to ~/.motoko/history/
20. Support `--session <name>` to resume sessions
21. Support `--no-history` to disable saving
22. Export to different formats (json, markdown)

### Configuration
23. Support config file at ~/.motoko/config.yaml
24. CLI flags override config file
25. Environment variables for API keys
26. Example config file in docs/

### Skills Integration
27. Support `--skill <name>` to invoke skill
28. Support `--skills-dir` for custom skills
29. List available skills
30. Skill parameter passing from CLI

### Output Formatting
31. Use rich library for beautiful output
32. Syntax highlighting for code blocks
33. Progress indicators for tool execution
34. Color-coded messages (user/assistant/tool)
35. Stream text as it's generated

### Testing
36. Test CLI commands work correctly
37. Test streaming output
38. Test configuration loading
39. Test history save/load
40. Integration tests with real models

**Success Criteria**:
- Can start interactive chat with `motoko chat`
- Can switch models and roles mid-conversation
- Tools execute and results display nicely
- Conversations can be saved and resumed
- Configuration is intuitive
- Output is beautiful and readable

**Example Usage**:
```bash
# Basic interactive chat
motoko chat

# Use specific model
motoko chat --model gemini-3-pro-preview

# Enable file tools with workspace
motoko chat --tools read,write,glob --workspace ~/projects

# Load a role
motoko chat --role architect --role-file ~/.motoko/roles/architect.md

# Invoke a skill
motoko chat --skill code-review --file src/agent.py

# Resume a previous session
motoko chat --session my-project-2025-01-18

# One-shot question (non-interactive)
motoko ask "What is 2+2?"

# List available models
motoko models list

# List available skills
motoko skills list

# Show current configuration
motoko config show
```

**CLI Structure**:
```
motoko/
├── cli/
│   ├── __init__.py
│   ├── main.py           # CLI entrypoint
│   ├── chat.py           # Interactive chat
│   ├── config.py         # Configuration management
│   ├── history.py        # History management
│   ├── formatting.py     # Output formatting with rich
│   └── commands.py       # Special commands (/model, /role, etc.)
└── __main__.py           # python -m motoko

pyproject.toml:
[project.scripts]
motoko = "motoko.cli.main:cli"
```

**Dependencies**:
- `click` or `typer` - CLI framework
- `rich` - Beautiful terminal output
- `prompt_toolkit` - Interactive input with multi-line, history
- `pyyaml` - Config file parsing (already have)

**Completed**: TBD

---

**Created**: 2025-01-18
**Last Updated**: 2025-01-18
