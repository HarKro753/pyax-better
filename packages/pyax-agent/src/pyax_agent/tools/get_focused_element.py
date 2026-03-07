"""Get focused element tool — returns the element with keyboard focus."""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_get_focused_element(bridge: BridgeClient):
    """Create a get_focused_element tool with the bridge client captured in closure."""

    @tool(
        "get_focused_element",
        "Get the UI element that currently has keyboard focus. "
        "Useful for understanding what the user is currently interacting with.",
        {},
    )
    async def get_focused_element(args: dict) -> dict:
        response = await bridge.send_command("get_focused_element")

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            result = json.dumps({"element": response.get("element", {})})

        return {"content": [{"type": "text", "text": result}]}

    return get_focused_element
