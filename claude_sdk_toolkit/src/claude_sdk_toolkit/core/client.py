"""Core Claude SDK client wrapper with enhanced functionality."""

from pathlib import Path
from typing import Any, Callable, Optional

try:
    from claude_agent_sdk import (
        ClaudeSDKClient as OriginalClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        ToolUseBlock,
        TextBlock,
        ToolResultBlock,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    # Create stub classes for type hints when SDK not available
    ClaudeAgentOptions = Any
    AssistantMessage = Any
    ResultMessage = Any
    ToolUseBlock = Any
    TextBlock = Any
    ToolResultBlock = Any


class ClaudeClient:
    """Enhanced wrapper around ClaudeSDKClient with additional features."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        working_dir: Optional[Path] = None,
        tools: Optional[list[str]] = None,
        permission_mode: str = "default",
        on_message_callback: Optional[Callable] = None,
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key
            model: Model name to use
            working_dir: Working directory for file operations
            tools: List of enabled tool names
            permission_mode: Permission mode (default, acceptEdits, bypassPermissions)
            on_message_callback: Callback function for streaming messages
        """
        if not SDK_AVAILABLE:
            raise RuntimeError(
                "claude_agent_sdk not installed. "
                "Install with: pip install claude-agent-sdk"
            )

        self.api_key = api_key
        self.model = model
        self.working_dir = working_dir or Path.cwd()
        self.tools = tools or ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
        self.permission_mode = permission_mode
        self.on_message_callback = on_message_callback

        self._client: Optional[OriginalClaudeSDKClient] = None
        self._conversation_history: list[dict] = []

    def _create_client(self) -> OriginalClaudeSDKClient:
        """Create a new SDK client with current options."""
        options = ClaudeAgentOptions(
            cwd=str(self.working_dir),
            tools=self.tools,
            permissionMode=self.permission_mode,
        )

        return OriginalClaudeSDKClient(
            api_key=self.api_key,
            model=self.model,
            agent_options=options,
        )

    def get_client(self) -> OriginalClaudeSDKClient:
        """Get or create the SDK client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def reset_session(self):
        """Reset the current session and start fresh."""
        self._client = None
        self._conversation_history.clear()

    def update_settings(
        self,
        working_dir: Optional[Path] = None,
        tools: Optional[list[str]] = None,
        permission_mode: Optional[str] = None,
    ):
        """Update client settings and reset session."""
        if working_dir is not None:
            self.working_dir = working_dir
        if tools is not None:
            self.tools = tools
        if permission_mode is not None:
            self.permission_mode = permission_mode

        # Reset to apply new settings
        self.reset_session()

    async def send_message(
        self,
        message: str,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, list[dict]]:
        """
        Send a message to Claude and get response.

        Args:
            message: User message to send
            system_prompt: Optional system prompt to prepend

        Returns:
            Tuple of (response_text, tool_uses)
        """
        client = self.get_client()

        # Build full message with system prompt if provided
        full_message = message
        if system_prompt:
            full_message = f"{system_prompt}\n\n{message}"

        # Track tool uses
        tool_uses = []
        response_text = []

        # Send message and stream response
        async for chunk in client.generate_stream(full_message):
            if isinstance(chunk, AssistantMessage):
                # Process assistant message
                for block in chunk.content:
                    if isinstance(block, TextBlock):
                        text = block.text
                        response_text.append(text)
                        if self.on_message_callback:
                            self.on_message_callback("text", text)

                    elif isinstance(block, ToolUseBlock):
                        tool_info = {
                            "name": block.name,
                            "input": block.input,
                            "id": block.id,
                        }
                        tool_uses.append(tool_info)
                        if self.on_message_callback:
                            self.on_message_callback("tool_use", tool_info)

            elif isinstance(chunk, ResultMessage):
                # Process tool results
                for block in chunk.content:
                    if isinstance(block, ToolResultBlock):
                        result_info = {
                            "tool_use_id": block.tool_use_id,
                            "content": block.content,
                            "is_error": block.is_error,
                        }
                        if self.on_message_callback:
                            self.on_message_callback("tool_result", result_info)

        # Store in conversation history
        self._conversation_history.append({
            "role": "user",
            "content": message,
        })
        self._conversation_history.append({
            "role": "assistant",
            "content": "".join(response_text),
            "tool_uses": tool_uses,
        })

        return "".join(response_text), tool_uses

    async def send_message_simple(self, message: str) -> str:
        """
        Send a message and return just the text response.

        Args:
            message: User message to send

        Returns:
            Response text
        """
        response, _ = await self.send_message(message)
        return response

    def get_conversation_history(self) -> list[dict]:
        """Get the conversation history."""
        return self._conversation_history.copy()

    def clear_conversation_history(self):
        """Clear the conversation history."""
        self._conversation_history.clear()

    @property
    def is_initialized(self) -> bool:
        """Check if client has been initialized."""
        return self._client is not None
