"""HTTP server for Major chat agent."""

import asyncio
import os
import json
import re
import subprocess
import uuid
import yaml
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .library import LibraryManager, LibraryFile as LibraryFileModel, get_content_type, is_supported_file
from .organize import WorkspaceOrganizer

from .agent import MajorAgent
from .config import MajorConfig
from .sessions import session_manager, SessionMetadata


# ============== Event Bus for Slack-like async messaging ==============

@dataclass
class SessionEvent:
    """Event that can be sent to clients."""
    type: str  # history, user_message, text_delta, tool_use, assistant_message, done, error
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SessionEventBus:
    """Manages event streams for sessions.

    Supports multiple subscribers per session and message queuing.
    """

    def __init__(self):
        # Event queues for each subscriber (session_id -> list of queues)
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        # Message queue for each session (messages waiting to be processed)
        self._message_queues: dict[str, asyncio.Queue] = {}
        # Currently processing flag per session
        self._processing: dict[str, bool] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """Subscribe to events for a session. Returns a queue that receives events."""
        async with self._lock:
            queue: asyncio.Queue = asyncio.Queue()
            self._subscribers[session_id].append(queue)
            return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """Unsubscribe from session events."""
        async with self._lock:
            if session_id in self._subscribers:
                try:
                    self._subscribers[session_id].remove(queue)
                except ValueError:
                    pass
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]

    async def publish(self, session_id: str, event: SessionEvent):
        """Publish event to all subscribers of a session."""
        async with self._lock:
            subscribers = self._subscribers.get(session_id, [])

        for queue in subscribers:
            try:
                await queue.put(event)
            except Exception:
                pass  # Subscriber may have disconnected

    async def queue_message(self, session_id: str, message: str) -> bool:
        """Queue a user message for processing. Returns True if queued."""
        async with self._lock:
            if session_id not in self._message_queues:
                self._message_queues[session_id] = asyncio.Queue()

            await self._message_queues[session_id].put(message)
            return True

    async def get_next_message(self, session_id: str) -> str | None:
        """Get next message from queue, or None if empty."""
        async with self._lock:
            if session_id not in self._message_queues:
                return None

            try:
                return self._message_queues[session_id].get_nowait()
            except asyncio.QueueEmpty:
                return None

    def is_processing(self, session_id: str) -> bool:
        """Check if session is currently processing."""
        return self._processing.get(session_id, False)

    def set_processing(self, session_id: str, value: bool):
        """Set processing state for session."""
        self._processing[session_id] = value


# Global event bus
event_bus = SessionEventBus()


app = FastAPI(title="Major Chat Agent", version="0.1.0")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3002", "http://localhost:3003", "http://localhost:3004", "http://localhost:3005"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def git_commit(workspace: Path, message: str) -> bool:
    """Commit changes to git repository.

    Args:
        workspace: Path to workspace
        message: Commit message

    Returns:
        True if commit succeeded, False otherwise
    """
    try:
        # Add all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=workspace,
            check=True,
            capture_output=True,
        )

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
        )

        if not result.stdout.strip():
            # No changes to commit
            return True

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=workspace,
            check=True,
            capture_output=True,
        )

        # Push (best effort, don't fail if push fails)
        subprocess.run(
            ["git", "push"],
            cwd=workspace,
            capture_output=True,
        )

        return True
    except subprocess.CalledProcessError as e:
        print(f"Git commit failed: {e}")
        return False

# Initialize agent
agent: MajorAgent | None = None


def get_agent() -> MajorAgent:
    """Get or create agent instance."""
    global agent
    if agent is None:
        config = MajorConfig()
        agent = MajorAgent(config=config)
    return agent


class ChatRequest(BaseModel):
    """Chat request."""
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    session_id: str
    response: str


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "agent": "major"}


