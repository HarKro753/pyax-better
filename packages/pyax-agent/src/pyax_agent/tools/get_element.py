"""Get element tool — retrieves details about a specific UI element by path.

The path is an array of child indices from the root element,
e.g. [0, 3, 2] means: first child, then fourth child, then third child.
"""

import json
import logging

from anthropic import beta_async_tool

from pyax_agent.bridge_client import BridgeClient

logger = logging.getLogger(__name__)


def create_get_element(bridge: BridgeClient):
    """Create a get_element tool with the bridge client captured in closure."""

    @beta_async_tool
    async def get_element(path: list[int], depth: int = 1) -> str:
        """Get detailed information about a specific UI element by its path.

        The path is an array of child indices from the root element.

        Args:
            path: Child index path from root element, e.g. [0, 3, 2].
            depth: How deep to recurse into children. Default 1.
        """
        response = await bridge.send_command("get_element", path=path, depth=depth)

        if "error" in response:
            return json.dumps({"error": response["error"]})

        return json.dumps(
            {
                "path": response.get("path", path),
                "element": response.get("element", {}),
            }
        )

    return get_element
