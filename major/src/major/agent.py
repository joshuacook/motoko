"""Major chat agent - Claude Agent SDK wrapper for interactive conversations.

Major is a thin wrapper around the Claude Agent SDK that:
- Uses SDK session files as source of truth (via resume=session_id)
- Passes through SDK events with minimal transformation
- Handles AskUserQuestion via can_use_tool callback
- Manages MCP server configuration and skills syncing
"""

from collections.abc import AsyncGenerator, Callable, Awaitable
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import PermissionResultAllow

from .config import MajorConfig
from .prompt import build_system_prompt


@dataclass
class AskUserQuestionEvent:
    """Event emitted when agent asks user a question."""
    questions: list[dict]
    tool_use_id: str


# Type alias for SDK messages
SDKMessage = Any  # SystemMessage | AssistantMessage | UserMessage | ResultMessage | StreamEvent


class MajorAgent:
    """Chat agent using Claude Agent SDK with session persistence.

    SDK session files are the source of truth for conversation history.
    Use resume=session_id to continue conversations.
    """

    def __init__(
        self,
        config: MajorConfig | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize the agent.

        Args:
            config: Configuration for MCP loading and workspace validation.
                   Defaults to MajorConfig() with standard paths.
            model: Model to use for conversations.
        """
        self.config = config or MajorConfig()
        self.model = model

        # Pending AskUserQuestion - set when waiting for user answer
        self._pending_question: AskUserQuestionEvent | None = None
        self._answer_callback: Callable[[dict[str, str]], None] | None = None

    async def send_message(
        self,
        message: str,
        workspace_path: str,
        session_id: str | None = None,
        attached_entities: list[dict] | None = None,
        on_ask_user: Callable[[AskUserQuestionEvent], Awaitable[dict[str, str]]] | None = None,
    ) -> AsyncGenerator[SDKMessage, None]:
        """Send a message and yield SDK events.

        Args:
            message: User message to send
            workspace_path: Path to workspace
            session_id: Optional session ID to resume. If None, starts new session.
            attached_entities: Optional attached entities for system prompt
            on_ask_user: Optional async callback for AskUserQuestion. If provided,
                        will be called when agent asks a question and should return
                        answers as {question_text: answer}.

        Yields:
            Raw SDK messages (SystemMessage, AssistantMessage, UserMessage,
            ResultMessage, StreamEvent). Caller should check message types.
        """
        # Validate and normalize workspace
        workspace = self.config.validate_workspace(workspace_path)

        # Sync skills from platform/user to workspace
        self.config.sync_skills(workspace)

        # Load MCP servers
        mcp_servers = self.config.load_mcp_servers(workspace)

        # Build system prompt with app and workspace context
        system_prompt = build_system_prompt(
            attached_entities=attached_entities,
            platform_config_path=self.config.platform_config_path,
            workspace_path=workspace,
        )

        # Build tool list
        tools = ['AskUserQuestion'] if on_ask_user else None

        # Create can_use_tool handler if we have a callback
        can_use_tool = None
        if on_ask_user:
            async def handle_tool_permission(
                tool_name: str,
                tool_input: dict[str, Any],
                context: Any = None,
            ) -> PermissionResultAllow:
                if tool_name == 'AskUserQuestion':
                    questions = tool_input.get('questions', [])

                    # Create event and call user callback
                    event = AskUserQuestionEvent(
                        questions=questions,
                        tool_use_id=str(id(tool_input)),  # Unique ID
                    )
                    answers = await on_ask_user(event)

                    return PermissionResultAllow(
                        updated_input={
                            'questions': questions,
                            'answers': answers,
                        }
                    )

                return PermissionResultAllow(updated_input=tool_input)

            can_use_tool = handle_tool_permission

        # Configure SDK options
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=self.model,
            resume=session_id,  # SDK loads history from JSONL
            system_prompt=system_prompt,
            mcp_servers=mcp_servers if mcp_servers else None,
            tools=tools,
            can_use_tool=can_use_tool,
            include_partial_messages=True,  # SDK sends deltas
            permission_mode='bypassPermissions',
            setting_sources=["project"],  # Load skills from .claude/skills/
        )

        # Run query and yield events
        async with ClaudeSDKClient(options=options) as client:
            await client.query(message)

            async for msg in client.receive_response():
                yield msg

    def get_session_id_from_init(self, msg: SDKMessage) -> str | None:
        """Extract session_id from SystemMessage init event.

        Args:
            msg: SDK message to check

        Returns:
            Session ID if this is an init message, None otherwise
        """
        if hasattr(msg, 'subtype') and msg.subtype == 'init':
            if hasattr(msg, 'data') and msg.data:
                return msg.data.get('session_id')
        return None
