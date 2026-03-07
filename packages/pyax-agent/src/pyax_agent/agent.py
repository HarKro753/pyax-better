"""Core agent loop using the Anthropic SDK's tool_runner.

The SDK handles:
  - Tool schema generation (@beta_async_tool decorator)
  - Tool dispatch (tool_runner iterates tool_use → call → result automatically)
  - API key from environment (ANTHROPIC_API_KEY, no manual config needed)

We wrap the tool_runner to emit SSE events for the Swift frontend.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import anthropic

from pyax_agent.bridge_client import BridgeClient
from pyax_agent.config import AgentConfig
from pyax_agent.models.sse import (
    DoneEvent,
    ErrorEvent,
    MessageEvent,
    SSEEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from pyax_agent.tools.registry import create_all_tools

logger = logging.getLogger(__name__)

# System prompt for Phase 1 (without memory files)
SYSTEM_PROMPT = """\
You are an accessibility assistant that helps users interact with macOS \
applications. You can inspect the UI, find elements, click buttons, and type text.

## Your Capabilities

You have access to tools that let you:
- Inspect the current UI state (get_ui_tree, find_elements, get_element)
- Click buttons and other elements (click_element)
- Type text into fields (type_text)
- Check what element has focus (get_focused_element)

## Guidelines

- Use get_ui_tree first to understand the current UI layout
- Use find_elements to search for specific elements by role, title, or value
- Always verify an action succeeded by checking the UI state after performing it
- Be concise but clear in your responses
- If you can't find an element, explain what you see instead
"""


class AgentLoop:
    """Runs the Anthropic tool_use agent loop via the SDK's tool_runner.

    Each call to `run()` processes a user message through Claude,
    executing tools as needed, and yields SSE events for streaming.
    """

    def __init__(
        self,
        config: AgentConfig,
        bridge: BridgeClient,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self.config = config
        self.bridge = bridge
        self._client = client or anthropic.AsyncAnthropic()
        self._tools = create_all_tools(bridge)
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the current agent loop."""
        self._cancelled = True

    async def run(
        self,
        message: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Run the agent loop for a user message.

        Uses the SDK's tool_runner which automatically:
        1. Sends messages + tools to Claude
        2. If Claude returns tool_use, calls the tool and feeds results back
        3. Repeats until Claude returns a text-only response

        We iterate the runner and emit SSE events at each step.

        Args:
            message: The user's message text.
            conversation_history: Optional list of previous messages.

        Yields:
            SSEEvent objects for each step (thinking, tool calls, response).
        """
        self._cancelled = False

        # Build messages list
        messages: list[dict[str, Any]] = list(conversation_history or [])
        messages.append({"role": "user", "content": message})

        yield ThinkingEvent(status="analyzing_request")

        try:
            runner = self._client.beta.messages.tool_runner(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=SYSTEM_PROMPT,
                tools=self._tools,
                messages=messages,
                max_iterations=self.config.max_turns,
            )

            async for response in runner:
                if self._cancelled:
                    yield ErrorEvent(message="Agent loop cancelled")
                    yield DoneEvent()
                    return

                # Process content blocks from this response
                for block in response.content:
                    if block.type == "text" and block.text:
                        # Text block — could be intermediate or final
                        pass
                    elif block.type == "tool_use":
                        # Emit tool call event
                        yield ToolCallEvent(
                            tool=block.name,
                            input=block.input if isinstance(block.input, dict) else {},
                        )

                # If this response has tool_use blocks, the runner will call them.
                # We need to emit tool_result events for the tool calls that were made.
                tool_response = await runner.generate_tool_call_response()
                if tool_response is not None:
                    # Extract tool results from the generated response
                    for result_block in tool_response.get("content", []):
                        if (
                            isinstance(result_block, dict)
                            and result_block.get("type") == "tool_result"
                        ):
                            tool_use_id = result_block.get("tool_use_id", "")
                            content = result_block.get("content", "")
                            is_error = result_block.get("is_error", False)

                            # Find the tool name from the response's tool_use blocks
                            tool_name = ""
                            for block in response.content:
                                if block.type == "tool_use" and block.id == tool_use_id:
                                    tool_name = block.name
                                    break

                            # Parse result for SSE
                            try:
                                result_data = (
                                    json.loads(content) if isinstance(content, str) else content
                                )
                            except (json.JSONDecodeError, TypeError):
                                result_data = {"raw": str(content)}

                            if is_error:
                                result_data = {"error": str(content)}

                            yield ToolResultEvent(tool=tool_name, result=result_data)

            # After the runner completes, extract the final text response
            final_message = await runner.until_done()
            text = self._extract_text(final_message)
            if text:
                yield MessageEvent(content=text)

        except anthropic.APIError as e:
            logger.error("Anthropic API error: %s", e)
            yield ErrorEvent(message=f"API error: {e}")
        except Exception as e:
            logger.error("Unexpected error in agent loop: %s", e)
            yield ErrorEvent(message=f"Unexpected error: {e}")

        yield DoneEvent()

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text content from a Claude response."""
        texts = []
        for block in response.content:
            if block.type == "text":
                texts.append(block.text)
        return "\n".join(texts)
