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
from fastapi.responses import StreamingResponse, FileResponse
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

    async def queue_message(self, session_id: str, message: str, context: dict | None = None) -> bool:
        """Queue a user message for processing. Returns True if queued."""
        async with self._lock:
            if session_id not in self._message_queues:
                self._message_queues[session_id] = asyncio.Queue()

            await self._message_queues[session_id].put((message, context))
            return True

    async def get_next_message(self, session_id: str) -> tuple[str, dict | None] | None:
        """Get next message and context from queue, or None if empty."""
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
    allow_origins=["http://localhost:3001", "http://localhost:3002", "http://localhost:3003", "http://localhost:3004", "http://localhost:3005", "http://localhost:3006", "http://localhost:3007"],
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
    context: dict | None = None  # {currentView, currentEntity, sourceIds}


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

    # Build source constraint from context
    source_constraint = None
    if request.context and request.context.get("sourceIds"):
        from .librarian import LibraryIndex
        lib_index = LibraryIndex(workspace_path)
        source_constraint = []
        total_chars = 0
        max_budget = 60000
        for sid in request.context["sourceIds"]:
            if sid == "*":
                docs = lib_index.list_documents()
            elif lib_index.get_topic(sid):
                docs = lib_index.list_documents(topic_filter=[sid])
            else:
                doc = lib_index.get_document(sid)
                docs = [doc] if doc else []

            for doc in docs:
                if total_chars >= max_budget:
                    break
                content = lib_index.get_document_content(doc.id)
                if content:
                    truncated = content[:min(15000, max_budget - total_chars)]
                    source_constraint.append({
                        "title": doc.title,
                        "content": truncated,
                    })
                    total_chars += len(truncated)
            if total_chars >= max_budget:
                break

    async def generate() -> AsyncGenerator[str, None]:
        """Generate SSE events from agent."""
        import logging
        logger = logging.getLogger(__name__)
        current_text = ""
        session_id = request.session_id
        sent_session_start = False

        logger.info(f"[chat] source_constraint: {len(source_constraint) if source_constraint else 0} docs, session_id={session_id}")
        try:
            async for event in agent.send_message(
                message=request.message,
                workspace_path=workspace_path,
                session_id=session_id,
                source_constraint=source_constraint,
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
                            # Check for tool use blocks
                            if hasattr(block, "type") and block.type == "tool_use":
                                tool_name = getattr(block, "name", "unknown")
                                yield f"data: {json.dumps({'type': 'tool_use', 'tool': tool_name, 'status': 'running'})}\n\n"

                elif event_type == "StreamEvent":
                    # Raw stream event
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event, "delta") and hasattr(event.delta, "text"):
                                yield f"data: {json.dumps({'type': 'text_delta', 'text': event.delta.text})}\n\n"
                        elif event.type == "content_block_start":
                            if hasattr(event, "content_block"):
                                block = event.content_block
                                if hasattr(block, "type") and block.type == "tool_use":
                                    tool_name = getattr(block, "name", "unknown")
                                    yield f"data: {json.dumps({'type': 'tool_use', 'tool': tool_name, 'status': 'start'})}\n\n"
                        elif event.type == "content_block_stop":
                            yield f"data: {json.dumps({'type': 'tool_use', 'status': 'stop'})}\n\n"

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
        except Exception as e:
            logger.error(f"[chat] Error in generate: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

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
    workflow: list[str] | None = None


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

        # Parse workflow (optional ordered list of entity type names)
        workflow_data = data.get("workflow")
        entity_names = set(entities_data.keys())
        workflow = [w for w in workflow_data if w in entity_names] if isinstance(workflow_data, list) else None

        return SchemaResponse(entities=entities, workflow=workflow)
    except (yaml.YAMLError, Exception) as e:
        # Return empty on parse error
        return SchemaResponse(entities=[])


class UpdateWorkflowRequest(BaseModel):
    """Request to update workflow order."""
    workflow: list[str]


class CreateEntityTypeRequest(BaseModel):
    """Request to create a new entity type."""
    name: str


@app.post("/schema/entity-types", response_model=SchemaEntityType)
async def create_entity_type(request: CreateEntityTypeRequest):
    """Create a new entity type in the workspace schema."""
    workspace = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))
    schema_path = workspace / ".claude" / "schema.yaml"

    # Validate name: lowercase, underscores, no special chars
    name = request.name.strip().lower().replace(" ", "_")
    if not re.match(r'^[a-z][a-z0-9_]*$', name):
        raise HTTPException(
            status_code=400,
            detail="Entity type name must start with a letter and contain only lowercase letters, numbers, and underscores",
        )

    # Load or create schema
    if schema_path.exists():
        try:
            data = yaml.safe_load(schema_path.read_text()) or {}
        except yaml.YAMLError:
            raise HTTPException(status_code=500, detail="Failed to parse schema.yaml")
    else:
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}

    entities = data.get("entities", {})

    # Check if already exists
    if name in entities:
        raise HTTPException(status_code=409, detail=f"Entity type '{name}' already exists")

    # Create the directory
    type_dir = workspace / name
    type_dir.mkdir(parents=True, exist_ok=True)

    # Add to schema
    entities[name] = {"directory": name}
    data["entities"] = entities

    schema_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))

    # Commit to git
    git_commit(workspace, f"Add entity type: {name}")

    return SchemaEntityType(name=name, directory=name)


