"""Tool registry — creates all agent tools with bridge client injection.

To add a new tool:
  1. Create a new file in tools/ (e.g. scroll.py)
  2. Write a create_<name>(bridge) factory that returns a @tool-decorated SdkMcpTool
  3. Import the factory here and add it to create_all_tools()

Tools are bundled into an in-process MCP server via create_sdk_mcp_server().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server
from claude_agent_sdk.types import McpSdkServerConfig

# Phase 1 bridge tools
from pyax_agent.tools.click_element import create_click_element
from pyax_agent.tools.find_elements import create_find_elements
from pyax_agent.tools.get_element import create_get_element
from pyax_agent.tools.get_focused_element import create_get_focused_element
from pyax_agent.tools.get_ui_tree import create_get_ui_tree
from pyax_agent.tools.type_text import create_type_text

# Phase 2 bridge tools
from pyax_agent.tools.scroll import create_scroll
from pyax_agent.tools.perform_action import create_perform_action
from pyax_agent.tools.get_element_at_position import create_get_element_at_position
from pyax_agent.tools.get_app_info import create_get_app_info
from pyax_agent.tools.list_windows import create_list_windows

# Phase 2 Swift tools (use EventEmitter, not bridge)
from pyax_agent.tools.highlight_elements import create_highlight_elements
from pyax_agent.tools.clear_highlights import create_clear_highlights
from pyax_agent.tools.speak_text import create_speak_text

# Phase 2 local tool
from pyax_agent.tools.take_screenshot import create_take_screenshot

if TYPE_CHECKING:
    from pyax_agent.bridge_client import BridgeClient
    from pyax_agent.event_emitter import EventEmitter


# Names of all tools (for tests and introspection)
TOOL_NAMES = [
    # Phase 1
    "get_ui_tree",
    "find_elements",
    "get_element",
    "click_element",
    "type_text",
    "get_focused_element",
    # Phase 2 — bridge tools
    "scroll",
    "perform_action",
    "get_element_at_position",
    "get_app_info",
    "list_windows",
    # Phase 2 — Swift tools
    "highlight_elements",
    "clear_highlights",
    "speak_text",
    # Phase 2 — local tools
    "take_screenshot",
]


def create_all_tools(
    bridge: "BridgeClient",
    emitter: "EventEmitter | None" = None,
) -> list[SdkMcpTool]:
    """Create all agent tools with the bridge client and emitter captured in closures.

    Args:
        bridge: The WebSocket bridge client for accessibility API calls.
        emitter: Optional event emitter for Swift side-events. If None, a default
            EventEmitter is created so tools can still be instantiated.

    Returns a list of SdkMcpTool instances ready for create_sdk_mcp_server().
    """
    if emitter is None:
        from pyax_agent.event_emitter import EventEmitter

        emitter = EventEmitter()

    return [
        # Phase 1
        create_get_ui_tree(bridge),
        create_find_elements(bridge),
        create_get_element(bridge),
        create_click_element(bridge),
        create_type_text(bridge),
        create_get_focused_element(bridge),
        # Phase 2 — bridge tools
        create_scroll(bridge),
        create_perform_action(bridge),
        create_get_element_at_position(bridge),
        create_get_app_info(bridge),
        create_list_windows(bridge),
        # Phase 2 — Swift tools
        create_highlight_elements(emitter),
        create_clear_highlights(emitter),
        create_speak_text(emitter),
        # Phase 2 — local tools
        create_take_screenshot(),
    ]


def create_mcp_server(
    bridge: "BridgeClient",
    emitter: "EventEmitter | None" = None,
) -> McpSdkServerConfig:
    """Create an in-process MCP server with all accessibility tools.

    This bundles all tools into a single MCP server that runs in-process,
    providing zero-overhead tool calls without subprocess IPC.

    Args:
        bridge: The WebSocket bridge client for communicating with the pyax bridge.
        emitter: Optional event emitter for Swift side-events.

    Returns:
        McpSdkServerConfig ready for ClaudeAgentOptions.mcp_servers.
    """
    tools = create_all_tools(bridge, emitter)
    return create_sdk_mcp_server(
        name="pyax-tools",
        version="0.1.0",
        tools=tools,
    )
