"""Find elements tool — searches UI elements by role, title, value, or other criteria.

Supports wildcard matching: *text* (contains), text* (starts with), *text (ends with).
Returns matching elements with their paths for later use with get_element or click_element.
"""

import json
import logging

from anthropic import beta_async_tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_find_elements(bridge: BridgeClient):
    """Create a find_elements tool with the bridge client captured in closure."""

    @beta_async_tool
    async def find_elements(
        role: str = "",
        title: str = "",
        value: str = "",
        identifier: str = "",
        description: str = "",
        dom_id: str = "",
        max_results: int = 10,
    ) -> str:
        """Search for UI elements by role, title, value, or other criteria.

        Supports wildcard matching: *text* (contains), text* (starts with), *text (ends with).
        Returns matching elements with their paths for later reference.

        Args:
            role: Element role to match, e.g. 'AXButton', 'AXTextField'. Supports wildcards.
            title: Element title to match. Supports wildcards.
            value: Element value to match. Supports wildcards.
            identifier: Element accessibility identifier to match.
            description: Element accessibility description to match.
            dom_id: DOM element ID to match (for web content).
            max_results: Maximum number of results to return. Default 10.
        """
        criteria: dict[str, str] = {}
        if role:
            criteria["role"] = role
        if title:
            criteria["title"] = title
        if value:
            criteria["value"] = value
        if identifier:
            criteria["identifier"] = identifier
        if description:
            criteria["description"] = description
        if dom_id:
            criteria["dom_id"] = dom_id

        if not criteria:
            return json.dumps(
                {
                    "error": "At least one search criterion is required (role, title, value, identifier, description, or dom_id)"
                }
            )

        response = await bridge.send_command(
            "find_elements",
            criteria=criteria,
            max_results=max_results,
        )

        if "error" in response:
            return json.dumps({"error": response["error"]})

        return json.dumps(
            {
                "app": response.get("app", ""),
                "results": response.get("results", []),
                "count": response.get("count", 0),
            }
        )

    return find_elements