@app.put("/schema/workflow")
async def update_workflow(request: UpdateWorkflowRequest):
    """Update the workflow order in schema.yaml."""
    workspace = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))
    schema_path = workspace / ".claude" / "schema.yaml"

    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="No schema.yaml found")

    try:
        data = yaml.safe_load(schema_path.read_text()) or {}
    except yaml.YAMLError:
        raise HTTPException(status_code=500, detail="Failed to parse schema.yaml")

    # Validate all workflow entries are valid entity types
    entity_names = set(data.get("entities", {}).keys())
    invalid = [w for w in request.workflow if w not in entity_names]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity types in workflow: {invalid}. Valid types: {sorted(entity_names)}",
        )

    # Update workflow in data
    data["workflow"] = request.workflow

    # Write back preserving structure
    schema_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True))

    # Commit to git
    git_commit(workspace, "Update workflow order")

    return {"workflow": request.workflow}


# ============== Entity Endpoints ==============

def get_workspace_path() -> str:
    """Get workspace path from environment."""
    return os.environ.get("WORKSPACE_PATH", "/workspace")


def get_schema_entity_types() -> list[str] | None:
    """Get valid entity types from schema. Returns None if no schema exists."""
    workspace = Path(get_workspace_path())
    schema_path = workspace / ".claude" / "schema.yaml"
    if not schema_path.exists():
        return None
    try:
        data = yaml.safe_load(schema_path.read_text()) or {}
        return list(data.get("entities", {}).keys())
    except Exception:
        return None


def validate_entity_type(entity_type: str) -> None:
    """Raise 400 if entity_type is not in the workspace schema."""
    valid_types = get_schema_entity_types()
    if valid_types is not None and entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity type '{entity_type}'. Valid types: {valid_types}",
        )


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


