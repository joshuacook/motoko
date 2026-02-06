"""Local session metadata management.

Manages session metadata in local JSON files, separate from SDK session JSONL files.
SDK JSONL files are the source of truth for conversation history.
Local metadata files store UI-specific data (title, archived, project, etc).

Storage structure:
    /opt/workspaces/{username}/{workspace}/.chelle/sessions.json

    {
        "session_id_1": {"title": "...", "archived": false, "project_id": null, ...},
        "session_id_2": {"title": "...", "archived": false, "project_id": null, ...}
    }
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionMetadata:
    """Metadata for a session (stored in local JSON, not SDK JSONL)."""
    session_id: str
    workspace_path: str
    title: str | None = None
    archived: bool = False
    project_id: str | None = None
    entity_type: str | None = None  # For sessions linked to entities (e.g., "handoffs")
    entity_id: str | None = None    # For sessions linked to entities (e.g., "handoff-foo")
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionMessage:
    """A message extracted from SDK JSONL."""
    role: str  # 'user' | 'assistant' | 'tool_use' | 'tool_result'
    content: str
    tool_name: str | None = None
    created_at: str | None = None


class SessionManager:
    """Manages local session metadata and reads SDK JSONL files."""

    def __init__(self, workspace_root: str = "/opt/workspaces"):
        self.workspace_root = workspace_root

    def _get_metadata_path(self, workspace_path: str) -> Path:
        """Get path to sessions.json for a workspace."""
        return Path(workspace_path) / ".chelle" / "sessions.json"

    def _get_sdk_sessions_dir(self, workspace_path: str) -> Path:
        """Get SDK sessions directory for a workspace.

        SDK stores sessions at: ~/.claude/projects/{workspace_path_encoded}/
        The workspace path is encoded (/ -> -, _ -> -)
        """
        # Encode workspace path for SDK directory structure
        # /opt/workspaces/josh/main -> -opt-workspaces-josh-main
        # /opt/workspaces/user_123/main -> -opt-workspaces-user-123-main
        encoded_path = workspace_path.replace('/', '-').replace('_', '-')
        return Path.home() / ".claude" / "projects" / encoded_path

    def _load_metadata(self, workspace_path: str) -> dict[str, dict]:
        """Load all session metadata for a workspace."""
        path = self._get_metadata_path(workspace_path)
        if not path.exists():
            return {}
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_metadata(self, workspace_path: str, metadata: dict[str, dict]) -> None:
        """Save all session metadata for a workspace."""
        path = self._get_metadata_path(workspace_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def list_sessions(
        self,
        workspace_path: str,
        include_archived: bool = False,
        entity_type: str | None = None,  # None = all, "null" = only sessions without entity
    ) -> list[SessionMetadata]:
        """List all sessions for a workspace.

        Merges SDK session files with local metadata.
        Sessions exist if they have a JSONL file, metadata is optional.

        Args:
            workspace_path: Path to the workspace
            include_archived: Whether to include archived sessions
            entity_type: Filter by entity type. "null" means only sessions without entity.
        """
        sessions = []
        metadata = self._load_metadata(workspace_path)
        sdk_dir = self._get_sdk_sessions_dir(workspace_path)

        # Find all SDK session files
        session_ids = set()
        if sdk_dir.exists():
            for jsonl_file in sdk_dir.glob("*.jsonl"):
                # Skip agent sidechain sessions (agent-*)
                if jsonl_file.stem.startswith('agent-'):
                    continue
                # Skip empty files and handle broken symlinks
                try:
                    if jsonl_file.stat().st_size == 0:
                        continue
                except FileNotFoundError:
                    # Broken symlink - remove it and skip
                    try:
                        jsonl_file.unlink()
                    except OSError:
                        pass
                    continue
                session_ids.add(jsonl_file.stem)

        # Also include any sessions in metadata (in case JSONL was deleted)
        # But filter out agent- prefixed ones
        for sid in metadata.keys():
            if not sid.startswith('agent-'):
                session_ids.add(sid)

        for session_id in session_ids:
            meta = metadata.get(session_id, {})

            # Skip archived unless requested
            if meta.get('archived', False) and not include_archived:
                continue

            # Filter by entity_type if specified
            session_entity_type = meta.get('entity_type')
            if entity_type is not None:
                if entity_type == "null":
                    # Only sessions without entity
                    if session_entity_type is not None:
                        continue
                else:
                    # Only sessions with matching entity type
                    if session_entity_type != entity_type:
                        continue

            session = SessionMetadata(
                session_id=session_id,
                workspace_path=workspace_path,
                title=meta.get('title'),
                archived=meta.get('archived', False),
                project_id=meta.get('project_id'),
                entity_type=session_entity_type,
                entity_id=meta.get('entity_id'),
                created_at=meta.get('created_at', datetime.utcnow().isoformat()),
                updated_at=meta.get('updated_at', datetime.utcnow().isoformat()),
            )
            sessions.append(session)

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def get_session(self, workspace_path: str, session_id: str) -> SessionMetadata | None:
        """Get metadata for a specific session."""
        metadata = self._load_metadata(workspace_path)
        meta = metadata.get(session_id)

        # Check if SDK session file exists
        sdk_dir = self._get_sdk_sessions_dir(workspace_path)
        jsonl_path = sdk_dir / f"{session_id}.jsonl"

        if not jsonl_path.exists() and not meta:
            return None

        return SessionMetadata(
            session_id=session_id,
            workspace_path=workspace_path,
            title=meta.get('title') if meta else None,
            archived=meta.get('archived', False) if meta else False,
            project_id=meta.get('project_id') if meta else None,
            entity_type=meta.get('entity_type') if meta else None,
            entity_id=meta.get('entity_id') if meta else None,
            created_at=meta.get('created_at', datetime.utcnow().isoformat()) if meta else datetime.utcnow().isoformat(),
            updated_at=meta.get('updated_at', datetime.utcnow().isoformat()) if meta else datetime.utcnow().isoformat(),
        )

    def update_session(
        self,
        workspace_path: str,
        session_id: str,
        title: str | None = None,
        archived: bool | None = None,
        project_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> SessionMetadata:
        """Update session metadata."""
        metadata = self._load_metadata(workspace_path)

        if session_id not in metadata:
            metadata[session_id] = {
                'created_at': datetime.utcnow().isoformat(),
            }

        if title is not None:
            metadata[session_id]['title'] = title
        if archived is not None:
            metadata[session_id]['archived'] = archived
        if project_id is not None:
            metadata[session_id]['project_id'] = project_id
        if entity_type is not None:
            metadata[session_id]['entity_type'] = entity_type
        if entity_id is not None:
            metadata[session_id]['entity_id'] = entity_id

        metadata[session_id]['updated_at'] = datetime.utcnow().isoformat()
        metadata[session_id]['workspace_path'] = workspace_path

        self._save_metadata(workspace_path, metadata)

        return self.get_session(workspace_path, session_id)

    def create_session(self, workspace_path: str, session_id: str) -> SessionMetadata:
        """Create metadata entry for a new session."""
        return self.update_session(workspace_path, session_id)

    def delete_session(self, workspace_path: str, session_id: str) -> bool:
        """Delete session metadata and optionally the JSONL file."""
        # Remove from metadata
        metadata = self._load_metadata(workspace_path)
        if session_id in metadata:
            del metadata[session_id]
            self._save_metadata(workspace_path, metadata)

        # Delete JSONL file (or broken symlink)
        sdk_dir = self._get_sdk_sessions_dir(workspace_path)
        jsonl_path = sdk_dir / f"{session_id}.jsonl"
        # exists() returns False for broken symlinks, so also check is_symlink()
        if jsonl_path.exists() or jsonl_path.is_symlink():
            jsonl_path.unlink()
            return True

        return session_id in metadata

    def get_history(self, workspace_path: str, session_id: str) -> list[SessionMessage]:
        """Parse SDK JSONL file to extract message history.

        JSONL format (one JSON object per line):
        - User messages: {"type": "human", "message": {"content": [{"type": "text", "text": "..."}]}}
        - Assistant messages: {"type": "assistant", "message": {"content": [...]}}
        - Tool use: content blocks with type "tool_use"
        - Tool result: content blocks with type "tool_result"
        """
        sdk_dir = self._get_sdk_sessions_dir(workspace_path)
        jsonl_path = sdk_dir / f"{session_id}.jsonl"

        if not jsonl_path.exists():
            return []

        messages = []

        try:
            with open(jsonl_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg_type = entry.get('type')
                    message = entry.get('message', {})
                    content = message.get('content', [])

                    # Skip meta messages (skill prompts, system injections)
                    if entry.get('isMeta'):
                        continue

                    # Handle user messages (SDK uses "user", older format used "human")
                    if msg_type in ('human', 'user'):
                        # Content can be a string or array of blocks
                        if isinstance(content, str):
                            if content.strip():
                                messages.append(SessionMessage(
                                    role='user',
                                    content=content,
                                ))
                        else:
                            # Array of content blocks
                            text_parts = []
                            for block in content:
                                if isinstance(block, dict) and block.get('type') == 'text':
                                    text_parts.append(block.get('text', ''))
                                elif isinstance(block, str):
                                    text_parts.append(block)

                            if text_parts:
                                messages.append(SessionMessage(
                                    role='user',
                                    content='\n'.join(text_parts),
                                ))

                    elif msg_type == 'assistant':
                        # Extract assistant response and tool use
                        text_parts = []

                        # Content can be array of blocks
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict):
                                    block_type = block.get('type')

                                    if block_type == 'text':
                                        text_parts.append(block.get('text', ''))

                                    elif block_type == 'tool_use':
                                        # Add tool use as separate message
                                        messages.append(SessionMessage(
                                            role='tool_use',
                                            content=json.dumps(block.get('input', {})),
                                            tool_name=block.get('name'),
                                        ))

                                    elif block_type == 'tool_result':
                                        # Tool result
                                        result_content = block.get('content', '')
                                        if isinstance(result_content, list):
                                            result_content = '\n'.join(
                                                b.get('text', str(b)) if isinstance(b, dict) else str(b)
                                                for b in result_content
                                            )
                                        messages.append(SessionMessage(
                                            role='tool_result',
                                            content=str(result_content)[:1000],  # Truncate
                                        ))

                        if text_parts:
                            messages.append(SessionMessage(
                                role='assistant',
                                content='\n'.join(text_parts),
                            ))

        except IOError:
            return []

        # Consolidate assistant messages within each turn (matches streaming behavior)
        # During streaming, multi-turn tool interactions accumulate all text into one message
        # When loading history, we consolidate all assistant text between user messages
        consolidated = []
        pending_assistant_texts = []

        for msg in messages:
            if msg.role == 'user':
                # Flush pending assistant texts before adding user message
                if pending_assistant_texts:
                    consolidated.append(SessionMessage(
                        role='assistant',
                        content='\n\n'.join(pending_assistant_texts),
                    ))
                    pending_assistant_texts = []
                consolidated.append(msg)
            elif msg.role == 'assistant':
                # Accumulate assistant text
                pending_assistant_texts.append(msg.content)
            else:
                # tool_use/tool_result - add as-is (will be filtered by frontend)
                consolidated.append(msg)

        # Flush any remaining assistant texts
        if pending_assistant_texts:
            consolidated.append(SessionMessage(
                role='assistant',
                content='\n\n'.join(pending_assistant_texts),
            ))

        return consolidated

    def get_last_assistant_message(self, workspace_path: str, session_id: str) -> str | None:
        """Get the last assistant message from a session (for title generation)."""
        messages = self.get_history(workspace_path, session_id)
        for msg in reversed(messages):
            if msg.role == 'assistant':
                return msg.content
        return None


# Global instance
session_manager = SessionManager()
