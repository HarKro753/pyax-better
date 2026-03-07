"""Speak text tool — emit SSE side-event for Swift to speak text aloud.

This tool does NOT call the bridge. It emits a SpeakEvent via the
EventEmitter so the Swift frontend uses text-to-speech.
"""

import json
import logging

from claude_agent_sdk import tool

from pyax_agent.event_emitter import EventEmitter
from pyax_agent.models.sse import SpeakEvent

logger = logging.getLogger(__name__)


def create_speak_text(emitter: EventEmitter):
    """Create a speak_text tool with the event emitter captured in closure."""

    @tool(
        "speak_text",
        "Speak text aloud using the system's text-to-speech engine. "
        "Useful for providing audio feedback to users with visual impairments. "
        "Optionally set the speech rate (0.0 = slowest, 1.0 = fastest, default 0.5).",
        {"text": str, "rate": float},
    )
    async def speak_text(args: dict) -> dict:
        text = args.get("text", "")
        rate = args.get("rate", 0.5)

        if not text:
            result = json.dumps({"error": "text parameter is required"})
            return {"content": [{"type": "text", "text": result}]}

        # Emit the SSE side-event for the Swift frontend
        await emitter.emit(SpeakEvent(text=text, rate=rate))

        result = json.dumps({"success": True})
        return {"content": [{"type": "text", "text": result}]}

    return speak_text
