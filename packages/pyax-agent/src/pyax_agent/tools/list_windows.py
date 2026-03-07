"""List windows tool — list all windows across all running applications.

Sends list_all_windows to the bridge which iterates every running app
and returns all their windows with titles, sizes, and positions.
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
        "List all windows across ALL running macOS applications (not just the "
        "focused one) with their titles, sizes, positions, and owning app name. "
        "Useful for understanding the full desktop layout and finding windows "
        "in any application.",
        {},
    )
    async def list_windows(args: dict) -> dict:
        response = await bridge.send_command("list_all_windows")

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            windows = response.get("windows", [])
            result = json.dumps(
                {
                    "windows": windows,
                    "count": len(windows),
                }
            )

        return {"content": [{"type": "text", "text": result}]}

    return list_windows