@app.get("/export/docx/{entity_type}/{entity_id:path}")
async def export_entity_docx(entity_type: str, entity_id: str):
    """Export an entity as a DOCX file."""
    workspace = Path(get_workspace_path())
    entity_path = workspace / entity_type.replace('::', '/') / f"{entity_id}.md"

    if not entity_path.exists():
        raise HTTPException(status_code=404, detail="Entity not found")

    content = entity_path.read_text()
    frontmatter, body = parse_frontmatter(content)
    title = frontmatter.get('title', entity_id.replace('-', ' ').replace('_', ' ').title())

    from .docx_export import markdown_to_docx
    docx_bytes = markdown_to_docx(body, title=title)

    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    filename = f"{safe_title}.docx"

    return StreamingResponse(
        iter([docx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    validate_entity_type(entity_type)
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
    source_ids: list[str] | None = None


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
            source_ids=s.source_ids,
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
        source_ids=session.source_ids,
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
        source_ids=session.source_ids,
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
        source_ids=session.source_ids,
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

class MessageContext(BaseModel):
    """Page context sent with a message."""
    currentView: str | None = None
    currentEntity: dict | None = None  # {type, id, title}
    sourceIds: list[str] | None = None  # For source-grounded chat

class SendMessageRequest(BaseModel):
    """Request to send a message (fire-and-forget)."""
    message: str
    context: MessageContext | None = None


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

    # Queue the message with context
    ctx = request.context.model_dump() if request.context else None
    await event_bus.queue_message(session_id, request.message, ctx)

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
            result = await event_bus.get_next_message(session_id)
            if result is None:
                break  # No more messages

            message, context = result

            # Build source constraint for source-grounded chat
            source_constraint = None
            if context and context.get("sourceIds"):
                from .librarian import LibraryIndex
                lib_index = LibraryIndex(workspace_path)
                source_constraint = []
                total_chars = 0
                max_budget = 60000
                for sid in context["sourceIds"]:
                    if sid == "*":
                        docs = lib_index.list_documents()
                    elif lib_index.get_topic(sid):
                        docs = lib_index.list_documents(topic_filter=[sid])
                    else:
                        doc = lib_index.get_document(sid)
                        docs = [doc] if doc else []

                    for doc in docs:
                        if total_chars >= max_budget:
                            break
                        content = lib_index.get_document_content(doc.id)
                        if content:
                            truncated = content[:min(15000, max_budget - total_chars)]
                            source_constraint.append({
                                "title": doc.title,
                                "content": truncated,
                            })
                            total_chars += len(truncated)
                    if total_chars >= max_budget:
                        break
                # Store source_ids in session metadata for persistence
                session_manager.update_session(
                    workspace_path, session_id, source_ids=context["sourceIds"]
                )

            # Build attached_entities from page context
            attached_entities = None
            if context and context.get("currentEntity"):
                entity_info = context["currentEntity"]
                entity_type = entity_info.get("type")
                entity_id = entity_info.get("id")
                entity_title = entity_info.get("title", "Untitled")

                if entity_type and entity_id:
                    # Load entity content from workspace
                    entity_path = Path(workspace_path) / entity_type / f"{entity_id}.md"
                    entity_content = ""
                    if entity_path.exists():
                        entity_content = entity_path.read_text()
                    attached_entities = [{
                        "type": entity_type,
                        "id": entity_id,
                        "title": entity_title,
                        "content": entity_content,
                    }]
            elif context and context.get("currentView"):
                # Just note what section the user is viewing
                view = context["currentView"]
                attached_entities = [{
                    "type": "navigation",
                    "id": view,
                    "title": f"User is currently viewing: {view}",
                    "content": "",
                }]

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
                    attached_entities=attached_entities,
                    source_constraint=source_constraint,
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
                    # Wait for event with timeout to send keepalive.
                    # 15s keeps Vercel proxy alive (its idle timeout is ~30s).
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
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

    # Process the file synchronously (extract content)
    library_file = manager.process_file(file_id)

    # Run AI analysis and create workspace entity
    if library_file.status == "complete":
        try:
            from .librarian import LibraryIndex, DocumentAnalyzer
            index = LibraryIndex(workspace)
            extracted = manager.get_extracted_content(file_id)
            if extracted:
                analyzer = DocumentAnalyzer()
                doc = analyzer.analyze_and_index(file_id, extracted, file.filename, index)

                # Create workspace entity from analyzed content
                entity_type = "documents"
                entity_id = manager._create_entity(
                    entity_type=entity_type,
                    title=doc.title,
                    content=extracted,
                    source_file=file_id,
                    source_filename=file.filename,
                )
                manager._update_file_entity(file_id, entity_type, entity_id)
                library_file = manager.get_file(file_id)
        except Exception as e:
            # Don't fail the upload if analysis fails - file is still usable
            import logging
            logging.getLogger(__name__).warning(f"Library analysis failed for {file_id}: {e}")

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


# ============== Library Topic Endpoints ==============

class TopicResponse(BaseModel):
    """Topic summary for API."""
    id: str
    name: str
    description: str
    document_count: int
    file_count: int = 0
    entity_count: int = 0


class TopicDocumentResponse(BaseModel):
    """Document info within a topic detail."""
    id: str
    title: str
    doc_type: str
    summary: str
    source: str = "file"  # "file" or "entity"


class TopicDetailResponse(BaseModel):
    """Detailed topic info with documents."""
    id: str
    name: str
    description: str
    document_count: int
    file_count: int = 0
    entity_count: int = 0
    documents: list[TopicDocumentResponse]


@app.get("/library/topics")
async def list_topics() -> list[TopicResponse]:
    """List all topics with document counts."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    topics = index.list_topics()

    result = []
    for t in topics:
        docs = index.list_documents(topic_filter=[t.id])
        entity_count = sum(1 for d in docs if d.id.startswith("entity:"))
        file_count = len(docs) - entity_count
        result.append(TopicResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            document_count=t.document_count,
            file_count=file_count,
            entity_count=entity_count,
        ))
    return result


@app.get("/library/topics/{topic_id}")
async def get_topic(topic_id: str) -> TopicDetailResponse:
    """Get a topic with its documents."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    topic = index.get_topic(topic_id)

    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Get documents for this topic
    docs = index.list_documents(topic_filter=[topic_id])

    entity_count = sum(1 for d in docs if d.id.startswith("entity:"))
    file_count = len(docs) - entity_count

    return TopicDetailResponse(
        id=topic.id,
        name=topic.name,
        description=topic.description,
        document_count=topic.document_count,
        file_count=file_count,
        entity_count=entity_count,
        documents=[
            TopicDocumentResponse(
                id=d.id,
                title=d.title,
                doc_type=d.doc_type,
                summary=d.summaries.brief,
                source="entity" if d.id.startswith("entity:") else "file",
            )
            for d in docs
        ],
    )


@app.post("/library/reindex")
async def reindex_library():
    """Re-run AI analysis on all completed library files that lack index data.

    This generates summaries and topics for files that were uploaded
    before the analysis step was added.
    """
    workspace = get_workspace_path()
    manager = LibraryManager(workspace)

    from .librarian import LibraryIndex, DocumentAnalyzer
    index = LibraryIndex(workspace)
    analyzer = DocumentAnalyzer()

    files = manager.list_files()
    results = {"indexed": 0, "skipped": 0, "failed": 0, "errors": [], "pruned": 0}

    # Prune stale library file entries from the index
    active_file_ids = {f.id for f in files}
    all_indexed = index.list_documents()
    for doc in all_indexed:
        if not doc.id.startswith("entity:") and doc.id not in active_file_ids:
            index.remove_document(doc.id)
            results["pruned"] += 1

    for lib_file in files:
        if lib_file.status != "complete":
            results["skipped"] += 1
            continue

        # Get extracted content
        extracted = manager.get_extracted_content(lib_file.id)
        if not extracted:
            results["skipped"] += 1
            continue

        # Check if already indexed (has summaries)
        existing = index.get_document(lib_file.id)
        needs_analysis = not existing or not existing.summaries.brief
        needs_entity = not lib_file.entity_id

        if not needs_analysis and not needs_entity:
            results["skipped"] += 1
            continue

        try:
            if needs_analysis:
                doc = analyzer.analyze_and_index(lib_file.id, extracted, lib_file.filename, index)
            else:
                doc = existing

            # Create workspace entity if missing
            if needs_entity and doc:
                entity_type = "documents"
                entity_id = manager._create_entity(
                    entity_type=entity_type,
                    title=doc.title,
                    content=extracted,
                    source_file=lib_file.id,
                    source_filename=lib_file.filename,
                )
                manager._update_file_entity(lib_file.id, entity_type, entity_id)

            results["indexed"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"file_id": lib_file.id, "filename": lib_file.filename, "error": str(e)})

    # Index workspace entities through the same pipeline
    entity_results = index.index_entities(analyzer)
    results["indexed"] += entity_results["indexed"]
    results["skipped"] += entity_results["skipped"]
    results["failed"] += entity_results["failed"]
    results["errors"].extend(entity_results["errors"])

    # Generate insights if documents were indexed
    if results["indexed"] > 0:
        try:
            all_docs = index.list_documents()
            if len(all_docs) >= 2:
                doc_briefs = [
                    {"id": d.id, "title": d.title, "brief": d.summaries.brief}
                    for d in all_docs if d.summaries.brief
                ]
                if len(doc_briefs) >= 2:
                    raw_insights = analyzer.generate_insights(doc_briefs)
                    insight_items = []
                    for raw in raw_insights:
                        from .librarian import InsightItem
                        import uuid as _uuid
                        insight_items.append(InsightItem(
                            id=_uuid.uuid4().hex,
                            type=raw.get("type", "connection"),
                            title=raw.get("title", ""),
                            description=raw.get("description", ""),
                            source_ids=raw.get("source_ids", []),
                            source_titles=raw.get("source_titles", []),
                            status="new",
                            created_at=datetime.utcnow().isoformat(),
                        ))
                    if insight_items:
                        index.add_insights(insight_items)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Insight generation failed: {e}")

        git_commit(Path(workspace), f"Library: reindex {results['indexed']} files")

    return results


@app.get("/library/entity-content/{entity_path:path}")
async def get_entity_content(entity_path: str) -> LibraryFileContentResponse:
    """Get the content of an entity-sourced indexed document."""
    workspace = Path(get_workspace_path())
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)

    doc_id = f"entity:{entity_path}"
    doc = index.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Entity not found in index")

    content = index.get_document_content(doc_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Entity file not found")

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
        id=doc_id,
        filename=doc.metadata.source_filename,
        content=content,
        summaries=summaries,
        topics=topics,
    )


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


# ============== Podcast Audio Endpoints ==============

class AudioGenerateRequest(BaseModel):
    """Request to generate podcast audio."""
    source_ids: list[str]
    title: str | None = None


class AudioGenerationResponse(BaseModel):
    """Audio generation metadata."""
    id: str
    title: str
    status: str
    source_ids: list[str]
    duration: float | None
    error: str | None
    created_at: str
    segment_count: int


@app.post("/library/audio/generate")
async def generate_audio(request: AudioGenerateRequest):
    """Generate podcast audio from sources (SSE stream)."""
    workspace = get_workspace_path()
    from .podcast import PodcastManager
    manager = PodcastManager(workspace)

    async def generate():
        async for event in manager.generate(request.source_ids, request.title):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/library/audio")
async def list_audio_generations() -> list[AudioGenerationResponse]:
    """List all audio generations."""
    workspace = get_workspace_path()
    from .podcast import PodcastManager
    manager = PodcastManager(workspace)
    generations = manager.list_generations()

    return [
        AudioGenerationResponse(
            id=g.id,
            title=g.title,
            status=g.status,
            source_ids=g.source_ids,
            duration=g.duration,
            error=g.error,
            created_at=g.created_at,
            segment_count=g.segment_count,
        )
        for g in generations
    ]


@app.get("/library/audio/{gen_id}")
async def get_audio_generation(gen_id: str) -> AudioGenerationResponse:
    """Get audio generation metadata."""
    workspace = get_workspace_path()
    from .podcast import PodcastManager
    manager = PodcastManager(workspace)
    gen = manager.get_generation(gen_id)

    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found")

    return AudioGenerationResponse(
        id=gen.id,
        title=gen.title,
        status=gen.status,
        source_ids=gen.source_ids,
        duration=gen.duration,
        error=gen.error,
        created_at=gen.created_at,
        segment_count=gen.segment_count,
    )


@app.get("/library/audio/{gen_id}/stream")
async def stream_audio(gen_id: str):
    """Stream the podcast MP3 file."""
    workspace = get_workspace_path()
    from .podcast import PodcastManager
    manager = PodcastManager(workspace)
    audio_path = manager.get_audio_path(gen_id)

    if not audio_path:
        raise HTTPException(status_code=404, detail="Audio not found or not ready")

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"podcast-{gen_id}.mp3",
    )


