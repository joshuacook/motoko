"""Motoko web chat interface - FastAPI backend."""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from agent import MotokoWebAgent
from auth import create_access_token, get_current_user, verify_password
from database import Database

# Environment configuration
WORKSPACE_PATH = Path(os.getenv("WORKSPACE_PATH", "/workspace"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "/data/conversations.db"))
PASSWORD_HASH = os.getenv("PASSWORD_HASH", "")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")

# Initialize app
app = FastAPI(title="Motoko Chat")

# Initialize database
db = Database(DATABASE_PATH)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the chat interface."""
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/login")
async def login(request: Request):
    """Authenticate user and return JWT token."""
    data = await request.json()
    password = data.get("password", "")

    if not PASSWORD_HASH:
        return {"error": "Authentication not configured"}, 500

    if verify_password(password, PASSWORD_HASH):
        token = create_access_token({"sub": "user"}, JWT_SECRET)
        return {"token": token}

    return {"error": "Invalid credentials"}, 401


@app.get("/api/stream")
async def stream_chat(request: Request):
    """Stream motoko chat responses via SSE."""
    # Verify authentication
    user = await get_current_user(request, JWT_SECRET)
    if not user:
        return {"error": "Unauthorized"}, 401

    # Get parameters
    message = request.query_params.get("message", "")
    conversation_id = request.query_params.get("conversation_id")
    model = request.query_params.get("model", "claude-sonnet-4")

    if not message:
        return {"error": "No message provided"}, 400

    # Get or create conversation
    if conversation_id:
        conversation = db.get_conversation(int(conversation_id))
        if not conversation:
            return {"error": "Conversation not found"}, 404
    else:
        conversation_id = db.create_conversation(title=message[:50])

    # Store user message
    db.add_message(conversation_id, "user", message)

    # Initialize motoko agent
    agent = MotokoWebAgent(
        workspace=WORKSPACE_PATH,
        model=model,
    )

    # Stream response
    async def generate():
        """Generate SSE events from motoko agent."""
        full_response = ""

        try:
            async for event in agent.stream(message):
                if event["type"] == "text":
                    full_response += event["data"]
                    yield {
                        "event": "message",
                        "data": event["data"]
                    }

                elif event["type"] == "tool_use":
                    yield {
                        "event": "tool",
                        "data": event["data"]
                    }

                elif event["type"] == "error":
                    yield {
                        "event": "error",
                        "data": event["data"]
                    }

            # Store assistant response
            if full_response:
                db.add_message(conversation_id, "assistant", full_response)

                # Update conversation with token count
                total_tokens = agent.get_token_count()
                db.update_conversation_tokens(conversation_id, total_tokens)

            yield {
                "event": "done",
                "data": {
                    "conversation_id": conversation_id,
                    "tokens": agent.get_token_count()
                }
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": str(e)
            }

    return EventSourceResponse(generate())


@app.get("/api/conversations")
async def list_conversations(request: Request):
    """List all conversations."""
    user = await get_current_user(request, JWT_SECRET)
    if not user:
        return {"error": "Unauthorized"}, 401

    conversations = db.list_conversations()
    return {"conversations": conversations}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, request: Request):
    """Get conversation with messages."""
    user = await get_current_user(request, JWT_SECRET)
    if not user:
        return {"error": "Unauthorized"}, 401

    conversation = db.get_conversation(conversation_id)
    if not conversation:
        return {"error": "Conversation not found"}, 404

    messages = db.get_messages(conversation_id)
    return {
        "conversation": conversation,
        "messages": messages
    }


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, request: Request):
    """Delete a conversation."""
    user = await get_current_user(request, JWT_SECRET)
    if not user:
        return {"error": "Unauthorized"}, 401

    db.delete_conversation(conversation_id)
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
