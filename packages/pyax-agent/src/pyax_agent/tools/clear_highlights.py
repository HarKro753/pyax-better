"""Clear highlights tool — emit SSE side-event for Swift to remove highlights.

This tool does NOT call the bridge. It emits a ClearHighlightsEvent via the
EventEmitter so the Swift frontend removes all overlay rectangles.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.event_emitter import EventEmitter
from pyax_agent.models.sse import ClearHighlightsEvent

logger = logging.getLogger(__name__)


def create_clear_highlights(emitter: EventEmitter):
    """Create a clear_highlights tool with the event emitter captured in closure."""

    @tool(
        "clear_highlights",
        "Clear all UI element highlights from the screen. "
        "Removes any overlay rectangles previously drawn by highlight_elements.",
        {},
    )
    async def clear_highlights(args: dict) -> dict:
        # Emit the SSE side-event for the Swift frontend
        await emitter.emit(ClearHighlightsEvent())

        result = json.dumps({"success": True})
        return {"content": [{"type": "text", "text": result}]}

    return clear_highlights
