"""Interactive chat command - Claude Code style."""

import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from motoko import Agent, create_model
from motoko.tools import (
    BashTool,
    GlobTool,
    GrepTool,
    ReadFileTool,
    WriteFileTool,
)

from .formatting import (
    end_tool_execution,
    formatter,
    print_error,
    print_help,
    print_response_chunk,
    print_response_end,
    print_response_start,
    print_session_info,
    print_system,
    print_task,
    print_welcome,
    start_tool_execution,
)


def chat_command(
    model: str,
    workspace: str | None,
    tools: str | None,
    all_tools: bool,
    temperature: float | None,
    stream: bool,
):
    """Run interactive chat session - Claude Code style."""
    # Print welcome
    print_welcome()

    # Create model
    try:
        model_kwargs = {}
        if temperature is not None:
            model_kwargs["temperature"] = temperature

        model_obj = create_model(model, **model_kwargs)
    except Exception as e:
        print_error(f"Failed to create model: {e}")
        sys.exit(1)

    # Set up workspace
    if workspace:
        workspace_path = Path(workspace).expanduser().resolve()
    else:
        workspace_path = Path.cwd()

    # Set up tools
    tool_list = []
    tools_enabled = False
    if all_tools or tools:
        tools_enabled = True
        # Add file tools
        tool_list.extend([
            ReadFileTool(workspace=workspace_path),
            WriteFileTool(workspace=workspace_path),
            GlobTool(workspace=workspace_path),
            GrepTool(workspace=workspace_path),
            BashTool(workspace=workspace_path),
        ])

    # Print session info
    print_session_info(model, str(workspace_path), tools_enabled)

    # Create agent with conversational system prompt
    default_system_prompt = """You are a helpful, conversational AI assistant.

IMPORTANT: Always respond with text first, then use tools if needed.

Be natural and engaging:
- Acknowledge user requests before taking action
- Respond to casual conversation naturally
- Ask follow-up questions when appropriate
- Show interest in what the user shares
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

This workspace uses a task management system. Tasks are stored in `tasks/` directory as markdown files:
- Format: `000001-task-name.md` → `000001-COMPLETED-task-name.md` when done
- Use 6-digit zero-filled numbers (000001, 000002, not 01, 02)

To work with tasks naturally:
  - List tasks: Read files from tasks/ directory
  - Create task: First ask for details, then use write_file to create numbered markdown file
  - Work on task: Read specific task file and discuss approach
  - Complete task: Use bash to rename file, adding -COMPLETED- after number

Example creating a task:
  User: "Create a task for X"
  You: "Sure! Let me ask a few questions: [ask about scope, details]. I'll create task 000004-x.md"
  Then use write_file to create: tasks/000004-task-name.md

Be conversational and collaborative about task management.

Be helpful, conversational, and collaborative."""

    agent = Agent(
        model=model_obj,
        tools=tool_list,
        workspace=workspace_path,
    )

    # Load tasks and update system prompt
    tasks_summary = agent.load_tasks_context(limit=10)
    tasks_context = agent.get_tasks_for_prompt()

    # Update system prompt with task context
    agent.current_system_prompt = default_system_prompt + tasks_context

    # Show tasks to user if any exist
    if tasks_summary and "No open tasks" not in tasks_summary:
        print_system(f"\n{tasks_summary}\n")

    # Preload starter roles for common use cases
    agent.add_role(
        "artist-manager",
        """You are an artist management assistant helping with booking, contracts,
tour planning, press materials, and financial tracking. Be collaborative - ask questions
about the artist's needs before creating materials. Work incrementally with user approval."""
    )

    agent.add_role(
        "educator",
        """You are an educational assistant helping with lesson planning, curriculum
development, student feedback, and course materials. Ask about learning objectives,
student level, and context before creating materials. Work step-by-step with teacher input."""
    )

    agent.add_role(
        "project-manager",
        """You are a project management assistant helping with proposals, planning,
status reports, and stakeholder communication. Ask about project scope, timeline, and
stakeholders before creating documents. Build collaboratively with frequent check-ins."""
    )

    # Create prompt session
    session: PromptSession = PromptSession(history=InMemoryHistory())

    # Main chat loop
    while True:
        try:
            # Get user input
            user_input = session.prompt("\n> ", multiline=False)

            # Skip empty input
            if not user_input.strip():
                continue

            # Handle special commands
            if user_input.startswith("/"):
                if handle_command(user_input, agent, model):
                    break  # Exit if command returns True
                continue

            # Reset tool counter for new request
            formatter.tool_count = 0

            # Print task in panel
            print_task(user_input)

            # Get response
            if stream:
                handle_streaming_response(agent, user_input)
            else:
                handle_sync_response(agent, user_input)

        except KeyboardInterrupt:
            print_system("\n\nGoodbye!")
            break
        except EOFError:
            print_system("\n\nGoodbye!")
            break
        except Exception as e:
            print_error(f"Error: {e}")
            import traceback
            traceback.print_exc()


