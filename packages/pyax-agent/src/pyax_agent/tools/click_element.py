"""Click element tool — performs AXPress on a UI element.

Identifies the element by path (from get_ui_tree or find_elements)
or by search criteria.
"""

import json
import logging

from anthropic import beta_async_tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_click_element(bridge: BridgeClient):
    """Create a click_element tool with the bridge client captured in closure."""

    @beta_async_tool
    async def click_element(
        path: list[int] = [],
        role: str = "",
        title: str = "",
    ) -> str:
        """Click (AXPress) a UI element such as a button, link, menu item, or checkbox.

        Identify the element by its path or by search criteria (role, title).

        Args:
            path: Child index path to the element, e.g. [0, 3, 2]. Use this if you know the path from a previous get_ui_tree or find_elements call.
            role: Element role to search for, e.g. 'AXButton'. Used when path is not provided.
            title: Element title to search for, e.g. 'Submit'. Used when path is not provided.
        """
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
            return json.dumps({"error": "Either path or search criteria (role, title) is required"})

        response = await bridge.send_command("perform_action", **kwargs)

        if "error" in response:
            return json.dumps({"error": response["error"]})

        return json.dumps({"success": response.get("success", False)})

    return click_element
