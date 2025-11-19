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
    bash: mv data/tasks/000011-GEORGIA_TECH-ai-assignment-5.md data/tasks/000011-COMPLETED-GEORGIA_TECH-ai-assignment-5.md && \
          mv data/tasks/000012-GEORGIA_TECH-ml-quiz-nov-10.md data/tasks/000012-COMPLETED-GEORGIA_TECH-ml-quiz-nov-10.md && \
          mv data/tasks/000016-JJOSHUAGUA-develop-recording-process.md data/tasks/000016-CANCELLED-JJOSHUAGUA-develop-recording-process.md && \
          mv data/tasks/000017-JJOSHUAGUA-continue-developing-algorithms.md data/tasks/000017-CANCELLED-JJOSHUAGUA-continue-developing-algorithms.md

  Then say: "Done! All tasks updated."

Use && to chain commands so they all execute in ONE bash call. If any fails, the rest won't run.

Be conversational but DECISIVE - take action immediately when told.

Be helpful, conversational, and collaborative."""

    agent = Agent(
        model=model_obj,
        tools=tool_list,
        workspace=workspace_path,
    )

    # Load project context
    project_context_content = agent.load_project_context()
    project_context = agent.get_project_context_for_prompt()

    # Load tasks and update system prompt
    tasks_summary = agent.load_tasks_context(limit=10)
    tasks_context = agent.get_tasks_for_prompt()

    # Update system prompt with project context and task context
    agent.current_system_prompt = default_system_prompt + project_context + tasks_context

    # Discover available roles from roles/ directory
    available_roles = agent.discover_roles()

    # Show project context to user if it exists
    if project_context_content:
        print_system(f"\n📋 Loaded project context from context/README.md\n")

    # Show available roles if any exist
    if available_roles:
        print_system(f"🎭 Available roles: {', '.join(available_roles)}")
        print_system(f"   Use /role <name> to switch roles\n")

    # Show tasks to user if any exist
    if tasks_summary and "No open tasks" not in tasks_summary:
        print_system(f"{tasks_summary}\n")

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
            # Try to get existing role
            role = agent.get_role(role_name)

            # If not found, try loading from file
            if not role:
                if agent.load_role_from_file(role_name):
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
