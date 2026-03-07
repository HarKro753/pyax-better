"""Tests for the agent core loop."""

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


# --- Fake Anthropic response objects (duck-typed, no SDK import needed) ---


@dataclass
class FakeTextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class FakeToolUseBlock:
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class FakeResponse:
    stop_reason: str = "end_turn"
    content: list = field(default_factory=list)
    role: str = "assistant"


class FakeToolRunner:
    """Fake BetaAsyncToolRunner that yields responses and handles tool call responses."""

    def __init__(self, responses, tool_call_responses=None):
        self._responses = responses
        self._tool_call_responses = tool_call_responses or []
        self._call_index = 0
        self._last_response = None

    async def __aiter__(self):
        for response in self._responses:
            self._last_response = response
            yield response

    async def generate_tool_call_response(self):
        if self._call_index < len(self._tool_call_responses):
            result = self._tool_call_responses[self._call_index]
            self._call_index += 1
            return result
        return None

    async def until_done(self):
        return self._last_response or self._responses[-1]


def make_config(**kwargs) -> AgentConfig:
    return AgentConfig(**kwargs)


class TestAgentLoopInit:
    """Tests for AgentLoop initialization."""

    def test_creates_with_config_and_bridge(self):
        config = make_config()
        bridge = BridgeClient()
        agent = AgentLoop(config=config, bridge=bridge)
        assert agent.config is config
        assert agent.bridge is bridge

    def test_accepts_custom_client(self):
        config = make_config()
        bridge = BridgeClient()
        mock_client = MagicMock()
        agent = AgentLoop(config=config, bridge=bridge, client=mock_client)
        assert agent._client is mock_client

    def test_creates_tools(self):
        config = make_config()
        bridge = BridgeClient()
        agent = AgentLoop(config=config, bridge=bridge)
        assert agent._tools is not None
        assert len(agent._tools) == 6
        names = {t.name for t in agent._tools}
        assert "get_ui_tree" in names
        assert "click_element" in names


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

    @pytest.fixture
    def agent_with_mock(self):
        config = make_config()
        bridge = BridgeClient()
        mock_client = MagicMock()
        agent = AgentLoop(config=config, bridge=bridge, client=mock_client)
        return agent, mock_client

    @pytest.mark.asyncio
    async def test_simple_text_response(self, agent_with_mock):
        """Test that a simple text response yields ThinkingEvent + MessageEvent + DoneEvent."""
        agent, mock_client = agent_with_mock

        final_response = FakeResponse(
            stop_reason="end_turn",
            content=[FakeTextBlock(text="Hello! I can help you.")],
        )

        runner = FakeToolRunner(
            responses=[final_response],
            tool_call_responses=[None],
        )
        mock_client.beta.messages.tool_runner.return_value = runner

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        assert isinstance(events[0], ThinkingEvent)
        assert isinstance(events[-1], DoneEvent)
        message_events = [e for e in events if isinstance(e, MessageEvent)]
        assert len(message_events) >= 1
        assert message_events[0].content == "Hello! I can help you."

    @pytest.mark.asyncio
    async def test_tool_call_then_response(self, agent_with_mock):
        """Test that tool calls yield ToolCallEvent + ToolResultEvent, then MessageEvent."""
        agent, mock_client = agent_with_mock

        tool_response = FakeResponse(
            stop_reason="tool_use",
            content=[
                FakeTextBlock(text="Let me check."),
                FakeToolUseBlock(id="tool-1", name="get_ui_tree", input={"depth": 3}),
            ],
        )
        final_response = FakeResponse(
            stop_reason="end_turn",
            content=[FakeTextBlock(text="I can see a Submit button.")],
        )

        tool_result = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-1",
                    "content": '{"app": "Safari", "pid": 123, "tree": {}}',
                }
            ],
        }

        runner = FakeToolRunner(
            responses=[tool_response, final_response],
            tool_call_responses=[tool_result, None],
        )
        mock_client.beta.messages.tool_runner.return_value = runner

        events = []
        async for event in agent.run("What do you see?"):
            events.append(event)

        types = [type(e).__name__ for e in events]
        assert "ThinkingEvent" in types
        assert "ToolCallEvent" in types
        assert "ToolResultEvent" in types
        assert "MessageEvent" in types
        assert types[-1] == "DoneEvent"

    @pytest.mark.asyncio
    async def test_api_error_handling(self, agent_with_mock):
        """Test that API errors yield ErrorEvent + DoneEvent."""
        agent, mock_client = agent_with_mock
        import anthropic

        mock_client.beta.messages.tool_runner.side_effect = anthropic.APIError(
            message="Rate limited",
            request=MagicMock(),
            body=None,
        )

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        assert isinstance(events[0], ThinkingEvent)
        assert isinstance(events[1], ErrorEvent)
        assert "API error" in events[1].message
        assert isinstance(events[2], DoneEvent)

    @pytest.mark.asyncio
    async def test_cancellation(self, agent_with_mock):
        """Test that cancellation stops the loop cleanly."""
        agent, mock_client = agent_with_mock

        tool_response = FakeResponse(
            stop_reason="tool_use",
            content=[FakeToolUseBlock(id="tool-1", name="get_ui_tree", input={})],
        )

        runner = FakeToolRunner(
            responses=[tool_response],
            tool_call_responses=[None],
        )
        mock_client.beta.messages.tool_runner.return_value = runner

        agent.cancel()

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        types = [type(e).__name__ for e in events]
        assert "DoneEvent" in types

    @pytest.mark.asyncio
    async def test_conversation_history(self, agent_with_mock):
        """Test that conversation history is passed to the tool_runner."""
        agent, mock_client = agent_with_mock

        final_response = FakeResponse(
            stop_reason="end_turn",
            content=[FakeTextBlock(text="OK")],
        )

        runner = FakeToolRunner(
            responses=[final_response],
            tool_call_responses=[None],
        )
        mock_client.beta.messages.tool_runner.return_value = runner

        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

        events = []
        async for event in agent.run("What did I say?", conversation_history=history):
            events.append(event)

        call_kwargs = mock_client.beta.messages.tool_runner.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) >= 3
        assert messages[0] == {"role": "user", "content": "Hi"}
        assert messages[1] == {"role": "assistant", "content": "Hello!"}
        assert messages[2] == {"role": "user", "content": "What did I say?"}

    @pytest.mark.asyncio
    async def test_unexpected_error(self, agent_with_mock):
        """Test that unexpected errors yield ErrorEvent + DoneEvent."""
        agent, mock_client = agent_with_mock

        mock_client.beta.messages.tool_runner.side_effect = RuntimeError("Something broke")

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        assert isinstance(events[0], ThinkingEvent)
        assert isinstance(events[1], ErrorEvent)
        assert "Unexpected error" in events[1].message
        assert isinstance(events[2], DoneEvent)


class TestAgentHelpers:
    """Tests for agent helper methods."""

    def test_extract_text_single_block(self):
        response = FakeResponse(content=[FakeTextBlock(text="Hello world")])
        assert AgentLoop._extract_text(response) == "Hello world"

    def test_extract_text_multiple_blocks(self):
        response = FakeResponse(
            content=[
                FakeTextBlock(text="Line 1"),
                FakeToolUseBlock(id="t", name="x", input={}),
                FakeTextBlock(text="Line 2"),
            ]
        )
        assert AgentLoop._extract_text(response) == "Line 1\nLine 2"

    def test_extract_text_no_text(self):
        response = FakeResponse(content=[FakeToolUseBlock(id="t", name="x", input={})])
        assert AgentLoop._extract_text(response) == ""