@app.delete("/library/audio/{gen_id}")
async def delete_audio_generation(gen_id: str):
    """Delete an audio generation."""
    workspace = get_workspace_path()
    from .podcast import PodcastManager
    manager = PodcastManager(workspace)

    if not manager.delete_generation(gen_id):
        raise HTTPException(status_code=404, detail="Generation not found")

    git_commit(Path(workspace), f"Library: delete podcast {gen_id}")
    return {"status": "deleted", "id": gen_id}


# ============== Topic Summary Endpoints ==============

class CollectionSummaryResponse(BaseModel):
    """Collection summary for a topic."""
    overview: str
    themes: list[str]
    key_findings: list[str]
    connections: str


@app.get("/library/topics/{topic_id}/summary")
async def get_topic_summary(topic_id: str) -> CollectionSummaryResponse:
    """Get or generate a topic summary."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    summary = index.get_topic_summary(topic_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Topic not found or no documents")

    return CollectionSummaryResponse(**summary)


@app.post("/library/topics/{topic_id}/summary")
async def regenerate_topic_summary(topic_id: str) -> CollectionSummaryResponse:
    """Force regenerate a topic summary."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    summary = index.regenerate_topic_summary(topic_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Topic not found or no documents")

    git_commit(Path(workspace), f"Library: regenerate topic summary {topic_id}")
    return CollectionSummaryResponse(**summary)


