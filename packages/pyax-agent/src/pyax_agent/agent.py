"""Core agent loop using the Claude Agent SDK.

The SDK handles:
  - Tool dispatch via in-process MCP servers
  - Authentication via Claude Code CLI (~/.claude, no ANTHROPIC_API_KEY needed)
  - Multi-turn conversation with automatic tool_use → call → result loops

We wrap the SDK's query() to emit SSE events for the Swift frontend.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from pyax_agent.bridge_client import BridgeClient
from pyax_agent.config import AgentConfig
from pyax_agent.event_emitter import EventEmitter
from pyax_agent.models.sse import (
    DoneEvent,
    ErrorEvent,
    MessageEvent,
    SSEEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from pyax_agent.tools.registry import TOOL_NAMES, create_mcp_server

logger = logging.getLogger(__name__)

# System prompt for the accessibility agent.
# Tool names, descriptions, and input schemas are injected automatically by the
# MCP protocol — Claude sees every @tool decorator's metadata via the tool
# catalog. The system prompt only needs to define *who the agent is* and *how
# it should behave*.
SYSTEM_PROMPT = """\
You are an accessibility assistant that helps disabled users interact with \
macOS applications. You have tools to inspect UI elements, perform actions, \
provide visual feedback, and capture screenshots — their names and schemas \
are provided via the tool catalog.

## Guidelines

- Start by inspecting the UI tree to understand the current layout
- Search for elements by role, title, or value when targeting specific UI
- Always verify an action succeeded by checking the UI state afterward
- Highlight elements before interacting with them so the user sees your target
- Speak actions aloud when the user relies on voice output
- Use screenshots only when visual context is needed (images, colors, layout)
- Be concise but clear in your responses
- If you can't find an element, explain what you see instead
"""


class AgentLoop:
    """Runs the Claude Agent SDK loop.

    Each call to `run()` processes a user message through Claude,
    executing tools as needed, and yields SSE events for streaming.
    """

    def __init__(
        self,
        config: AgentConfig,
        bridge: BridgeClient,
        query_fn: Any = None,
        emitter: EventEmitter | None = None,
    ) -> None:
        self.config = config
        self.bridge = bridge
        self._query_fn = query_fn or query
        self._emitter = emitter or EventEmitter()
        self._mcp_server = create_mcp_server(bridge, self._emitter)
        self._cancelled = False

    @property
    def emitter(self) -> EventEmitter:
        """The event emitter for Swift side-events."""
        return self._emitter

    def cancel(self) -> None:
        """Cancel the current agent loop."""
        self._cancelled = True

    def _build_options(self) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from our config."""
        allowed_tools = [f"mcp__pyax-tools__{name}" for name in TOOL_NAMES]
        return ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            model=self.config.model,
            max_turns=self.config.max_turns,
            permission_mode=self.config.permission_mode,
            mcp_servers={"pyax-tools": self._mcp_server},
            allowed_tools=allowed_tools,
        )

    async def run(
        self,
        message: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Run the agent loop for a user message.

        Uses the Claude Agent SDK's query() which automatically:
        1. Sends messages + tools to Claude via Claude Code CLI
        2. If Claude returns tool_use, calls the MCP tool and feeds results back
        3. Repeats until Claude returns a text-only response (ResultMessage)

        We iterate the yielded messages and emit SSE events at each step.
        Side-events from tools (highlights, speak, etc.) are drained and yielded
        after each SDK message.

        Args:
            message: The user's message text.
            conversation_history: Optional list of previous messages (unused with SDK,
                reserved for future session continuation).

        Yields:
            SSEEvent objects for each step (thinking, tool calls, response).
        """
        self._cancelled = False

        yield ThinkingEvent(status="analyzing_request")

        try:
            options = self._build_options()

            async for msg in self._query_fn(prompt=message, options=options):
                if self._cancelled:
                    yield ErrorEvent(message="Agent loop cancelled")
                    yield DoneEvent()
                    return

                # Map SDK message types to our SSE events
                events = self._process_message(msg)
                for event in events:
                    yield event

                # Also yield any side-events from tools (highlights, speak, etc.)
                for side_event in self._emitter.drain():
                    yield side_event

        except Exception as e:
            logger.error("Agent SDK error: %s", e)
            yield ErrorEvent(message=f"Agent error: {e}")

        yield DoneEvent()

    def _process_message(self, msg: Any) -> list[SSEEvent]:
        """Convert a Claude Agent SDK message to SSE events.

        Args:
            msg: A message from the SDK (AssistantMessage, ResultMessage, etc.)

        Returns:
            List of SSE events to emit.
        """
        events: list[SSEEvent] = []

        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text:
                    # Intermediate text from assistant (thinking aloud)
                    events.append(MessageEvent(content=block.text))
                elif isinstance(block, ToolUseBlock):
                    events.append(
                        ToolCallEvent(
                            tool=self._strip_mcp_prefix(block.name),
                            input=block.input if isinstance(block.input, dict) else {},
                        )
                    )
                elif isinstance(block, ToolResultBlock):
                    # Tool result block in assistant message
                    tool_name = ""
                    result_data = self._parse_tool_result(block.content)
                    if block.is_error:
                        result_data = {"error": str(block.content)}
                    events.append(ToolResultEvent(tool=tool_name, result=result_data))
                elif isinstance(block, ThinkingBlock):
                    events.append(ThinkingEvent(status="reasoning"))

        elif isinstance(msg, ResultMessage):
            # Final result — extract text
            if msg.result:
                events.append(MessageEvent(content=msg.result))

        elif isinstance(msg, UserMessage):
            # User messages may contain tool results forwarded by the SDK
            if hasattr(msg, "content") and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        result_data = self._parse_tool_result(block.content)
                        if block.is_error:
                            result_data = {"error": str(block.content)}
                        events.append(ToolResultEvent(tool="", result=result_data))

        elif isinstance(msg, SystemMessage):
            # System messages (e.g., errors from the SDK)
            # SystemMessage has .subtype and .data (dict)
            events.append(ThinkingEvent(status="system"))

        return events

    @staticmethod
    def _strip_mcp_prefix(name: str) -> str:
        """Strip the 'mcp__pyax-tools__' prefix from tool names.

        The SDK prefixes MCP tool names with 'mcp__<server>__'.
        We strip this for cleaner SSE events.
        """
        prefix = "mcp__pyax-tools__"
        if name.startswith(prefix):
            return name[len(prefix) :]
        return name

    @staticmethod
    def _parse_tool_result(content: Any) -> Any:
        """Parse tool result content into a dict for SSE serialization."""
        if content is None:
            return {}
        if isinstance(content, str):
            try:
                return json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return {"raw": content}
        if isinstance(content, list):
            # List of content blocks — extract text
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        return json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        texts.append(text)
            if texts:
                return {"raw": "\n".join(texts)}
        return {"raw": str(content)}
