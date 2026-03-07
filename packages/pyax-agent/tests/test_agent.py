"""Tests for the agent core loop using Claude Agent SDK."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from pyax_agent.agent import AgentLoop, SYSTEM_PROMPT
from pyax_agent.bridge_client import BridgeClient
from pyax_agent.config import AgentConfig
from pyax_agent.models.sse import (
    DoneEvent,
    ErrorEvent,
    MessageEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)


def make_config(**kwargs) -> AgentConfig:
    return AgentConfig(**kwargs)


async def make_fake_query(messages: list):
    """Create a fake query function that yields the given messages."""

    async def fake_query(*, prompt, options=None):
        for msg in messages:
            yield msg

    return fake_query


class TestAgentLoopInit:
    """Tests for AgentLoop initialization."""

    def test_creates_with_config_and_bridge(self):
        config = make_config()
        bridge = BridgeClient()
        agent = AgentLoop(config=config, bridge=bridge)
        assert agent.config is config
        assert agent.bridge is bridge

    def test_accepts_custom_query_fn(self):
        config = make_config()
        bridge = BridgeClient()
        mock_fn = MagicMock()
        agent = AgentLoop(config=config, bridge=bridge, query_fn=mock_fn)
        assert agent._query_fn is mock_fn

    def test_creates_mcp_server(self):
        config = make_config()
        bridge = BridgeClient()
        agent = AgentLoop(config=config, bridge=bridge)
        assert agent._mcp_server is not None

    def test_build_options(self):
        config = make_config(model="claude-opus-4-20250514", max_turns=10)
        bridge = BridgeClient()
        agent = AgentLoop(config=config, bridge=bridge)
        options = agent._build_options()
        assert options.model == "claude-opus-4-20250514"
        assert options.max_turns == 10
        assert options.system_prompt == SYSTEM_PROMPT
        assert "pyax-tools" in options.mcp_servers
        assert len(options.allowed_tools) == 6


class TestSystemPrompt:
    """Tests for the system prompt."""

    def test_contains_key_sections(self):
        assert "accessibility" in SYSTEM_PROMPT.lower()
        assert "get_ui_tree" in SYSTEM_PROMPT
        assert "find_elements" in SYSTEM_PROMPT
        assert "click_element" in SYSTEM_PROMPT
        assert "type_text" in SYSTEM_PROMPT


class TestAgentLoopRun:
    """Tests for the agent run method."""

    @pytest.mark.asyncio
    async def test_simple_text_response(self):
        """Test that a simple result yields ThinkingEvent + MessageEvent + DoneEvent."""
        config = make_config()
        bridge = BridgeClient()

        result_msg = ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            result="Hello! I can help you.",
        )

        async def fake_query(*, prompt, options=None):
            yield result_msg

        agent = AgentLoop(config=config, bridge=bridge, query_fn=fake_query)

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        assert isinstance(events[0], ThinkingEvent)
        assert isinstance(events[-1], DoneEvent)
        message_events = [e for e in events if isinstance(e, MessageEvent)]
        assert len(message_events) >= 1
        assert message_events[0].content == "Hello! I can help you."

    @pytest.mark.asyncio
    async def test_assistant_text_message(self):
        """Test that an AssistantMessage with text yields MessageEvent."""
        config = make_config()
        bridge = BridgeClient()

        assistant_msg = AssistantMessage(
            content=[TextBlock(text="Let me check the UI.")],
            model="claude-sonnet-4-20250514",
        )
        result_msg = ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            result="Done checking.",
        )

        async def fake_query(*, prompt, options=None):
            yield assistant_msg
            yield result_msg

        agent = AgentLoop(config=config, bridge=bridge, query_fn=fake_query)

        events = []
        async for event in agent.run("Check UI"):
            events.append(event)

        message_events = [e for e in events if isinstance(e, MessageEvent)]
        assert len(message_events) >= 1
        assert any("check" in e.content.lower() for e in message_events)

    @pytest.mark.asyncio
    async def test_tool_call_event(self):
        """Test that tool_use blocks yield ToolCallEvent."""
        config = make_config()
        bridge = BridgeClient()

        assistant_msg = AssistantMessage(
            content=[
                TextBlock(text="Let me check."),
                ToolUseBlock(
                    id="tool-1",
                    name="mcp__pyax-tools__get_ui_tree",
                    input={"depth": 3},
                ),
            ],
            model="claude-sonnet-4-20250514",
        )
        result_msg = ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            result="I can see a Submit button.",
        )

        async def fake_query(*, prompt, options=None):
            yield assistant_msg
            yield result_msg

        agent = AgentLoop(config=config, bridge=bridge, query_fn=fake_query)

        events = []
        async for event in agent.run("What do you see?"):
            events.append(event)

        types = [type(e).__name__ for e in events]
        assert "ThinkingEvent" in types
        assert "ToolCallEvent" in types
        assert "MessageEvent" in types
        assert types[-1] == "DoneEvent"

        # Verify the tool name has the MCP prefix stripped
        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        assert tool_calls[0].tool == "get_ui_tree"
        assert tool_calls[0].input == {"depth": 3}

    @pytest.mark.asyncio
    async def test_tool_result_event(self):
        """Test that ToolResultBlock yields ToolResultEvent."""
        config = make_config()
        bridge = BridgeClient()

        assistant_msg = AssistantMessage(
            content=[
                ToolResultBlock(
                    tool_use_id="tool-1",
                    content='{"app": "Safari", "tree": {}}',
                ),
            ],
            model="claude-sonnet-4-20250514",
        )
        result_msg = ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
        )

        async def fake_query(*, prompt, options=None):
            yield assistant_msg
            yield result_msg

        agent = AgentLoop(config=config, bridge=bridge, query_fn=fake_query)

        events = []
        async for event in agent.run("Check"):
            events.append(event)

        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(result_events) >= 1

    @pytest.mark.asyncio
    async def test_thinking_block(self):
        """Test that ThinkingBlock yields ThinkingEvent."""
        config = make_config()
        bridge = BridgeClient()

        assistant_msg = AssistantMessage(
            content=[
                ThinkingBlock(thinking="I need to check the UI tree.", signature="sig"),
                TextBlock(text="Let me look at the UI."),
            ],
            model="claude-sonnet-4-20250514",
        )
        result_msg = ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
        )

        async def fake_query(*, prompt, options=None):
            yield assistant_msg
            yield result_msg

        agent = AgentLoop(config=config, bridge=bridge, query_fn=fake_query)

        events = []
        async for event in agent.run("Think about it"):
            events.append(event)

        thinking_events = [e for e in events if isinstance(e, ThinkingEvent)]
        # At least one from initial yield + one from ThinkingBlock
        assert len(thinking_events) >= 2

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test that exceptions yield ErrorEvent + DoneEvent."""
        config = make_config()
        bridge = BridgeClient()

        async def failing_query(*, prompt, options=None):
            raise RuntimeError("Connection failed")
            yield  # Make it an async generator

        agent = AgentLoop(config=config, bridge=bridge, query_fn=failing_query)

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        assert isinstance(events[0], ThinkingEvent)
        assert isinstance(events[1], ErrorEvent)
        assert "Connection failed" in events[1].message
        assert isinstance(events[2], DoneEvent)

    @pytest.mark.asyncio
    async def test_cancellation(self):
        """Test that cancellation stops the loop cleanly."""
        config = make_config()
        bridge = BridgeClient()

        assistant_msg = AssistantMessage(
            content=[TextBlock(text="Working on it...")],
            model="claude-sonnet-4-20250514",
        )

        async def slow_query(*, prompt, options=None):
            yield assistant_msg

        agent = AgentLoop(config=config, bridge=bridge, query_fn=slow_query)
        agent.cancel()

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        types = [type(e).__name__ for e in events]
        assert "DoneEvent" in types