# ============== Insight Endpoints ==============

class InsightResponse(BaseModel):
    """Insight item for API."""
    id: str
    type: str
    title: str
    description: str
    source_ids: list[str]
    source_titles: list[str]
    status: str
    created_at: str


class InsightCountResponse(BaseModel):
    """Insight count response."""
    count: int


class UpdateInsightRequest(BaseModel):
    """Request to update insight status."""
    status: str


@app.get("/library/insights")
async def list_insights(status: str | None = None) -> list[InsightResponse]:
    """List insights with optional status filter."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    items = index.list_insights(status_filter=status)

    return [
        InsightResponse(
            id=i.id,
            type=i.type,
            title=i.title,
            description=i.description,
            source_ids=i.source_ids,
            source_titles=i.source_titles,
            status=i.status,
            created_at=i.created_at,
        )
        for i in items
    ]


@app.get("/library/insights/count")
async def get_insight_count() -> InsightCountResponse:
    """Get count of new insights."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    return InsightCountResponse(count=index.get_insight_count())


@app.patch("/library/insights/{insight_id}")
async def update_insight(insight_id: str, request: UpdateInsightRequest) -> InsightResponse:
    """Update an insight's status."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    item = index.update_insight(insight_id, request.status)

    if not item:
        raise HTTPException(status_code=404, detail="Insight not found")

    git_commit(Path(workspace), f"Library: update insight {insight_id}")

    return InsightResponse(
        id=item.id,
        type=item.type,
        title=item.title,
        description=item.description,
        source_ids=item.source_ids,
        source_titles=item.source_titles,
        status=item.status,
        created_at=item.created_at,
    )


# ============== Notebook endpoints ==============


class NotebookResponse(BaseModel):
    id: str
    title: str
    source_ids: list[str]
    source_labels: list[str]
    chat_session_id: str | None = None
    audio_generation_ids: list[str] = []
    created_at: str = ""
    updated_at: str = ""


class CreateNotebookRequest(BaseModel):
    title: str
    source_ids: list[str] = []
    source_labels: list[str] = []


class UpdateNotebookRequest(BaseModel):
    title: str | None = None
    source_ids: list[str] | None = None
    source_labels: list[str] | None = None
    chat_session_id: str | None = None
    audio_generation_ids: list[str] | None = None


@app.get("/library/notebooks")
async def list_notebooks() -> list[NotebookResponse]:
    """List all notebooks."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    notebooks = index.list_notebooks()
    return [NotebookResponse(**n.to_dict()) for n in notebooks]


