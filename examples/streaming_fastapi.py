"""FastAPI integration example with SSE streaming.

Run with: uvicorn streaming_fastapi:app --reload
Then open http://localhost:8000/static/chat.html in browser
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from motoko import Agent, create_model, ReadFileTool, GlobTool
from motoko.streaming import create_sse_response_fastapi

app = FastAPI(title="Motoko Streaming Demo")

# Global agent instance
workspace = Path.cwd()
model = create_model("claude-3-5-sonnet-20241022")
tools = [
    ReadFileTool(workspace=workspace),
    GlobTool(workspace=workspace),
]
agent = Agent(model=model, tools=tools, workspace=workspace)


class ChatRequest(BaseModel):
    """Chat request model."""

    message: str
    system_prompt: Optional[str] = "You are a helpful assistant."


@app.post("/stream")
async def stream_chat(request: ChatRequest):
    """Stream chat response with SSE.

    Example curl:
        curl -X POST http://localhost:8000/stream \\
             -H "Content-Type: application/json" \\
             -d '{"message":"Hello!"}'
    """
    # Create event stream
    event_stream = agent.stream(
        message=request.message, system_prompt=request.system_prompt
    )

    # Return SSE response
    return StreamingResponse(
        create_sse_response_fastapi(event_stream), media_type="text/event-stream"
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model": agent.model.model_name, "tools": len(agent.tools)}


# Example HTML client
HTML_CLIENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Motoko Streaming Chat</title>
    <style>
        body {
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            background: #1a1a1a;
            color: #e0e0e0;
        }
        #messages {
            border: 1px solid #333;
            padding: 20px;
            min-height: 400px;
            margin-bottom: 20px;
            background: #2a2a2a;
            border-radius: 8px;
        }
        .message {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 4px;
        }
        .user { background: #1a3a5a; }
        .assistant { background: #2a4a2a; }
        .tool { background: #4a3a1a; font-size: 0.9em; }
        input {
            width: 70%;
            padding: 10px;
            background: #2a2a2a;
            border: 1px solid #444;
            color: #e0e0e0;
            border-radius: 4px;
        }
        button {
            padding: 10px 20px;
            background: #4a7c59;
            border: none;
            color: white;
            cursor: pointer;
            border-radius: 4px;
        }
        button:hover { background: #5a8c69; }
    </style>
</head>
<body>
    <h1>Motoko Streaming Chat</h1>
    <div id="messages"></div>
    <input type="text" id="input" placeholder="Type a message..." />
    <button onclick="sendMessage()">Send</button>

    <script>
        const messagesDiv = document.getElementById('messages');
        const input = document.getElementById('input');

        async function sendMessage() {
            const message = input.value;
            if (!message) return;

            // Add user message
            addMessage('user', message);
            input.value = '';

            // Create assistant message container
            const assistantMsg = addMessage('assistant', '');

            // Stream response
            const response = await fetch('/stream', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message})
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const {done, value} = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, {stream: true});
                const events = buffer.split('\\n\\n');
                buffer = events.pop();

                for (const event of events) {
                    if (!event.trim()) continue;

                    const lines = event.split('\\n');
                    let eventType, eventData;

                    for (const line of lines) {
                        if (line.startsWith('event:')) {
                            eventType = line.slice(6).trim();
                        } else if (line.startsWith('data:')) {
                            eventData = JSON.parse(line.slice(5).trim());
                        }
                    }

                    if (eventType === 'text_chunk') {
                        assistantMsg.textContent += eventData.data;
                    } else if (eventType === 'tool_start') {
                        addMessage('tool', `[Using ${eventData.data.name}]`);
                    } else if (eventType === 'tool_end') {
                        if (eventData.data.is_error) {
                            addMessage('tool', `[Error: ${eventData.data.content}]`);
                        }
                    }
                }
            }
        }

        function addMessage(role, content) {
            const div = document.createElement('div');
            div.className = `message ${role}`;
            div.textContent = content;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            return div;
        }

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
"""


@app.get("/")
async def root():
    """Serve HTML client."""
    from fastapi.responses import HTMLResponse

    return HTMLResponse(content=HTML_CLIENT)


if __name__ == "__main__":
    import uvicorn

    print("Starting Motoko Streaming Demo...")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000)