@app.post("/chat")
async def chat(request: ChatRequest):
    """Send a chat message and get streaming response."""
    workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")

    agent = get_agent()

    async def generate() -> AsyncGenerator[str, None]:
        """Generate SSE events from agent."""
        current_text = ""
        session_id = request.session_id
        sent_session_start = False

        async for event in agent.send_message(
            message=request.message,
            workspace_path=workspace_path,
            session_id=session_id,
        ):
            # Handle different event types
            event_type = type(event).__name__

            if event_type == "AssistantMessage":
                # Extract text content
                if hasattr(event, "content"):
                    for block in event.content:
                        if hasattr(block, "text"):
                            delta = block.text[len(current_text):]
                            if delta:
                                current_text = block.text
                                yield f"data: {json.dumps({'type': 'text_delta', 'text': delta})}\n\n"

            elif event_type == "StreamEvent":
                # Raw stream event
                if hasattr(event, "type"):
                    if event.type == "content_block_delta":
                        if hasattr(event, "delta") and hasattr(event.delta, "text"):
                            yield f"data: {json.dumps({'type': 'text_delta', 'text': event.delta.text})}\n\n"

            elif event_type == "ResultMessage":
                # Final result with session ID
                if hasattr(event, "session_id"):
                    session_id = event.session_id
                    if not sent_session_start:
                        yield f"data: {json.dumps({'type': 'session_start', 'session_id': session_id})}\n\n"
                        sent_session_start = True
                    # Register session with session_manager so it appears in list
                    session_manager.create_session(workspace_path, session_id)

        # Commit session to git (git as database - commit after every message)
        git_commit(Path(workspace_path), f"Chat: {session_id}")

        # Send done event
        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'usage': {'input_tokens': 0, 'output_tokens': 0}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/chat/sync", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """Send a chat message and get full response (non-streaming)."""
    workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")

    agent = get_agent()

    full_response = ""
    session_id = request.session_id

    async for event in agent.send_message(
        message=request.message,
        workspace_path=workspace_path,
        session_id=session_id,
    ):
        event_type = type(event).__name__

        if event_type == "AssistantMessage":
            if hasattr(event, "content"):
                for block in event.content:
                    if hasattr(block, "text"):
                        full_response = block.text

        elif event_type == "ResultMessage":
            if hasattr(event, "session_id"):
                session_id = event.session_id
                # Register session with session_manager so it appears in list
                session_manager.create_session(workspace_path, session_id)

    # Commit session to git (git as database - commit after every message)
    git_commit(Path(workspace_path), f"Chat: {session_id}")

    return ChatResponse(
        session_id=session_id or "unknown",
        response=full_response,
    )


# Background task storage for chat/send
_running_sessions: dict[str, asyncio.Task] = {}


class ChatSendResponse(BaseModel):
    """Response from chat/send endpoint."""
    session_id: str
    status: str  # "started" or "already_running"


@app.post("/chat/send", response_model=ChatSendResponse)
async def chat_send(request: ChatRequest):
    """Send a chat message (fire-and-forget).

    Starts Claude in background and returns immediately.
    Poll /sessions/{session_id}/history to get updates.
    """
    workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")

    # Generate a pending session ID if not provided
    session_id = request.session_id
    if not session_id:
        import uuid
        session_id = f"pending-{uuid.uuid4().hex[:8]}"

    # Check if already running
    if session_id in _running_sessions:
        task = _running_sessions[session_id]
        if not task.done():
            return ChatSendResponse(session_id=session_id, status="already_running")

    agent = get_agent()

    async def run_chat():
        """Run chat in background, writing to session files."""
        nonlocal session_id
        try:
            async for event in agent.send_message(
                message=request.message,
                workspace_path=workspace_path,
                session_id=session_id if not session_id.startswith("pending-") else None,
            ):
                event_type = type(event).__name__
                if event_type == "ResultMessage":
                    if hasattr(event, "session_id") and event.session_id:
                        # Update with real session ID from SDK
                        real_session_id = event.session_id
                        session_manager.create_session(workspace_path, real_session_id)
                        # Update tracking
                        if session_id in _running_sessions:
                            _running_sessions[real_session_id] = _running_sessions.pop(session_id)
                        session_id = real_session_id
            # Commit session to git (git as database - commit after every message)
            git_commit(Path(workspace_path), f"Chat: {session_id}")
        except Exception as e:
            print(f"[CHAT_SEND] Background task error: {e}", flush=True)
        finally:
            # Clean up tracking
            _running_sessions.pop(session_id, None)

    # Start background task
    task = asyncio.create_task(run_chat())
    _running_sessions[session_id] = task

    # Wait briefly for SDK to create the real session ID
    await asyncio.sleep(0.5)

    # Check if we got a real session ID
    for sid, t in list(_running_sessions.items()):
        if t is task and not sid.startswith("pending-"):
            session_id = sid
            break

    return ChatSendResponse(session_id=session_id, status="started")


# ============== Schema Endpoint ==============

class SchemaEntityType(BaseModel):
    """Entity type from schema."""
    name: str
    directory: str
    description: str | None = None
    icon: str | None = None


class SchemaResponse(BaseModel):
    """Workspace schema response."""
    entities: list[SchemaEntityType]


@app.get("/schema", response_model=SchemaResponse)
async def get_schema():
    """Get workspace schema (entity types from .claude/schema.yaml)."""
    workspace = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))
    schema_path = workspace / ".claude" / "schema.yaml"

    if not schema_path.exists():
        return SchemaResponse(entities=[])

    try:
        data = yaml.safe_load(schema_path.read_text()) or {}
        entities_data = data.get("entities", {})

        entities = []
        for name, config in entities_data.items():
            entities.append(SchemaEntityType(
                name=name,
                directory=config.get("directory", name),
                description=config.get("description"),
                icon=config.get("icon"),
            ))

        return SchemaResponse(entities=entities)
    except (yaml.YAMLError, Exception) as e:
        # Return empty on parse error
        return SchemaResponse(entities=[])


# ============== Entity Endpoints ==============

def get_workspace_path() -> str:
    """Get workspace path from environment."""
    return os.environ.get("WORKSPACE_PATH", "/workspace")


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()
        return frontmatter, body
    except yaml.YAMLError:
        return {}, content


def serialize_frontmatter(frontmatter: dict, body: str) -> str:
    """Serialize frontmatter and body back to markdown."""
    if not frontmatter:
        return body
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    return f"---\n{yaml_str}---\n\n{body}"


class EntityType(BaseModel):
    """Entity type info."""
    name: str
    count: int


class EntityListItem(BaseModel):
    """Entity list item."""
    id: str
    title: str


class Entity(BaseModel):
    """Full entity."""
    id: str
    type: str
    title: str
    content: str
    frontmatter: dict


class CreateEntityRequest(BaseModel):
    """Request to create entity."""
    title: str
    content: str = ""
    frontmatter: dict = {}


class UpdateEntityRequest(BaseModel):
    """Request to update entity."""
    title: str | None = None
    content: str | None = None
    frontmatter: dict | None = None


@app.get("/entities/types")
async def list_entity_types() -> list[EntityType]:
    """List all entity types in the workspace."""
    workspace = Path(get_workspace_path())
    types = []

    # Directories that are entity types (not hidden, not special)
    skip_dirs = {'.git', '.claude', '.chelle', 'node_modules', '__pycache__', '.venv'}

    for item in workspace.iterdir():
        if item.is_dir() and item.name not in skip_dirs and not item.name.startswith('.'):
            # Count markdown files (show directory even if empty)
            count = len(list(item.glob('**/*.md')))
            types.append(EntityType(name=item.name, count=count))

    return sorted(types, key=lambda t: t.name)


@app.get("/entities/{entity_type}")
async def list_entities(entity_type: str) -> list[EntityListItem]:
    """List entities of a given type."""
    workspace = Path(get_workspace_path())
    type_dir = workspace / entity_type.replace('::', '/')

    if not type_dir.exists() or not type_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Entity type '{entity_type}' not found")

    entities = []
    for md_file in type_dir.glob('**/*.md'):
        try:
            content = md_file.read_text()
            frontmatter, _ = parse_frontmatter(content)
            title = frontmatter.get('title', md_file.stem.replace('-', ' ').replace('_', ' ').title())

            # Build entity ID (relative path without .md)
            rel_path = md_file.relative_to(type_dir)
            entity_id = str(rel_path)[:-3]  # Remove .md

            entities.append(EntityListItem(id=entity_id, title=title))
        except Exception:
            continue

    return sorted(entities, key=lambda e: e.title.lower())


@app.get("/entities/{entity_type}/{entity_id:path}")
async def get_entity(entity_type: str, entity_id: str) -> Entity:
    """Get a specific entity."""
    workspace = Path(get_workspace_path())
    entity_path = workspace / entity_type.replace('::', '/') / f"{entity_id}.md"

    if not entity_path.exists():
        raise HTTPException(status_code=404, detail="Entity not found")

    content = entity_path.read_text()
    frontmatter, body = parse_frontmatter(content)
    title = frontmatter.get('title', entity_id.replace('-', ' ').replace('_', ' ').title())

    return Entity(
        id=entity_id,
        type=entity_type,
        title=title,
        content=body,
        frontmatter=frontmatter,
    )


@app.post("/entities/{entity_type}")
async def create_entity(entity_type: str, request: CreateEntityRequest) -> Entity:
    """Create a new entity."""
    workspace = Path(get_workspace_path())
    type_dir = workspace / entity_type.replace('::', '/')
    type_dir.mkdir(parents=True, exist_ok=True)

    # Generate ID from title
    entity_id = re.sub(r'[^a-z0-9]+', '-', request.title.lower()).strip('-')
    entity_path = type_dir / f"{entity_id}.md"

    # Avoid overwriting
    if entity_path.exists():
        counter = 1
        while (type_dir / f"{entity_id}-{counter}.md").exists():
            counter += 1
        entity_id = f"{entity_id}-{counter}"
        entity_path = type_dir / f"{entity_id}.md"

    # Build frontmatter
    frontmatter = {**request.frontmatter, 'title': request.title}
    content = serialize_frontmatter(frontmatter, request.content)

    entity_path.write_text(content)

    # Commit to git
    git_commit(workspace, f"Create {entity_type}/{entity_id}")

    return Entity(
        id=entity_id,
        type=entity_type,
        title=request.title,
        content=request.content,
        frontmatter=frontmatter,
    )


@app.put("/entities/{entity_type}/{entity_id:path}")
async def update_entity(entity_type: str, entity_id: str, request: UpdateEntityRequest) -> Entity:
    """Update an existing entity."""
    workspace = Path(get_workspace_path())
    entity_path = workspace / entity_type.replace('::', '/') / f"{entity_id}.md"

    if not entity_path.exists():
        raise HTTPException(status_code=404, detail="Entity not found")

    # Read existing
    existing = entity_path.read_text()
    frontmatter, body = parse_frontmatter(existing)

    # Update fields
    if request.title is not None:
        frontmatter['title'] = request.title
    if request.frontmatter is not None:
        frontmatter.update(request.frontmatter)
    if request.content is not None:
        body = request.content

    content = serialize_frontmatter(frontmatter, body)
    entity_path.write_text(content)

    # Commit to git
    git_commit(workspace, f"Update {entity_type}/{entity_id}")

    title = frontmatter.get('title', entity_id.replace('-', ' ').title())

    return Entity(
        id=entity_id,
        type=entity_type,
        title=title,
        content=body,
        frontmatter=frontmatter,
    )


@app.delete("/entities/{entity_type}/{entity_id:path}")
async def delete_entity(entity_type: str, entity_id: str):
    """Delete an entity."""
    workspace = Path(get_workspace_path())
    entity_path = workspace / entity_type.replace('::', '/') / f"{entity_id}.md"

    if not entity_path.exists():
        raise HTTPException(status_code=404, detail="Entity not found")

    entity_path.unlink()

    # Commit to git
    git_commit(workspace, f"Delete {entity_type}/{entity_id}")

    return {"status": "deleted", "id": entity_id}


# ============== Session Endpoints ==============

class SessionInfo(BaseModel):
    """Session info for API."""
    id: str
    title: str | None
    archived: bool
    created_at: str
    updated_at: str


class SessionMessageResponse(BaseModel):
    """Session message for API."""
    role: str
    content: str
    tool_name: str | None = None


class UpdateSessionRequest(BaseModel):
    """Request to update session."""
    title: str | None = None
    archived: bool | None = None


@app.get("/sessions")
async def list_sessions(include_archived: bool = False) -> list[SessionInfo]:
    """List all sessions."""
    workspace = get_workspace_path()
    sessions = session_manager.list_sessions(workspace, include_archived)

    return [
        SessionInfo(
            id=s.session_id,
            title=s.title,
            archived=s.archived,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    title: str | None = None


@app.post("/sessions", response_model=SessionInfo)
async def create_session(request: CreateSessionRequest = None):
    """Create a new chat session.

    Returns the session info with generated ID. Use this ID to:
    1. Connect to /sessions/{id}/events for real-time updates
    2. Send messages via POST /sessions/{id}/messages
    """
    workspace = get_workspace_path()
    session_id = str(uuid.uuid4())

    # Create session
    session_manager.create_session(workspace, session_id)

    # Update title if provided
    if request and request.title:
        session_manager.update_session(workspace, session_id, title=request.title)

    session = session_manager.get_session(workspace, session_id)

    return SessionInfo(
        id=session.session_id,
        title=session.title,
        archived=session.archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.get("/sessions/{session_id}")
async def get_session(session_id: str) -> SessionInfo:
    """Get session info."""
    workspace = get_workspace_path()
    session = session_manager.get_session(workspace, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionInfo(
        id=session.session_id,
        title=session.title,
        archived=session.archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str) -> dict:
    """Get session message history."""
    workspace = get_workspace_path()
    messages = session_manager.get_history(workspace, session_id)

    return {
        "session_id": session_id,
        "messages": [
            SessionMessageResponse(
                role=m.role,
                content=m.content,
                tool_name=m.tool_name,
            )
            for m in messages
        ],
    }


@app.patch("/sessions/{session_id}")
async def update_session(session_id: str, request: UpdateSessionRequest) -> SessionInfo:
    """Update session metadata."""
    workspace = get_workspace_path()

    session = session_manager.update_session(
        workspace,
        session_id,
        title=request.title,
        archived=request.archived,
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Commit metadata change to git
    git_commit(Path(workspace), f"Update session: {session_id}")

    return SessionInfo(
        id=session.session_id,
        title=session.title,
        archived=session.archived,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    workspace = get_workspace_path()
    session_manager.delete_session(workspace, session_id)
    # Commit deletion to git
    git_commit(Path(workspace), f"Delete session: {session_id}")
    return {"status": "deleted", "session_id": session_id}


# ============== Slack-like Async Chat Endpoints ==============

class SendMessageRequest(BaseModel):
    """Request to send a message (fire-and-forget)."""
    message: str


class SendMessageResponse(BaseModel):
    """Response from sending a message."""
    status: str  # "queued"
    message_id: str


@app.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: str, request: SendMessageRequest):
    """Send a message to a session (fire-and-forget).

    The message is queued and the agent will process it asynchronously.
    Events are pushed to subscribers via the /sessions/{id}/events SSE endpoint.
    """
    workspace_path = get_workspace_path()

    # Verify session exists or create it
    session = session_manager.get_session(workspace_path, session_id)
    if not session:
        # Create the session
        session_manager.create_session(workspace_path, session_id)

    # Generate message ID
    message_id = f"msg-{uuid.uuid4().hex[:12]}"

    # Queue the message
    await event_bus.queue_message(session_id, request.message)

    # Publish user_message event to subscribers
    await event_bus.publish(session_id, SessionEvent(
        type="user_message",
        data={"message": request.message, "message_id": message_id}
    ))

    # Start processing if not already running
    if not event_bus.is_processing(session_id):
        asyncio.create_task(_process_session_messages(session_id, workspace_path))

    return SendMessageResponse(status="queued", message_id=message_id)


async def _process_session_messages(session_id: str, workspace_path: str):
    """Process queued messages for a session.

    Runs in background, picks up messages from queue, sends to agent,
    publishes events to subscribers.
    """
    if event_bus.is_processing(session_id):
        return  # Already processing

    event_bus.set_processing(session_id, True)

    # Track the actual SDK session ID (may differ from our session_id for new sessions)
    sdk_session_id: str | None = None

    # Check if SDK session file exists (determines if we should resume or create new)
    sessions_dir = Path(workspace_path) / ".chelle" / "sessions"
    session_file = sessions_dir / f"{session_id}.jsonl"
    if session_file.exists():
        sdk_session_id = session_id

    try:
        agent = get_agent()

        while True:
            # Get next message from queue
            message = await event_bus.get_next_message(session_id)
            if message is None:
                break  # No more messages

            # Publish processing_start event
            await event_bus.publish(session_id, SessionEvent(
                type="processing_start",
                data={"message": message}
            ))

            current_text = ""

            try:
                async for event in agent.send_message(
                    message=message,
                    workspace_path=workspace_path,
                    session_id=sdk_session_id,  # None for new sessions, SDK creates its own ID
                ):
                    event_type = type(event).__name__

                    if event_type == "AssistantMessage":
                        # Extract text content
                        if hasattr(event, "content"):
                            for block in event.content:
                                if hasattr(block, "text"):
                                    delta = block.text[len(current_text):]
                                    if delta:
                                        current_text = block.text
                                        await event_bus.publish(session_id, SessionEvent(
                                            type="text_delta",
                                            data={"text": delta}
                                        ))
                                # Check for tool use
                                if hasattr(block, "type") and block.type == "tool_use":
                                    tool_name = getattr(block, "name", "unknown")
                                    await event_bus.publish(session_id, SessionEvent(
                                        type="tool_use",
                                        data={"tool": tool_name, "status": "running"}
                                    ))

                    elif event_type == "StreamEvent":
                        # Raw stream event
                        if hasattr(event, "type"):
                            if event.type == "content_block_delta":
                                if hasattr(event, "delta") and hasattr(event.delta, "text"):
                                    await event_bus.publish(session_id, SessionEvent(
                                        type="text_delta",
                                        data={"text": event.delta.text}
                                    ))
                            elif event.type == "content_block_start":
                                # Tool use start
                                if hasattr(event, "content_block"):
                                    block = event.content_block
                                    if hasattr(block, "type") and block.type == "tool_use":
                                        tool_name = getattr(block, "name", "unknown")
                                        await event_bus.publish(session_id, SessionEvent(
                                            type="tool_use",
                                            data={"tool": tool_name, "status": "start"}
                                        ))
                            elif event.type == "content_block_stop":
                                # Could be end of tool use
                                await event_bus.publish(session_id, SessionEvent(
                                    type="tool_use",
                                    data={"status": "stop"}
                                ))

                    elif event_type == "ResultMessage":
                        # Final result - capture SDK's session ID
                        if hasattr(event, "session_id") and event.session_id:
                            actual_sdk_id = event.session_id
                            session_manager.create_session(workspace_path, actual_sdk_id)

                            # If SDK created a new session with different ID, symlink to our session_id
                            if actual_sdk_id != session_id:
                                sdk_file = sessions_dir / f"{actual_sdk_id}.jsonl"
                                our_file = sessions_dir / f"{session_id}.jsonl"
                                if sdk_file.exists() and not our_file.exists():
                                    try:
                                        our_file.symlink_to(sdk_file.name)
                                    except Exception:
                                        pass  # Best effort

                            # Use SDK's session ID for future messages in this batch
                            sdk_session_id = actual_sdk_id

                # Publish assistant_message with full content
                if current_text:
                    await event_bus.publish(session_id, SessionEvent(
                        type="assistant_message",
                        data={"content": current_text}
                    ))

                # Commit to git
                git_commit(Path(workspace_path), f"Chat: {session_id}")

            except Exception as e:
                await event_bus.publish(session_id, SessionEvent(
                    type="error",
                    data={"error": str(e)}
                ))

        # All messages processed
        await event_bus.publish(session_id, SessionEvent(
            type="done",
            data={"session_id": session_id}
        ))

    finally:
        event_bus.set_processing(session_id, False)


@app.get("/sessions/{session_id}/events")
async def session_events(session_id: str):
    """Subscribe to session events via Server-Sent Events.

    On connect:
    1. Sends 'connected' event
    2. Sends 'history' event with all past messages
    3. Streams real-time events (user_message, text_delta, tool_use, assistant_message, done, error)

    Client should maintain this connection for the duration of the chat session.
    """
    workspace_path = get_workspace_path()

    async def generate() -> AsyncGenerator[str, None]:
        # Subscribe to events
        queue = await event_bus.subscribe(session_id)

        try:
            # Send connected event
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # Send history
            try:
                messages = session_manager.get_history(workspace_path, session_id)
                history_data = [
                    {"role": m.role, "content": m.content, "tool_name": m.tool_name}
                    for m in messages
                ]
                yield f"data: {json.dumps({'type': 'history', 'messages': history_data})}\n\n"
            except Exception:
                # No history yet, that's fine
                yield f"data: {json.dumps({'type': 'history', 'messages': []})}\n\n"

            # Stream events
            while True:
                try:
                    # Wait for event with timeout to allow checking connection
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps({'type': event.type, **event.data, 'timestamp': event.timestamp})}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"

        finally:
            await event_bus.unsubscribe(session_id, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# ============== Library Endpoints ==============

class LibraryFileResponse(BaseModel):
    """Library file info for API."""
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    error_message: str | None
    entity_type: str | None
    entity_id: str | None
    created_at: str
    processed_at: str | None


def _library_file_to_response(lf: LibraryFileModel) -> LibraryFileResponse:
    """Convert LibraryFile dataclass to response model."""
    return LibraryFileResponse(
        id=lf.id,
        filename=lf.filename,
        content_type=lf.content_type,
        size_bytes=lf.size_bytes,
        status=lf.status,
        error_message=lf.error_message,
        entity_type=lf.entity_type,
        entity_id=lf.entity_id,
        created_at=lf.created_at,
        processed_at=lf.processed_at,
    )


@app.get("/library/files")
async def list_library_files() -> list[LibraryFileResponse]:
    """List all library files."""
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)
    files = manager.list_files()
    return [_library_file_to_response(f) for f in files]


@app.get("/library/files/{file_id}")
async def get_library_file(file_id: str) -> LibraryFileResponse:
    """Get a specific library file."""
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)
    library_file = manager.get_file(file_id)

    if not library_file:
        raise HTTPException(status_code=404, detail="File not found")

    return _library_file_to_response(library_file)


class LibraryFileContentResponse(BaseModel):
    """Library file content response."""
    id: str
    filename: str
    content: str
    summaries: dict | None = None
    topics: list[str] | None = None


@app.get("/library/files/{file_id}/content")
async def get_library_file_content(file_id: str) -> LibraryFileContentResponse:
    """Get the extracted content of a library file."""
    workspace = Path(get_workspace_path())
    manager = LibraryManager(str(workspace))
    library_file = manager.get_file(file_id)

    if not library_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Read extracted content
    content_path = workspace / ".library" / "files" / file_id / "extracted.txt"
    if not content_path.exists():
        raise HTTPException(status_code=404, detail="Content not found - file may not be processed yet")

    content = content_path.read_text()

    # Try to load index data for summaries/topics
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    doc = index.get_document(file_id)

    summaries = None
    topics = None
    if doc:
        summaries = {
            "brief": doc.summaries.brief,
            "standard": doc.summaries.standard,
            "detailed": doc.summaries.detailed,
        }
        topics = doc.topics

    return LibraryFileContentResponse(
        id=file_id,
        filename=library_file.filename,
        content=content,
        summaries=summaries,
        topics=topics,
    )


@app.post("/library/upload")
async def upload_library_file(file: UploadFile = File(...)) -> LibraryFileResponse:
    """Upload and process a file.

    Supports: PDF (.pdf), Markdown (.md), Plain Text (.txt)
    """
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    if not is_supported_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: .pdf, .md, .txt"
        )

    # Read file content
    content = await file.read()

    # Generate file ID
    file_id = uuid.uuid4().hex[:12]

    # Determine content type
    content_type = file.content_type or get_content_type(file.filename)

    # Save the file
    library_file = manager.save_uploaded_file(
        file_id=file_id,
        filename=file.filename,
        content=content,
        content_type=content_type,
    )

    # Process the file synchronously (extract content, create entity)
    library_file = manager.process_file(file_id)

    # Commit to git
    git_commit(Path(workspace), f"Library: upload {file.filename}")

    return _library_file_to_response(library_file)


@app.delete("/library/files/{file_id}")
async def delete_library_file(file_id: str):
    """Delete a library file and its associated entity."""
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)

    library_file = manager.get_file(file_id)
    if not library_file:
        raise HTTPException(status_code=404, detail="File not found")

    filename = library_file.filename
    deleted = manager.delete_file(file_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")

    # Commit to git
    git_commit(Path(workspace), f"Library: delete {filename}")

    return {"status": "deleted", "id": file_id}


@app.post("/library/files/{file_id}/retry")
async def retry_library_file(file_id: str) -> LibraryFileResponse:
    """Retry processing a failed file."""
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)

    library_file = manager.get_file(file_id)
    if not library_file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        library_file = manager.retry_processing(file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Commit to git
    git_commit(Path(workspace), f"Library: retry {library_file.filename}")

    return _library_file_to_response(library_file)


@app.post("/library/infer-schema")
async def infer_schema():
    """Analyze library files and propose a workspace schema."""
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)
    organizer = WorkspaceOrganizer(Path(workspace))

    try:
        proposal = organizer.infer_schema(manager)
        return proposal
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class OrganizeRequest(BaseModel):
    """Request body for workspace organization."""
    workspace_schema: dict
    file_assignments: list[dict]


@app.post("/library/organize")
async def organize_workspace(request: OrganizeRequest):
    """Apply schema and create structured entities (SSE stream)."""
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)
    organizer = WorkspaceOrganizer(Path(workspace))

    async def generate():
        async for event in organizer.organize(
            request.workspace_schema,
            request.file_assignments,
            manager,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def main():
    """Run the server."""
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
