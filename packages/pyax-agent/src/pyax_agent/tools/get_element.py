"""Get element tool — retrieves details about a specific UI element by path.

The path is an array of child indices from the root element,
e.g. [0, 3, 2] means: first child, then fourth child, then third child.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_get_element(bridge: BridgeClient):
    """Create a get_element tool with the bridge client captured in closure."""

    @tool(
        "get_element",
        "Get detailed information about a specific UI element by its path. "
        "The path is an array of child indices from the root element.",
        {"path": list, "depth": int},
    )
    async def get_element(args: dict) -> dict:
        path = args.get("path", [])
        depth = args.get("depth", 1)
        response = await bridge.send_command("get_element", path=path, depth=depth)

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            result = json.dumps(
                {
                    "path": response.get("path", path),
                    "element": response.get("element", {}),
                }
            )

        return {"content": [{"type": "text", "text": result}]}

    return get_element
