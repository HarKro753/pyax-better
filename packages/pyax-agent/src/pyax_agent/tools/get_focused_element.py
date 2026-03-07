"""Get focused element tool — returns the element with keyboard focus."""

import json
import logging

from anthropic import beta_async_tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_get_focused_element(bridge: BridgeClient):
    """Create a get_focused_element tool with the bridge client captured in closure."""

    @beta_async_tool
    async def get_focused_element() -> str:
        """Get the UI element that currently has keyboard focus.

        Useful for understanding what the user is currently interacting with.
        """
        response = await bridge.send_command("get_focused_element")

        if "error" in response:
            return json.dumps({"error": response["error"]})

        return json.dumps({"element": response.get("element", {})})

    return get_focused_element
