"""Tests for individual tool functions and the registry."""

import json

import pytest

from claude_agent_sdk import SdkMcpTool

from pyax_agent.event_emitter import EventEmitter
from pyax_agent.models.sse import ClearHighlightsEvent, HighlightEvent, SpeakEvent
from pyax_agent.tools.registry import TOOL_NAMES, create_all_tools, create_mcp_server
from pyax_agent.tools.get_ui_tree import create_get_ui_tree
from pyax_agent.tools.find_elements import create_find_elements
from pyax_agent.tools.get_element import create_get_element
from pyax_agent.tools.click_element import create_click_element
from pyax_agent.tools.type_text import create_type_text
from pyax_agent.tools.get_focused_element import create_get_focused_element
from pyax_agent.tools.scroll import create_scroll
from pyax_agent.tools.perform_action import create_perform_action
from pyax_agent.tools.get_element_at_position import create_get_element_at_position
from pyax_agent.tools.get_app_info import create_get_app_info
from pyax_agent.tools.list_windows import create_list_windows
from pyax_agent.tools.highlight_elements import create_highlight_elements
from pyax_agent.tools.clear_highlights import create_clear_highlights
from pyax_agent.tools.speak_text import create_speak_text
from pyax_agent.tools.take_screenshot import create_take_screenshot


class FakeBridge:
    """Fake bridge client for testing tools without a WebSocket connection."""

    def __init__(self):
        self.commands: list[dict] = []
        self._responses: list[dict] = []
        self._call_count = 0

    def set_response(self, response: dict):
        self._responses = [response]
        self._call_count = 0

    def set_responses(self, responses: list[dict]):
        self._responses = responses
        self._call_count = 0

    async def send_command(self, command: str, timeout: float = 10.0, **kwargs):
        self.commands.append({"command": command, **kwargs})
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
            self._call_count += 1
            return {"type": "response", "command": command, **resp}
        return {"type": "response", "command": command}


def _extract_text(result: dict) -> str:
    """Extract text from a tool result dict."""
    return result["content"][0]["text"]


def _extract_json(result: dict) -> dict:
    """Extract and parse JSON from a tool result dict."""
    return json.loads(_extract_text(result))


class TestRegistry:
    """Tests for the tool registry."""

    def test_tool_names_match_created_tools(self):
        """Every name in TOOL_NAMES has a matching created tool and vice-versa."""
        bridge = FakeBridge()
        tools = create_all_tools(bridge)
        names = {t.name for t in tools}
        assert names == set(TOOL_NAMES)

    def test_all_are_sdk_mcp_tools(self):
        bridge = FakeBridge()
        tools = create_all_tools(bridge)
        for t in tools:
            assert isinstance(t, SdkMcpTool), f"{t.name} is not SdkMcpTool"

    def test_all_have_descriptions(self):
        bridge = FakeBridge()
        tools = create_all_tools(bridge)
        for t in tools:
            assert t.description, f"{t.name} missing description"

    def test_all_have_input_schemas(self):
        bridge = FakeBridge()
        tools = create_all_tools(bridge)
        for t in tools:
            schema = t.input_schema
            assert isinstance(schema, dict), f"{t.name} schema is not a dict"

    def test_all_have_handlers(self):
        """All tools should have an async handler callable."""
        bridge = FakeBridge()
        tools = create_all_tools(bridge)
        for t in tools:
            assert callable(t.handler), f"{t.name} missing handler"

    def test_create_mcp_server(self):
        """create_mcp_server should return an McpSdkServerConfig."""
        bridge = FakeBridge()
        server_config = create_mcp_server(bridge)
        # It should be a config object usable by ClaudeAgentOptions
        assert server_config is not None