class TestAgentHelpers:
    """Tests for agent helper methods."""

    def test_strip_mcp_prefix(self):
        assert AgentLoop._strip_mcp_prefix("mcp__pyax-tools__get_ui_tree") == "get_ui_tree"
        assert AgentLoop._strip_mcp_prefix("mcp__pyax-tools__click_element") == "click_element"
        assert AgentLoop._strip_mcp_prefix("plain_name") == "plain_name"
        assert AgentLoop._strip_mcp_prefix("") == ""

    def test_parse_tool_result_json_string(self):
        result = AgentLoop._parse_tool_result('{"app": "Safari", "count": 1}')
        assert result == {"app": "Safari", "count": 1}

    def test_parse_tool_result_plain_string(self):
        result = AgentLoop._parse_tool_result("not json")
        assert result == {"raw": "not json"}

    def test_parse_tool_result_none(self):
        result = AgentLoop._parse_tool_result(None)
        assert result == {}

    def test_parse_tool_result_list(self):
        result = AgentLoop._parse_tool_result([{"type": "text", "text": '{"app": "Safari"}'}])
        assert result == {"app": "Safari"}

    def test_parse_tool_result_list_non_json(self):
        result = AgentLoop._parse_tool_result([{"type": "text", "text": "plain text"}])
        assert result == {"raw": "plain text"}

    def test_process_message_system(self):
        """SystemMessage should be handled without error."""
        config = make_config()
        bridge = BridgeClient()
        agent = AgentLoop(config=config, bridge=bridge)

        msg = SystemMessage(
            subtype="system",
            data={"info": "Connected to server"},
        )
        events = agent._process_message(msg)
        # SystemMessages produce ThinkingEvent with status="system"
        assert any(isinstance(e, ThinkingEvent) for e in events)
