"""Motoko agent wrapper for web interface."""

from pathlib import Path
from typing import AsyncGenerator

from motoko import Agent, create_model
from motoko.tools import (
    BashTool,
    GlobTool,
    GrepTool,
    ReadFileTool,
    WriteFileTool,
)


class MotokoWebAgent:
    """Web-friendly wrapper for Motoko Agent."""

    def __init__(self, workspace: Path, model: str = "claude-sonnet-4"):
        """Initialize motoko agent for web use.

        Args:
            workspace: Workspace directory path
            model: Model name (claude-sonnet-4, gemini-2-flash-preview, etc.)
        """
        self.workspace = Path(workspace)
        self.model_name = model

        # Create model
        self.model = create_model(model)

        # Set up tools
        self.tools = [
            ReadFileTool(workspace=self.workspace),
            WriteFileTool(workspace=self.workspace),
            GlobTool(workspace=self.workspace),
            GrepTool(workspace=self.workspace),
            BashTool(workspace=self.workspace),
        ]

        # Create agent
        self.agent = Agent(
            model=self.model,
            tools=self.tools,
            workspace=self.workspace,
        )

        # Load project context
        project_context = self.agent.get_project_context_for_prompt()
        tasks_context = self.agent.get_tasks_for_prompt()

        # Build system prompt
        default_system_prompt = """You are Motoko, a helpful AI assistant for project and task management.

IMPORTANT: Always respond with text first, then use tools if needed.

Be natural and engaging:
- Acknowledge user requests before taking action
- Respond to casual conversation naturally
- Ask follow-up questions when appropriate
- Keep responses concise and friendly

When the user has a task or request:
- First acknowledge and clarify what they want
- Ask questions about details, scope, or preferences
- Use tools AFTER discussing the approach
- Work collaboratively, not autonomously
- Check in frequently for feedback

You have these tools available:
- write_file: Create/edit files
- read_file: Read file contents
- glob: Find files
- grep: Search in files
- bash: Run commands

## Task Management

This workspace uses a task management system. Tasks are stored in `data/tasks/` directory as markdown files.

**IMPORTANT: You already have the current task list loaded in your context below. DO NOT use glob or grep to list tasks - just reference what you already know.**

File naming convention:
- Open: `000001-PROJECT-task-name.md`
- Completed: `000001-COMPLETED-PROJECT-task-name.md`
- Cancelled/Won't Do: `000001-CANCELLED-PROJECT-task-name.md`
- Use 6-digit zero-filled numbers (000001, 000002, not 01, 02)

Task operations - BE DECISIVE:

**CRITICAL: Use ONE bash command with all renames chained together using && to complete the entire action atomically!**

Example - user says "011 and 012 are done, 016 and 017 won't be done":

  Say: "Marking 11 and 12 as complete, and cancelling 16 and 17."

  Then use ONE bash command:
    bash: mv data/tasks/000011-PROJECT-task-1.md data/tasks/000011-COMPLETED-PROJECT-task-1.md && \\
          mv data/tasks/000012-PROJECT-task-2.md data/tasks/000012-COMPLETED-PROJECT-task-2.md && \\
          mv data/tasks/000016-PROJECT-task-3.md data/tasks/000016-CANCELLED-PROJECT-task-3.md && \\
          mv data/tasks/000017-PROJECT-task-4.md data/tasks/000017-CANCELLED-PROJECT-task-4.md

  Then say: "Done! All tasks updated."

Use && to chain commands so they all execute in ONE bash call. If any fails, the rest won't run.

Be conversational but DECISIVE - take action immediately when told.

Be helpful, conversational, and collaborative."""

        # Set system prompt with context
        self.agent.current_system_prompt = (
            default_system_prompt + project_context + tasks_context
        )

    async def stream(self, message: str) -> AsyncGenerator[dict, None]:
        """Stream response from agent.

        Args:
            message: User message

        Yields:
            Event dictionaries with type and data
        """
        try:
            async for event in self.agent.stream(message=message):
                if event.type == "text_chunk":
                    yield {
                        "type": "text",
                        "data": event.data
                    }

                elif event.type == "tool_start":
                    tool = event.data
                    yield {
                        "type": "tool_use",
                        "data": {
                            "name": tool.name,
                            "input": tool.input
                        }
                    }

                elif event.type == "tool_end":
                    result = event.data
                    yield {
                        "type": "tool_result",
                        "data": {
                            "content": result.content,
                            "is_error": result.is_error
                        }
                    }

                elif event.type == "error":
                    yield {
                        "type": "error",
                        "data": str(event.data)
                    }

        except Exception as e:
            yield {
                "type": "error",
                "data": str(e)
            }

    def get_token_count(self) -> int:
        """Get total token count for conversation.

        Returns:
            Total tokens used
        """
        # Estimate based on message count
        # TODO: Implement proper token counting
        return len(self.agent.messages) * 100
