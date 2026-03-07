"""Type text tool — sets text in a text field by focusing it and setting AXValue.

Identifies the text field by path or by search criteria.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_type_text(bridge: BridgeClient):
    """Create a type_text tool with the bridge client captured in closure."""

    @tool(
        "type_text",
        "Type text into a text field. Focuses the element and sets its value. "
        "Identify the text field by path or by search criteria (role, title).",
        {"text": str, "path": list, "role": str, "title": str},
    )
    async def type_text(args: dict) -> dict:
        text = args.get("text", "")
        path = args.get("path", [])
        role = args.get("role", "")
        title = args.get("title", "")

        if not text:
            result = json.dumps({"error": "text parameter is required"})
            return {"content": [{"type": "text", "text": result}]}

        # Build targeting kwargs
        target_kwargs: dict = {}
        if path:
            target_kwargs["path"] = path
        elif role or title:
            criteria: dict[str, str] = {}
            if role:
                criteria["role"] = role
            if title:
                criteria["title"] = title
            target_kwargs["criteria"] = criteria
        else:
            result = json.dumps(
                {"error": "Either path or search criteria (role, title) is required"}
            )
            return {"content": [{"type": "text", "text": result}]}

        # Focus the element first
        await bridge.send_command(
            "set_attribute", attribute="AXFocused", value=True, **target_kwargs
        )

        # Then set the value
        response = await bridge.send_command(
            "set_attribute", attribute="AXValue", value=text, **target_kwargs
        )

        if "error" in response:
            result = json.dumps({"error": response["error"]})
        else:
            result = json.dumps({"success": response.get("success", False)})

        return {"content": [{"type": "text", "text": result}]}

    return type_text