def handle_sync_response(agent: Agent, message: str):
    """Handle non-streaming response."""
    try:
        response = agent.chat(message=message)
        print_response_start()
        print_response_chunk(response.text)
        print_response_end()
    except Exception as e:
        print_error(f"Failed to get response: {e}")


def handle_streaming_response(agent: Agent, message: str):
    """Handle streaming response - Claude Code style."""
    import asyncio

    async def stream_response():
        try:
            response_started = False

            async for event in agent.stream(message=message):
                if event.type == "text_chunk":
                    # Start response section if not started
                    if not response_started:
                        print_response_start()
                        response_started = True
                    print_response_chunk(event.data)

                elif event.type == "tool_start":
                    tool = event.data
                    start_tool_execution(tool.name, tool.input)

                elif event.type == "tool_end":
                    result = event.data
                    end_tool_execution(
                        result.tool_use_id,
                        result.content,
                        result.is_error
                    )

                elif event.type == "error":
                    print_error(f"Stream error: {event.data}")

                elif event.type == "done":
                    if response_started:
                        print_response_end()

        except Exception as e:
            print_error(f"Streaming failed: {e}")
            import traceback
            traceback.print_exc()

    # Run async stream
    asyncio.run(stream_response())


def handle_command(command: str, agent: Agent, current_model: str) -> bool:
    """Handle special CLI commands.

    Returns:
        True if should exit, False otherwise
    """
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()

    if cmd in ["/exit", "/quit"]:
        print_system("\nGoodbye!")
        return True

    elif cmd == "/help":
        print_help()
        return False

    elif cmd == "/clear":
        agent.messages.clear()
        print_system("✓ Conversation history cleared")
        return False

    elif cmd == "/roles":
        roles = agent.list_roles()
        if roles:
            print_system("\nAvailable roles:")
            for role in roles:
                current = " (current)" if role["name"] == agent.current_role else ""
                print_system(f"  • {role['name']}{current}")
        else:
            print_system("No roles defined yet")
        return False

    elif cmd == "/role":
        if len(parts) < 2:
            print_error("Usage: /role <role-name>")
            return False

        role_name = parts[1]
        try:
            role = agent.get_role(role_name)
            if role:
                agent.switch_role(role.system_prompt, role_name=role_name)
                print_system(f"✓ Switched to role: {role_name}")
            else:
                print_error(f"Role '{role_name}' not found. Use /roles to see available roles.")
        except Exception as e:
            print_error(f"Failed to switch role: {e}")
        return False

    elif cmd == "/model":
        if len(parts) < 2:
            print_error("Usage: /model <model-name>")
            print_system("Example: /model gemini-3-pro-preview")
            return False

        new_model_name = parts[1]
        try:
            new_model = create_model(new_model_name)
            agent.model = new_model
            print_system(f"✓ Switched to model: {new_model_name}")
        except Exception as e:
            print_error(f"Failed to switch model: {e}")
        return False

    else:
        print_error(f"Unknown command: {cmd}")
        print_system("Type /help for available commands")
        return False