class TestGetUITree:
    """Tests for get_ui_tree tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Safari", "pid": 123, "tree": {"AXRole": "AXApplication"}})
        tool = create_get_ui_tree(bridge)
        result = _extract_json(await tool.handler({"depth": 5}))
        assert result["app"] == "Safari"
        assert result["pid"] == 123
        assert "tree" in result

    @pytest.mark.asyncio
    async def test_custom_depth(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Finder", "pid": 456, "tree": {}})
        tool = create_get_ui_tree(bridge)
        await tool.handler({"depth": 3})
        assert bridge.commands[0]["depth"] == 3

    @pytest.mark.asyncio
    async def test_default_depth(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Finder", "pid": 456, "tree": {}})
        tool = create_get_ui_tree(bridge)
        await tool.handler({})
        assert bridge.commands[0]["depth"] == 5

    @pytest.mark.asyncio
    async def test_error_response(self):
        bridge = FakeBridge()
        bridge.set_response({"error": "No focused app"})
        tool = create_get_ui_tree(bridge)
        result = _extract_json(await tool.handler({}))
        assert "error" in result

    def test_schema_excludes_bridge(self):
        bridge = FakeBridge()
        tool = create_get_ui_tree(bridge)
        schema = tool.input_schema
        assert "bridge" not in schema


class TestFindElements:
    """Tests for find_elements tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = FakeBridge()
        bridge.set_response(
            {
                "app": "Safari",
                "results": [{"AXRole": "AXButton", "AXTitle": "Submit"}],
                "count": 1,
            }
        )
        tool = create_find_elements(bridge)
        result = _extract_json(await tool.handler({"title": "Submit"}))
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_no_criteria(self):
        bridge = FakeBridge()
        tool = create_find_elements(bridge)
        result = _extract_json(await tool.handler({}))
        assert "error" in result
        assert "criterion" in result["error"]

    @pytest.mark.asyncio
    async def test_builds_criteria_dict(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Test", "results": [], "count": 0})
        tool = create_find_elements(bridge)
        await tool.handler({"role": "AXButton", "title": "*submit*"})
        cmd = bridge.commands[0]
        assert cmd["criteria"]["role"] == "AXButton"
        assert cmd["criteria"]["title"] == "*submit*"

    @pytest.mark.asyncio
    async def test_max_results(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Test", "results": [], "count": 0})
        tool = create_find_elements(bridge)
        await tool.handler({"role": "AXButton", "max_results": 5})
        assert bridge.commands[0]["max_results"] == 5


class TestGetElement:
    """Tests for get_element tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = FakeBridge()
        bridge.set_response({"path": [0, 1, 2], "element": {"AXRole": "AXButton"}})
        tool = create_get_element(bridge)
        result = _extract_json(await tool.handler({"path": [0, 1, 2]}))
        assert result["element"]["AXRole"] == "AXButton"
        assert result["path"] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_with_depth(self):
        bridge = FakeBridge()
        bridge.set_response({"path": [0], "element": {}})
        tool = create_get_element(bridge)
        await tool.handler({"path": [0], "depth": 3})
        assert bridge.commands[0]["depth"] == 3


class TestClickElement:
    """Tests for click_element tool."""

    @pytest.mark.asyncio
    async def test_click_by_path(self):
        bridge = FakeBridge()
        bridge.set_response({"success": True})
        tool = create_click_element(bridge)
        result = _extract_json(await tool.handler({"path": [0, 1]}))
        assert result["success"] is True
        assert bridge.commands[0]["action"] == "AXPress"
        assert bridge.commands[0]["path"] == [0, 1]

    @pytest.mark.asyncio
    async def test_click_by_criteria(self):
        bridge = FakeBridge()
        bridge.set_response({"success": True})
        tool = create_click_element(bridge)
        result = _extract_json(await tool.handler({"title": "OK"}))
        assert result["success"] is True
        assert bridge.commands[0]["criteria"]["title"] == "OK"

    @pytest.mark.asyncio
    async def test_missing_target(self):
        bridge = FakeBridge()
        tool = create_click_element(bridge)
        result = _extract_json(await tool.handler({}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_response(self):
        bridge = FakeBridge()
        bridge.set_response({"error": "Element not found"})
        tool = create_click_element(bridge)
        result = _extract_json(await tool.handler({"path": [0, 99]}))
        assert "error" in result


class TestTypeText:
    """Tests for type_text tool."""

    @pytest.mark.asyncio
    async def test_type_by_path(self):
        bridge = FakeBridge()
        bridge.set_responses([{"success": True}, {"success": True}])
        tool = create_type_text(bridge)
        result = _extract_json(await tool.handler({"text": "Hello", "path": [0, 1]}))
        assert result["success"] is True
        assert len(bridge.commands) == 2
        assert bridge.commands[0]["attribute"] == "AXFocused"
        assert bridge.commands[1]["attribute"] == "AXValue"
        assert bridge.commands[1]["value"] == "Hello"

    @pytest.mark.asyncio
    async def test_type_by_criteria(self):
        bridge = FakeBridge()
        bridge.set_responses([{"success": True}, {"success": True}])
        tool = create_type_text(bridge)
        result = _extract_json(await tool.handler({"text": "World", "role": "AXTextField"}))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_empty_text(self):
        bridge = FakeBridge()
        tool = create_type_text(bridge)
        result = _extract_json(await tool.handler({"text": "", "path": [0]}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_missing_target(self):
        bridge = FakeBridge()
        tool = create_type_text(bridge)
        result = _extract_json(await tool.handler({"text": "Hello"}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_response(self):
        bridge = FakeBridge()
        bridge.set_responses([{"success": True}, {"error": "Cannot set value"}])
        tool = create_type_text(bridge)
        result = _extract_json(await tool.handler({"text": "test", "path": [0, 1]}))
        assert "error" in result


class TestGetFocusedElement:
    """Tests for get_focused_element tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = FakeBridge()
        bridge.set_response({"element": {"AXRole": "AXTextField", "AXValue": "Hello"}})
        tool = create_get_focused_element(bridge)
        result = _extract_json(await tool.handler({}))
        assert result["element"]["AXRole"] == "AXTextField"

    @pytest.mark.asyncio
    async def test_error(self):
        bridge = FakeBridge()
        bridge.set_response({"error": "No focused element"})
        tool = create_get_focused_element(bridge)
        result = _extract_json(await tool.handler({}))
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# Phase 2 tests
# ═══════════════════════════════════════════════════════════════════


class TestEventEmitter:
    """Tests for the EventEmitter."""

    @pytest.mark.asyncio
    async def test_emit_and_drain(self):
        emitter = EventEmitter()
        await emitter.emit(HighlightEvent(highlights=[{"x": 0}]))
        await emitter.emit(SpeakEvent(text="hello"))
        events = emitter.drain()
        assert len(events) == 2
        assert isinstance(events[0], HighlightEvent)
        assert isinstance(events[1], SpeakEvent)

    @pytest.mark.asyncio
    async def test_drain_empty(self):
        emitter = EventEmitter()
        events = emitter.drain()
        assert events == []

    @pytest.mark.asyncio
    async def test_drain_clears_queue(self):
        emitter = EventEmitter()
        await emitter.emit(ClearHighlightsEvent())
        events = emitter.drain()
        assert len(events) == 1
        # Second drain should be empty
        events = emitter.drain()
        assert events == []


class TestScroll:
    """Tests for scroll tool."""

    @pytest.mark.asyncio
    async def test_scroll_down_by_path(self):
        bridge = FakeBridge()
        bridge.set_response({"success": True})
        tool = create_scroll(bridge)
        result = _extract_json(
            await tool.handler({"path": [0, 1], "direction": "down", "amount": 2})
        )
        assert result["success"] is True
        assert result["direction"] == "down"
        assert result["amount"] == 2
        # Should have called perform_action twice (amount=2)
        assert len(bridge.commands) == 2
        assert bridge.commands[0]["action"] == "AXScrollDown"

    @pytest.mark.asyncio
    async def test_scroll_up_by_criteria(self):
        bridge = FakeBridge()
        bridge.set_response({"success": True})
        tool = create_scroll(bridge)
        result = _extract_json(await tool.handler({"role": "AXScrollArea", "direction": "up"}))
        assert result["success"] is True
        assert result["direction"] == "up"
        # Default amount = 3
        assert len(bridge.commands) == 3
        assert bridge.commands[0]["action"] == "AXScrollUp"
        assert bridge.commands[0]["criteria"]["role"] == "AXScrollArea"

    @pytest.mark.asyncio
    async def test_scroll_invalid_direction(self):
        bridge = FakeBridge()
        tool = create_scroll(bridge)
        result = _extract_json(await tool.handler({"path": [0], "direction": "left"}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_scroll_default_direction(self):
        bridge = FakeBridge()
        bridge.set_response({"success": True})
        tool = create_scroll(bridge)
        result = _extract_json(await tool.handler({"path": [0]}))
        assert result["direction"] == "down"

    @pytest.mark.asyncio
    async def test_scroll_error_midway(self):
        bridge = FakeBridge()
        bridge.set_responses([{"success": True}, {"error": "Element gone"}])
        tool = create_scroll(bridge)
        result = _extract_json(await tool.handler({"path": [0], "direction": "down", "amount": 3}))
        assert "error" in result


class TestPerformAction:
    """Tests for perform_action tool."""

    @pytest.mark.asyncio
    async def test_action_by_path(self):
        bridge = FakeBridge()
        bridge.set_response({"success": True})
        tool = create_perform_action(bridge)
        result = _extract_json(await tool.handler({"path": [0, 1], "action": "AXShowMenu"}))
        assert result["success"] is True
        assert bridge.commands[0]["action"] == "AXShowMenu"
        assert bridge.commands[0]["path"] == [0, 1]

    @pytest.mark.asyncio
    async def test_action_by_criteria(self):
        bridge = FakeBridge()
        bridge.set_response({"success": True})
        tool = create_perform_action(bridge)
        result = _extract_json(
            await tool.handler({"role": "AXButton", "title": "OK", "action": "AXConfirm"})
        )
        assert result["success"] is True
        assert bridge.commands[0]["criteria"]["role"] == "AXButton"

    @pytest.mark.asyncio
    async def test_missing_action(self):
        bridge = FakeBridge()
        tool = create_perform_action(bridge)
        result = _extract_json(await tool.handler({"path": [0]}))
        assert "error" in result
        assert "action" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_target(self):
        bridge = FakeBridge()
        tool = create_perform_action(bridge)
        result = _extract_json(await tool.handler({"action": "AXPress"}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_response(self):
        bridge = FakeBridge()
        bridge.set_response({"error": "Action not supported"})
        tool = create_perform_action(bridge)
        result = _extract_json(await tool.handler({"path": [0], "action": "AXFoo"}))
        assert "error" in result


class TestGetElementAtPosition:
    """Tests for get_element_at_position tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = FakeBridge()
        bridge.set_response({"element": {"AXRole": "AXButton"}, "path": [0, 2]})
        tool = create_get_element_at_position(bridge)
        result = _extract_json(await tool.handler({"x": 100.0, "y": 200.0}))
        assert result["element"]["AXRole"] == "AXButton"
        assert result["path"] == [0, 2]
        assert bridge.commands[0]["x"] == 100.0
        assert bridge.commands[0]["y"] == 200.0

    @pytest.mark.asyncio
    async def test_missing_coordinates(self):
        bridge = FakeBridge()
        tool = create_get_element_at_position(bridge)
        result = _extract_json(await tool.handler({}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_missing_y(self):
        bridge = FakeBridge()
        tool = create_get_element_at_position(bridge)
        result = _extract_json(await tool.handler({"x": 100.0}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_error_response(self):
        bridge = FakeBridge()
        bridge.set_response({"error": "No element at position"})
        tool = create_get_element_at_position(bridge)
        result = _extract_json(await tool.handler({"x": 0.0, "y": 0.0}))
        assert "error" in result


class TestGetAppInfo:
    """Tests for get_app_info tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = FakeBridge()
        bridge.set_response(
            {
                "app": "Safari",
                "pid": 123,
                "bundle_id": "com.apple.Safari",
                "windows": [{"title": "Main", "size": [800, 600]}],
            }
        )
        tool = create_get_app_info(bridge)
        result = _extract_json(await tool.handler({}))
        assert result["app"] == "Safari"
        assert result["pid"] == 123
        assert result["bundle_id"] == "com.apple.Safari"
        assert len(result["windows"]) == 1

    @pytest.mark.asyncio
    async def test_error(self):
        bridge = FakeBridge()
        bridge.set_response({"error": "No focused app"})
        tool = create_get_app_info(bridge)
        result = _extract_json(await tool.handler({}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_sends_correct_command(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Finder", "pid": 1})
        tool = create_get_app_info(bridge)
        await tool.handler({})
        assert bridge.commands[0]["command"] == "get_app_info"


class TestListWindows:
    """Tests for list_windows tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = FakeBridge()
        bridge.set_response(
            {
                "app": "Finder",
                "windows": [
                    {"title": "Documents", "position": [0, 0], "size": [800, 600]},
                    {"title": "Downloads", "position": [100, 100], "size": [700, 500]},
                ],
            }
        )
        tool = create_list_windows(bridge)
        result = _extract_json(await tool.handler({}))
        assert result["app"] == "Finder"
        assert result["count"] == 2
        assert len(result["windows"]) == 2

    @pytest.mark.asyncio
    async def test_no_windows(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Finder", "windows": []})
        tool = create_list_windows(bridge)
        result = _extract_json(await tool.handler({}))
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_error(self):
        bridge = FakeBridge()
        bridge.set_response({"error": "No focused app"})
        tool = create_list_windows(bridge)
        result = _extract_json(await tool.handler({}))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_sends_get_app_info_command(self):
        bridge = FakeBridge()
        bridge.set_response({"app": "Test", "windows": []})
        tool = create_list_windows(bridge)
        await tool.handler({})
        assert bridge.commands[0]["command"] == "get_app_info"


class TestHighlightElements:
    """Tests for highlight_elements tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        emitter = EventEmitter()
        tool = create_highlight_elements(emitter)
        highlights = [
            {"x": 10, "y": 20, "width": 100, "height": 50, "color": "red", "label": "Button"}
        ]
        result = _extract_json(await tool.handler({"highlights": highlights, "duration": 5.0}))
        assert result["success"] is True
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_emits_highlight_event(self):
        emitter = EventEmitter()
        tool = create_highlight_elements(emitter)
        highlights = [{"x": 10, "y": 20, "width": 100, "height": 50}]
        await tool.handler({"highlights": highlights, "duration": 2.0})
        events = emitter.drain()
        assert len(events) == 1
        assert isinstance(events[0], HighlightEvent)
        assert events[0].highlights == highlights
        assert events[0].duration == 2.0

    @pytest.mark.asyncio
    async def test_default_duration(self):
        emitter = EventEmitter()
        tool = create_highlight_elements(emitter)
        highlights = [{"x": 0, "y": 0, "width": 10, "height": 10}]
        await tool.handler({"highlights": highlights})
        events = emitter.drain()
        assert events[0].duration == 3.0

    @pytest.mark.asyncio
    async def test_empty_highlights(self):
        emitter = EventEmitter()
        tool = create_highlight_elements(emitter)
        result = _extract_json(await tool.handler({"highlights": []}))
        assert "error" in result
        # No event should have been emitted
        assert emitter.drain() == []

    @pytest.mark.asyncio
    async def test_no_highlights(self):
        emitter = EventEmitter()
        tool = create_highlight_elements(emitter)
        result = _extract_json(await tool.handler({}))
        assert "error" in result


class TestClearHighlights:
    """Tests for clear_highlights tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        emitter = EventEmitter()
        tool = create_clear_highlights(emitter)
        result = _extract_json(await tool.handler({}))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_emits_clear_event(self):
        emitter = EventEmitter()
        tool = create_clear_highlights(emitter)
        await tool.handler({})
        events = emitter.drain()
        assert len(events) == 1
        assert isinstance(events[0], ClearHighlightsEvent)


class TestSpeakText:
    """Tests for speak_text tool."""

    @pytest.mark.asyncio
    async def test_success(self):
        emitter = EventEmitter()
        tool = create_speak_text(emitter)
        result = _extract_json(await tool.handler({"text": "Hello world", "rate": 0.7}))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_emits_speak_event(self):
        emitter = EventEmitter()
        tool = create_speak_text(emitter)
        await tool.handler({"text": "Testing", "rate": 0.3})
        events = emitter.drain()
        assert len(events) == 1
        assert isinstance(events[0], SpeakEvent)
        assert events[0].text == "Testing"
        assert events[0].rate == 0.3

    @pytest.mark.asyncio
    async def test_default_rate(self):
        emitter = EventEmitter()
        tool = create_speak_text(emitter)
        await tool.handler({"text": "Default rate"})
        events = emitter.drain()
        assert events[0].rate == 0.5

    @pytest.mark.asyncio
    async def test_empty_text(self):
        emitter = EventEmitter()
        tool = create_speak_text(emitter)
        result = _extract_json(await tool.handler({"text": ""}))
        assert "error" in result
        assert emitter.drain() == []

    @pytest.mark.asyncio
    async def test_missing_text(self):
        emitter = EventEmitter()
        tool = create_speak_text(emitter)
        result = _extract_json(await tool.handler({}))
        assert "error" in result


class TestTakeScreenshot:
    """Tests for take_screenshot tool."""

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        """Test screenshot returns base64 image content."""
        import subprocess
        import tempfile
        import base64
        from pathlib import Path

        # Create a tiny 1x1 PNG for testing
        # Minimal valid PNG: header + IHDR + IDAT + IEND
        fake_png = (
            b"\x89PNG\r\n\x1a\n"  # PNG signature
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde"  # 1x1 RGB
            b"\x00\x00\x00\x0cIDATx"
            b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
            b"\x18\xd8N"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        def fake_run(cmd, **kwargs):
            # Write fake PNG to the output path (last arg)
            output_path = cmd[-1]
            Path(output_path).write_bytes(fake_png)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        monkeypatch.setattr(subprocess, "run", fake_run)

        tool = create_take_screenshot()
        result = await tool.handler({})

        assert result["content"][0]["type"] == "image"
        assert result["content"][0]["source"]["type"] == "base64"
        assert result["content"][0]["source"]["media_type"] == "image/png"
        # Verify it's valid base64
        decoded = base64.b64decode(result["content"][0]["source"]["data"])
        assert decoded == fake_png

    @pytest.mark.asyncio
    async def test_with_region(self, monkeypatch):
        """Test screenshot with region captures the specified area."""
        import subprocess
        from pathlib import Path

        captured_cmd = []

        def fake_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            Path(cmd[-1]).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        monkeypatch.setattr(subprocess, "run", fake_run)

        tool = create_take_screenshot()
        await tool.handler({"region": {"x": 10, "y": 20, "width": 300, "height": 200}})

        assert "-R" in captured_cmd
        r_index = captured_cmd.index("-R")
        assert captured_cmd[r_index + 1] == "10,20,300,200"

    @pytest.mark.asyncio
    async def test_screencapture_failure(self, monkeypatch):
        """Test handling of screencapture failure."""
        import subprocess

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, b"", b"capture failed")

        monkeypatch.setattr(subprocess, "run", fake_run)

        tool = create_take_screenshot()
        result = await tool.handler({})

        assert result["content"][0]["type"] == "text"
        data = json.loads(result["content"][0]["text"])
        assert "error" in data
        assert "failed" in data["error"]

    @pytest.mark.asyncio
    async def test_timeout(self, monkeypatch):
        """Test handling of screencapture timeout."""
        import subprocess

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 10)

        monkeypatch.setattr(subprocess, "run", fake_run)

        tool = create_take_screenshot()
        result = await tool.handler({})

        assert result["content"][0]["type"] == "text"
        data = json.loads(result["content"][0]["text"])
        assert "error" in data
        assert "timed out" in data["error"]
