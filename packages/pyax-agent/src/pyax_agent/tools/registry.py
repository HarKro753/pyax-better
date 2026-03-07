"""Tool registry — creates all agent tools with bridge client injection.

To add a new tool:
  1. Create a new file in tools/ (e.g. scroll.py)
  2. Write a create_<name>(bridge) factory that returns a @beta_async_tool
  3. Import the factory here and add it to create_all_tools()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyax_agent.tools.click_element import create_click_element
from pyax_agent.tools.find_elements import create_find_elements
from pyax_agent.tools.get_element import create_get_element
from pyax_agent.tools.get_focused_element import create_get_focused_element
from pyax_agent.tools.get_ui_tree import create_get_ui_tree
from pyax_agent.tools.type_text import create_type_text

if TYPE_CHECKING:
    from pyax_agent.bridge_client import BridgeClient


# Names of all tools (for tests and introspection)
TOOL_NAMES = [
    "get_ui_tree",
    "find_elements",
    "get_element",
    "click_element",
    "type_text",
    "get_focused_element",
]


def create_all_tools(bridge: "BridgeClient") -> list:
    """Create all agent tools with the bridge client captured in closures.

    Returns a list of @beta_async_tool decorated functions ready for
    client.beta.messages.tool_runner().
    """
    return [
        create_get_ui_tree(bridge),
        create_find_elements(bridge),
        create_get_element(bridge),
        create_click_element(bridge),
        create_type_text(bridge),
        create_get_focused_element(bridge),
    ]
