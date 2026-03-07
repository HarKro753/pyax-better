"""Highlight elements tool — emit SSE side-event for Swift to draw highlights.

This tool does NOT call the bridge. It emits a HighlightEvent via the
EventEmitter so the Swift frontend draws overlay rectangles on screen.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.event_emitter import EventEmitter
from pyax_agent.models.sse import HighlightEvent

logger = logging.getLogger(__name__)


def create_highlight_elements(emitter: EventEmitter):
    """Create a highlight_elements tool with the event emitter captured in closure."""

    @tool(
        "highlight_elements",
        "Highlight UI elements on screen by drawing colored overlay rectangles. "
        "Provide a list of highlights, each with x, y, width, height, color, and label. "
        "The Swift frontend will render these overlays for the specified duration.",
        {"highlights": list, "duration": float},
    )
    async def highlight_elements(args: dict) -> dict:
        highlights = args.get("highlights", [])
        duration = args.get("duration", 3.0)

        if not highlights:
            result = json.dumps({"error": "highlights list is required and cannot be empty"})
            return {"content": [{"type": "text", "text": result}]}

        # Emit the SSE side-event for the Swift frontend
        await emitter.emit(HighlightEvent(highlights=highlights, duration=duration))

        result = json.dumps({"success": True, "count": len(highlights)})
        return {"content": [{"type": "text", "text": result}]}

    return highlight_elements
