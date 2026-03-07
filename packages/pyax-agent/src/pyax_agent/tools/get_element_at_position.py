"""Get element at position tool — hit-test at screen coordinates.

Returns the UI element at the given (x, y) screen position.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_get_element_at_position(bridge: BridgeClient):
    """Create a get_element_at_position tool with the bridge client captured in closure."""

    @tool(
        "get_element_at_position",
        "Get the UI element at a specific screen position (x, y coordinates). "
        "Useful for identifying what element is at a particular location on screen.",
        {"x": float, "y": float},
    )
    async def get_element_at_position(args: dict) -> dict:
        x = args.get("x")
        y = args.get("y")

        if x is None or y is None:
            result = json.dumps({"error": "Both x and y coordinates are required"})
            return {"content": [{"type": "text", "text": result}]}

        response = await bridge.send_command("get_element_at_position", x=x, y=y)

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            result = json.dumps(
                {
                    "element": response.get("element", {}),
                    "path": response.get("path", []),
                }
            )

        return {"content": [{"type": "text", "text": result}]}

    return get_element_at_position
