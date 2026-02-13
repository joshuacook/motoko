"""Major chat agent - Claude Agent SDK wrapper for interactive conversations."""

from .config import MajorConfig
from .sessions import SessionManager, SessionMetadata, SessionMessage, session_manager


# Lazy import for MajorAgent to avoid pulling in claude_agent_sdk
# when only major.librarian is needed (e.g., from batou's virtualenv)
def __getattr__(name):
    if name == "MajorAgent":
        from .agent import MajorAgent
        return MajorAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "MajorAgent",
    "MajorConfig",
    "SessionManager",
    "SessionMetadata",
    "SessionMessage",
    "session_manager",
]
