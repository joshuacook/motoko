"""Core Agent class for executing LLM loops with tools."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .models.base import BaseModel
from .skills.loader import SkillLoader
from .tasks.manager import TaskManager
from .tools.base import BaseTool
from .types import (
    Message,
    MessageRole,
    ModelResponse,
    Role,
    StopReason,
    StreamEvent,
    ToolDefinition,
    ToolResult,
    ToolUse,
    VerbosityLevel,
)


class Agent:
    """Agent that executes LLM loops with tool calling.

    The Agent manages the conversation loop, tool execution, and
    coordination between the model and tools. It provides the
    core agent loop from Claude Code but with model flexibility.
    """

    def __init__(
        self,
        model: BaseModel,
        tools: list[BaseTool] | None = None,
        workspace: str | Path | None = None,
        verbosity: VerbosityLevel = VerbosityLevel.NORMAL,
        skills_dir: str | Path | None = None,
    ):
        """Initialize Agent.

        Args:
            model: Model implementation to use
            tools: List of available tools
            workspace: Working directory for file operations
            verbosity: Default verbosity level for tool results
            skills_dir: Directory containing skill definitions (optional)
        """
        self.model = model
        self.tools = tools or []
        self.workspace = Path(workspace) if workspace else Path.cwd()
        self.verbosity = verbosity

        # Conversation state
        self.messages: list[Message] = []
        self.current_system_prompt: str | None = None

        # Tool registry
        self._tool_registry: dict[str, BaseTool] = {tool.name: tool for tool in self.tools}

        # Skills
        self.skill_loader = (
            SkillLoader(Path(skills_dir)) if skills_dir else SkillLoader()
        )
        self.skill_loader.load()

        # Role management
        self.roles: dict[str, Role] = {}  # Registered roles
        self.current_role: str | None = None  # Active role name
        self.role_history: list[tuple[str, str]] = []  # (role_name, system_prompt) history

        # Task management
        self.task_manager = TaskManager(self.workspace)
        self.tasks_context: str | None = None  # Cached task context for system prompt

        # Project context
        self.project_context: str | None = None  # Cached project context from context/README.md

    def chat(
        self,
        message: str,
        system_prompt: str | None = None,
        session_id: str | None = None,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> ModelResponse:
        """Send a message and get response.

        This is the main entry point for synchronous chat.
        Implements the agent loop: message → tool calls → results → response.

        Args:
            message: User message
            system_prompt: System prompt (role context)
            session_id: Session identifier
            max_iterations: Maximum tool calling iterations (default: 10)
            **kwargs: Additional model parameters

        Returns:
            ModelResponse with final response
        """
        # Initialize or load conversation history
        if session_id:
            # In a real implementation, we'd load from storage
            # For now, start fresh each time
            conversation: list[Message] = []
        else:
            conversation = []

        # Add user message
        conversation.append(Message(role=MessageRole.USER, content=message))

        # Update system prompt if provided
        if system_prompt:
            self.current_system_prompt = system_prompt

        # Get tool definitions
        tool_definitions = self._get_tool_definitions() if self.tools else None

        # Agent loop
        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            # Call model
            response = self.model.chat(
                messages=conversation,
                tools=tool_definitions,
                system=self.current_system_prompt,
                **kwargs,
            )

            # Check if model wants to use tools
            if response.has_tool_calls:
                # Add assistant's response (with tool calls) to conversation
                conversation.append(
                    Message(role=MessageRole.ASSISTANT, content=response.content)
                )

                # Execute tools
                tool_results = self._execute_tools(response.tool_calls)

                # Add tool results to conversation as user message
                conversation.append(Message(role=MessageRole.USER, content=tool_results))

                # Continue loop - model will see tool results
                continue
            else:
                # Model returned final response (no more tools)
                # Add to conversation history
                conversation.append(
                    Message(role=MessageRole.ASSISTANT, content=response.content)
                )

                # Store conversation if we have a session
                self.messages = conversation

                return response

        # If we hit max iterations, return last response
        # This is a safety mechanism
        return response

    async def stream(
        self,
        message: str,
        system_prompt: str | None = None,
        session_id: str | None = None,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Stream response with progressive updates.

        Args:
            message: User message
            system_prompt: System prompt (role context)
            session_id: Session identifier
            max_iterations: Maximum tool calling iterations (default: 10)
            **kwargs: Additional model parameters

        Yields:
            StreamEvent objects (TextChunk, ToolStart, ToolEnd, etc.)
        """
        from .types import DoneEvent, ErrorEvent, TextChunk, ToolEnd, ToolStart

        # Initialize conversation
        if session_id:
            conversation: list[Message] = []
        else:
            conversation = []

        # Add user message
        conversation.append(Message(role=MessageRole.USER, content=message))

        # Update system prompt if provided
        if system_prompt:
            self.current_system_prompt = system_prompt

        # Get tool definitions
        tool_definitions = self._get_tool_definitions() if self.tools else None

        # Agent loop
        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            try:
                # Stream from model
                async for event in self.model.stream(
                    messages=conversation,
                    tools=tool_definitions,
                    system=self.current_system_prompt,
                    **kwargs,
                ):
                    # Forward text chunks
                    if isinstance(event, TextChunk):
                        yield event

                    # Handle tool start
                    elif isinstance(event, ToolStart):
                        yield event

                        # Execute tool immediately
                        tool_result = self._execute_single_tool(event.data)

                        # Yield tool end event
                        yield ToolEnd(data=tool_result)

                        # Check if we should auto-prompt for verification
                        tool_name = event.data.name
                        tool_input = event.data.input
                        if tool_name == "write_file" and not tool_result.is_error:
                            # Check if it's executable code
                            file_path = tool_input.get("file_path", "")
                            if file_path.endswith((".py", ".sh", ".js", ".rb")):
                                # Inject a follow-up message to run the file
                                run_cmd = f"python {file_path}" if file_path.endswith(".py") else f"bash {file_path}"
                                # Add to conversation after current response
                                self._pending_followup = f"Now run {file_path} to verify it works using: {run_cmd}"

                    # Handle done event
                    elif isinstance(event, DoneEvent):
                        response = event.data

                        # Check if more tools needed
                        if response.has_tool_calls:
                            # Add assistant message to conversation
                            conversation.append(
                                Message(role=MessageRole.ASSISTANT, content=response.content)
                            )

                            # Execute remaining tools (if any weren't streamed)
                            tool_results = []
                            for tool_call in response.tool_calls:
                                result = self._execute_single_tool(tool_call)
                                tool_results.append(result)

                            # Add tool results to conversation
                            conversation.append(
                                Message(role=MessageRole.USER, content=tool_results)
                            )

                            # Continue loop - will call model again
                            break  # Break inner loop, continue outer while loop
                        else:
                            # Check if we have a pending follow-up
                            if hasattr(self, "_pending_followup") and self._pending_followup:
                                # Add assistant's response
                                conversation.append(
                                    Message(role=MessageRole.ASSISTANT, content=response.content)
                                )
                                # Add follow-up user message
                                conversation.append(
                                    Message(role=MessageRole.USER, content=self._pending_followup)
                                )
                                self._pending_followup = None
                                # Continue loop to handle follow-up
                                break
                            else:
                                # Final response - done
                                conversation.append(
                                    Message(role=MessageRole.ASSISTANT, content=response.content)
                                )
                                self.messages = conversation
                                yield DoneEvent(data=response)
                                return  # Exit completely

                    # Forward error events
                    elif isinstance(event, ErrorEvent):
                        yield event
                        return  # Stop on error

            except Exception as e:
                # Yield error and stop
                yield ErrorEvent(data=str(e))
                return

        # If we hit max iterations, yield done
        yield DoneEvent(
            data=ModelResponse(
                content=[],
                stop_reason=StopReason.MAX_TOKENS,
                model=self.model.model_name,
            )
        )

    def switch_role(self, new_system_prompt: str, role_name: str | None = None) -> None:
        """Switch to a different role mid-conversation.

        This preserves the conversation history but changes the system prompt
        for subsequent interactions. Useful for changing perspective or expertise
        mid-conversation.

        Args:
            new_system_prompt: New role context/system prompt
            role_name: Optional name for this role (for tracking)

        Example:
            agent.switch_role("You are a financial advisor", role_name="advisor")
            response = agent.chat("How should I invest?")
        """
        # Record the role change in history
        old_role = self.current_role or "default"
        old_prompt = self.current_system_prompt or ""

        if old_prompt:  # Don't record if this is the first role
            self.role_history.append((old_role, old_prompt))

        # Update to new role
        self.current_system_prompt = new_system_prompt
        self.current_role = role_name

    def add_role(
        self,
        role_name: str,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
        **metadata: Any
    ) -> None:
        """Add a role for multi-role conversations.

        Roles can have their own system prompts and tool access. This enables
        scenarios like having multiple specialized agents collaborating.

        Args:
            role_name: Unique name for the role
            system_prompt: Role context/system prompt
            tools: Role-specific tools (subset of agent's tools)
            **metadata: Additional role metadata

        Example:
            agent.add_role("artist_manager", "You are an artist manager...",
                          tools=[read_tool, write_tool])
            agent.add_role("booking_agent", "You are a booking agent...",
                          tools=[read_tool, web_tool])
        """
        # Get tool names
        tool_names = [tool.name for tool in (tools or [])]

        # Create and register role
        role = Role(
            name=role_name,
            system_prompt=system_prompt,
            tools=tool_names,
            metadata=metadata
        )
        self.roles[role_name] = role

    def chat_as(self, role_name: str, message: str, **kwargs: Any) -> ModelResponse:
        """Send message as a specific role.

        Temporarily switches to the specified role, sends the message, and
        returns the response. The message is tagged with the role name.

        Args:
            role_name: Name of role to use (must be registered with add_role)
            message: User message
            **kwargs: Additional arguments for chat()

        Returns:
            ModelResponse with response

        Raises:
            ValueError: If role not found

        Example:
            response = agent.chat_as("artist_manager", "What's the tour schedule?")
        """
        if role_name not in self.roles:
            raise ValueError(f"Role '{role_name}' not found. Use add_role() first.")

        role = self.roles[role_name]

        # Save current state
        original_role = self.current_role
        original_prompt = self.current_system_prompt
        original_tools = self._tool_registry.copy()

        try:
            # Switch to role
            self.current_role = role_name
            self.current_system_prompt = role.system_prompt

            # Filter tools to role-specific tools if specified
            if role.tools:
                self._tool_registry = {
                    name: tool for name, tool in original_tools.items()
                    if name in role.tools
                }

            # Send message (tagged with role)
            response = self.chat(message=message, system_prompt=role.system_prompt, **kwargs)

            # Tag the assistant's response with role
            if self.messages:
                self.messages[-1].role_name = role_name

            return response

        finally:
            # Restore original state
            self.current_role = original_role
            self.current_system_prompt = original_prompt
            self._tool_registry = original_tools

    async def stream_as(
        self, role_name: str, message: str, **kwargs: Any
    ) -> AsyncIterator[StreamEvent]:
        """Stream response as a specific role.

        Args:
            role_name: Name of role to use (must be registered with add_role)
            message: User message
            **kwargs: Additional arguments for stream()

        Yields:
            StreamEvent objects

        Raises:
            ValueError: If role not found

        Example:
            async for event in agent.stream_as("artist_manager", "What's next?"):
                print(event.data)
        """
        if role_name not in self.roles:
            raise ValueError(f"Role '{role_name}' not found. Use add_role() first.")

        role = self.roles[role_name]

        # Save current state
        original_role = self.current_role
        original_prompt = self.current_system_prompt
        original_tools = self._tool_registry.copy()

        try:
            # Switch to role
            self.current_role = role_name
            self.current_system_prompt = role.system_prompt

            # Filter tools to role-specific tools if specified
            if role.tools:
                self._tool_registry = {
                    name: tool for name, tool in original_tools.items()
                    if name in role.tools
                }

            # Stream message
            async for event in self.stream(message=message, system_prompt=role.system_prompt, **kwargs):
                yield event

            # Tag the assistant's response with role
            if self.messages:
                self.messages[-1].role_name = role_name

        finally:
            # Restore original state
            self.current_role = original_role
            self.current_system_prompt = original_prompt
            self._tool_registry = original_tools

    def list_roles(self) -> list[dict[str, Any]]:
        """List all registered roles.

        Returns:
            List of role information dictionaries
        """
        return [
            {
                "name": role.name,
                "system_prompt": role.system_prompt[:100] + "..."
                if len(role.system_prompt) > 100
                else role.system_prompt,
                "tools": role.tools,
                "metadata": role.metadata,
            }
            for role in self.roles.values()
        ]

    def get_role(self, role_name: str) -> Role | None:
        """Get a specific role by name.

        Args:
            role_name: Name of the role

        Returns:
            Role object if found, None otherwise
        """
        return self.roles.get(role_name)

    def remove_role(self, role_name: str) -> None:
        """Remove a role.

        Args:
            role_name: Name of role to remove

        Raises:
            ValueError: If role not found
        """
        if role_name not in self.roles:
            raise ValueError(f"Role '{role_name}' not found")

        del self.roles[role_name]

        # If this was the current role, clear it
        if self.current_role == role_name:
            self.current_role = None

    def invoke_skill(
        self, skill_name: str, system_prompt: str | None = None, **parameters: Any
    ) -> ModelResponse:
        """Invoke a skill with given parameters.

        Skills are specialized prompts with optional tool access. When invoked,
        the skill's instructions are formatted with the provided parameters and
        sent to the model.

        Args:
            skill_name: Name of the skill to invoke
            system_prompt: Optional system prompt to use (overrides current)
            **parameters: Parameters to pass to the skill

        Returns:
            ModelResponse from executing the skill

        Raises:
            ValueError: If skill not found or validation fails
        """
        skill = self.skill_loader.get(skill_name)

        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found")

        # Validate skill can be executed with available tools
        tool_names = [tool.name for tool in self.tools]
        is_valid, error_msg = self.skill_loader.validate(skill_name, tool_names)

        if not is_valid:
            raise ValueError(error_msg)

        # Format skill prompt with parameters
        skill_prompt = skill.format_prompt(**parameters)

        # Execute the skill using the chat method
        return self.chat(message=skill_prompt, system_prompt=system_prompt)

    async def invoke_skill_stream(
        self, skill_name: str, system_prompt: str | None = None, **parameters: Any
    ) -> AsyncIterator[StreamEvent]:
        """Invoke a skill with streaming response.

        Args:
            skill_name: Name of the skill to invoke
            system_prompt: Optional system prompt to use
            **parameters: Parameters to pass to the skill

        Yields:
            StreamEvent objects as the skill executes

        Raises:
            ValueError: If skill not found or validation fails
        """
        skill = self.skill_loader.get(skill_name)

        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found")

        # Validate skill
        tool_names = [tool.name for tool in self.tools]
        is_valid, error_msg = self.skill_loader.validate(skill_name, tool_names)

        if not is_valid:
            raise ValueError(error_msg)

        # Format skill prompt
        skill_prompt = skill.format_prompt(**parameters)

        # Stream the skill execution
        async for event in self.stream(message=skill_prompt, system_prompt=system_prompt):
            yield event

    def list_skills(self) -> list[dict[str, Any]]:
        """List all available skills.

        Returns:
            List of skill metadata dictionaries
        """
        return self.skill_loader.get_skill_definitions()

    def get_skill(self, name: str) -> Any | None:
        """Get a specific skill by name.

        Args:
            name: Skill name

        Returns:
            Skill object if found, None otherwise
        """
        return self.skill_loader.get(name)

    def reload_skills(self) -> None:
        """Reload all skills from disk.

        Useful for development when skills are being modified.
        """
        self.skill_loader.reload()

    def _get_tool_definitions(self) -> list[ToolDefinition]:
        """Get tool definitions for model.

        Returns:
            List of tool definitions
        """
        return [tool.get_definition() for tool in self.tools]

    def _execute_tools(self, tool_calls: list[ToolUse]) -> list[ToolResult]:
        """Execute multiple tools (in parallel if possible).

        Args:
            tool_calls: List of tool use requests

        Returns:
            List of tool results
        """

        results = []

        # For now, execute sequentially (parallel execution in future enhancement)
        for tool_call in tool_calls:
            try:
                result = self._execute_single_tool(tool_call)
                results.append(result)
            except Exception as e:
                # Create error result
                error_result = ToolResult(
                    tool_use_id=tool_call.id,
                    content=f"Error executing tool {tool_call.name}: {str(e)}",
                    is_error=True,
                )
                results.append(error_result)

        return results

    def _execute_single_tool(self, tool_call: ToolUse) -> ToolResult:
        """Execute a single tool.

        Args:
            tool_call: Tool use request

        Returns:
            ToolResult from execution
        """
        tool_name = tool_call.name

        if tool_name not in self._tool_registry:
            return ToolResult(
                tool_use_id=tool_call.id,
                content=f"Error: Tool not found: {tool_name}",
                is_error=True,
            )

        tool = self._tool_registry[tool_name]

        try:
            # Execute tool with parameters
            result = tool.execute(**tool_call.input)

            # Set tool_use_id for tracking
            result.tool_use_id = tool_call.id

            # Format based on verbosity
            result.content = result.format(self.verbosity)

            return result

        except Exception as e:
            return ToolResult(
                tool_use_id=tool_call.id,
                content=f"Error executing {tool_name}: {str(e)}",
                is_error=True,
            )

    def load_tasks_context(self, limit: int = 10) -> str:
        """Load task context for system prompt.

        Args:
            limit: Maximum number of open tasks to load

        Returns:
            Formatted task summary
        """
        summary = self.task_manager.get_open_tasks_summary(limit=limit)
        self.tasks_context = summary
        return summary

    def get_tasks_for_prompt(self) -> str:
        """Get task context to inject into system prompt.

        Returns:
            Task context string or empty string if no tasks
        """
        if self.tasks_context:
            return f"\n\n## Current Tasks\n\n{self.tasks_context}"
        return ""

    def load_project_context(self) -> str | None:
        """Load project context from context/README.md.

        Returns:
            Project context content or None if file doesn't exist
        """
        context_file = self.workspace / "context" / "README.md"
        if context_file.exists():
            self.project_context = context_file.read_text()
            return self.project_context
        return None

    def get_project_context_for_prompt(self) -> str:
        """Get project context to inject into system prompt.

        Returns:
            Project context string or empty string if no context
        """
        if self.project_context:
            return f"\n\n## Project Context\n\n{self.project_context}"
        return ""

    def reset(self) -> None:
        """Reset conversation state."""
        self.messages = []
        self.current_system_prompt = None

    def __repr__(self) -> str:
        """String representation of agent."""
        return (
            f"Agent(model={self.model.model_name}, "
            f"tools={len(self.tools)}, "
            f"workspace={self.workspace})"
        )
