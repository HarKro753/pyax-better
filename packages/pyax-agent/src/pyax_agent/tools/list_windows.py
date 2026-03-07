"""List windows tool — list all windows with titles, sizes, positions.

Sends get_app_info to the bridge and extracts the window list.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_list_windows(bridge: BridgeClient):
    """Create a list_windows tool with the bridge client captured in closure."""

    @tool(
        "list_windows",
        "List all windows of the currently focused application with their titles, "
        "sizes, and positions. Useful for understanding the window layout.",
        {},
    )
    async def list_windows(args: dict) -> dict:
        response = await bridge.send_command("get_app_info")

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            windows = response.get("windows", [])
            result = json.dumps(
                {
                    "app": response.get("app", ""),
                    "windows": windows,
                    "count": len(windows),
                }
            )

        return {"content": [{"type": "text", "text": result}]}

    return list_windows
