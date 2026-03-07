"""Type text tool — sets text in a text field by focusing it and setting AXValue.

Identifies the text field by path or by search criteria.
"""

import json
import logging

from anthropic import beta_async_tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_type_text(bridge: BridgeClient):
    """Create a type_text tool with the bridge client captured in closure."""

    @beta_async_tool
    async def type_text(
        text: str,
        path: list[int] = [],
        role: str = "",
        title: str = "",
    ) -> str:
        """Type text into a text field. Focuses the element and sets its value.

        Identify the text field by path or by search criteria (role, title).

        Args:
            text: The text to type into the field.
            path: Child index path to the text field. Use this if you know the path from a previous call.
            role: Element role to search for, e.g. 'AXTextField'. Used when path is not provided.
            title: Element title to search for. Used when path is not provided.
        """
        if not text:
            return json.dumps({"error": "text parameter is required"})

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
            return json.dumps({"error": "Either path or search criteria (role, title) is required"})

        # Focus the element first
        await bridge.send_command(
            "set_attribute", attribute="AXFocused", value=True, **target_kwargs
        )

        # Then set the value
        response = await bridge.send_command(
            "set_attribute", attribute="AXValue", value=text, **target_kwargs
        )

        if "error" in response:
            return json.dumps({"error": response["error"]})

        return json.dumps({"success": response.get("success", False)})

    return type_text
