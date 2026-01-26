"""HTTP server for Major chat agent."""

import asyncio
import os
import json
import re
import subprocess
import yaml
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import MajorAgent
from .config import MajorConfig
from .sessions import session_manager, SessionMetadata


app = FastAPI(title="Major Chat Agent", version="0.1.0")


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

    return ChatResponse(
        session_id=session_id or "unknown",
        response=full_response,
    )


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
    return {"status": "deleted", "session_id": session_id}


def main():
    """Run the server."""
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
