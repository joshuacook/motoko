# Major

Chat agent using Claude Agent SDK with session persistence.

## Overview

Major is a thin wrapper around the Claude Agent SDK that:

- Uses SDK session files as source of truth (via `resume=session_id`)
- Passes through SDK events with minimal transformation
- Handles AskUserQuestion via `can_use_tool` callback
- Manages MCP server configuration and skills syncing

## Usage

```python
from major import MajorAgent, MajorConfig

config = MajorConfig(
    workspace_root="/opt/workspaces",
    platform_config_path="/opt/claude-code-apps/platform",
)

agent = MajorAgent(config=config)

async for event in agent.send_message(
    message="Hello",
    workspace_path="/opt/workspaces/user/workspace",
    session_id=None,  # Start new session, or pass existing ID to resume
):
    # Handle SDK events
    session_id = agent.get_session_id_from_init(event)
    if session_id:
        # Store session_id for future resume
        pass
```

## Architecture

SDK session files (`~/.claude/projects/<path>/<session_id>.jsonl`) are the source of truth for conversation history. Firestore messages are a display cache that can be rebuilt from session files.

See MAJOR.md in the motoko root for full architecture documentation.
