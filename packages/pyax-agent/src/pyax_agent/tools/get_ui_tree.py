"""Get UI tree tool — returns the accessibility tree of the focused app.

Use this to understand the current UI layout: what elements exist,
their roles, titles, values, and available actions.
"""

import json
import logging

from anthropic import beta_async_tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_get_ui_tree(bridge: BridgeClient):
    """Create a get_ui_tree tool with the bridge client captured in closure."""

    @beta_async_tool
    async def get_ui_tree(depth: int = 5) -> str:
        """Get the hierarchical UI element tree of the currently focused macOS application.

        Returns the full accessibility tree with roles, titles, values, and available actions.
        Use this to understand the current UI layout.

        Args:
            depth: Maximum depth to recurse into the tree. Default 5.
        """
        response = await bridge.send_command("get_tree", depth=depth)

        if "error" in response:
            return json.dumps({"error": response["error"]})

        return json.dumps(
            {
                "app": response.get("app", ""),
                "pid": response.get("pid", 0),
                "tree": response.get("tree", {}),
            }
        )

    return get_ui_tree
