"""Scroll tool — scroll a scrollable area up or down.

Sends AXScrollUp/AXScrollDown (or AXIncrement/AXDecrement) to the bridge.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_scroll(bridge: BridgeClient):
    """Create a scroll tool with the bridge client captured in closure."""

    @tool(
        "scroll",
        "Scroll a scrollable area up or down. Identify the element by path or "
        "by search criteria (role, title). Specify direction ('up' or 'down') "
        "and optionally an amount (number of scroll steps, default 3).",
        {"path": list, "role": str, "title": str, "direction": str, "amount": int},
    )
    async def scroll(args: dict) -> dict:
        path = args.get("path", [])
        role = args.get("role", "")
        title = args.get("title", "")
        direction = args.get("direction", "down")
        amount = args.get("amount", 3)

        if direction not in ("up", "down"):
            result = json.dumps({"error": "direction must be 'up' or 'down'"})
            return {"content": [{"type": "text", "text": result}]}

        # Map direction to AX action
        action = "AXScrollUp" if direction == "up" else "AXScrollDown"

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

        # Perform the scroll action `amount` times
        response: dict = {}
        for _ in range(amount):
            response = await bridge.send_command("perform_action", **kwargs)
            if "error" in response:
                result = json.dumps({"error": response["error"]})
                return {"content": [{"type": "text", "text": result}]}

        result = json.dumps({"success": True, "direction": direction, "amount": amount})
        return {"content": [{"type": "text", "text": result}]}

    return scroll
