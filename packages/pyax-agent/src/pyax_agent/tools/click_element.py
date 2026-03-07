"""Click element tool — performs AXPress on a UI element.

Identifies the element by path (from get_ui_tree or find_elements)
or by search criteria.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_click_element(bridge: BridgeClient):
    """Create a click_element tool with the bridge client captured in closure."""

    @tool(
        "click_element",
        "Click (AXPress) a UI element such as a button, link, menu item, or checkbox. "
        "Identify the element by its path or by search criteria (role, title).",
        {"path": list, "role": str, "title": str},
    )
    async def click_element(args: dict) -> dict:
        path = args.get("path", [])
        role = args.get("role", "")
        title = args.get("title", "")

        kwargs: dict = {"action": "AXPress"}

        if path:
            kwargs["path"] = path
        elif role or title:
            criteria: dict[str, str] = {}
            if role:
                criteria["role"] = role
            if title:
                criteria["title"] = title
            kwargs["criteria"] = criteria
        else:
            result = json.dumps(
                {"error": "Either path or search criteria (role, title) is required"}
            )
            return {"content": [{"type": "text", "text": result}]}

        response = await bridge.send_command("perform_action", **kwargs)

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            result = json.dumps({"success": response.get("success", False)})

        return {"content": [{"type": "text", "text": result}]}

    return click_element
