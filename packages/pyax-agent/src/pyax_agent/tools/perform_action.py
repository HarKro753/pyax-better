"""Perform action tool — perform any AX action on a UI element.

Supports actions like AXShowMenu, AXConfirm, AXCancel, AXRaise, etc.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_perform_action(bridge: BridgeClient):
    """Create a perform_action tool with the bridge client captured in closure."""

    @tool(
        "perform_action",
        "Perform any accessibility action on a UI element. Common actions include "
        "AXShowMenu, AXConfirm, AXCancel, AXRaise, AXPick, AXIncrement, AXDecrement. "
        "Identify the element by path or by search criteria (role, title).",
        {"path": list, "role": str, "title": str, "action": str},
    )
    async def perform_action(args: dict) -> dict:
        path = args.get("path", [])
        role = args.get("role", "")
        title = args.get("title", "")
        action = args.get("action", "")

        if not action:
            result = json.dumps({"error": "action parameter is required"})
            return {"content": [{"type": "text", "text": result}]}

        kwargs: dict = {"action": action}

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

    return perform_action
