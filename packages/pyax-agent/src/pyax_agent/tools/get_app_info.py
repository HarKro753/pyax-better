"""Get app info tool — get focused app metadata.

Returns information about the currently focused application.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_get_app_info(bridge: BridgeClient):
    """Create a get_app_info tool with the bridge client captured in closure."""

    @tool(
        "get_app_info",
        "Get metadata about the currently focused macOS application, including "
        "its name, PID, bundle identifier, and window information.",
        {},
    )
    async def get_app_info(args: dict) -> dict:
        response = await bridge.send_command("get_app_info")

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            result = json.dumps(
                {
                    "app": response.get("app", ""),
                    "pid": response.get("pid", 0),
                    "bundle_id": response.get("bundle_id", ""),
                    "windows": response.get("windows", []),
                }
            )

        return {"content": [{"type": "text", "text": result}]}

    return get_app_info