@app.post("/library/notebooks")
async def create_notebook(request: CreateNotebookRequest) -> NotebookResponse:
    """Create a new notebook."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    notebook = index.create_notebook(request.title, request.source_ids, request.source_labels)
    git_commit(Path(workspace), f"Library: create notebook '{request.title}'")
    return NotebookResponse(**notebook.to_dict())


@app.get("/library/notebooks/{notebook_id}")
async def get_notebook(notebook_id: str) -> NotebookResponse:
    """Get a notebook by ID."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    notebook = index.get_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return NotebookResponse(**notebook.to_dict())


@app.patch("/library/notebooks/{notebook_id}")
async def update_notebook(notebook_id: str, request: UpdateNotebookRequest) -> NotebookResponse:
    """Update a notebook."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    notebook = index.update_notebook(notebook_id, **updates)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    git_commit(Path(workspace), f"Library: update notebook '{notebook.title}'")
    return NotebookResponse(**notebook.to_dict())


@app.delete("/library/notebooks/{notebook_id}")
async def delete_notebook(notebook_id: str):
    """Delete a notebook."""
    workspace = get_workspace_path()
    from .librarian import LibraryIndex
    index = LibraryIndex(workspace)
    if not index.delete_notebook(notebook_id):
        raise HTTPException(status_code=404, detail="Notebook not found")
    git_commit(Path(workspace), f"Library: delete notebook {notebook_id}")
    return {"ok": True}


def main():
    """Run the server."""
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
