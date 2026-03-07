"""Tests for individual tool functions and the registry."""

import json

import pytest

from claude_agent_sdk import SdkMcpTool

from pyax_agent.tools.registry import TOOL_NAMES, create_all_tools, create_mcp_server
from pyax_agent.tools.get_ui_tree import create_get_ui_tree
from pyax_agent.tools.find_elements import create_find_elements
from pyax_agent.tools.get_element import create_get_element
from pyax_agent.tools.click_element import create_click_element
from pyax_agent.tools.type_text import create_type_text
from pyax_agent.tools.get_focused_element import create_get_focused_element


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

    def test_tool_names_list(self):
        assert len(TOOL_NAMES) == 6

    def test_create_all_tools(self):
        bridge = FakeBridge()
        tools = create_all_tools(bridge)
        assert len(tools) == 6

    def test_all_tool_names_match(self):
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
