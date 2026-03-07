"""Server-Sent Events models and serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    """Base SSE event."""

    event: str

    def data_dict(self) -> dict[str, Any]:
        """Return the data payload as a dict."""
        raise NotImplementedError


@dataclass
class ThinkingEvent(SSEEvent):
    """Agent is processing."""

    status: str = "analyzing_request"

    def __init__(self, status: str = "analyzing_request"):
        super().__init__(event="thinking")
        self.status = status

    def data_dict(self) -> dict[str, Any]:
        return {"status": self.status}


@dataclass
class ToolCallEvent(SSEEvent):
    """Agent is calling a tool."""

    tool: str = ""
    input: dict[str, Any] = field(default_factory=dict)

    def __init__(self, tool: str = "", input: dict[str, Any] | None = None):
        super().__init__(event="tool_call")
        self.tool = tool
        self.input = input or {}

    def data_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "input": self.input}


@dataclass
class ToolResultEvent(SSEEvent):
    """Tool returned a result."""

    tool: str = ""
    result: Any = None

    def __init__(self, tool: str = "", result: Any = None):
        super().__init__(event="tool_result")
        self.tool = tool
        self.result = result

    def data_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "result": self.result}


@dataclass
class HighlightEvent(SSEEvent):
    """Swift should draw highlights."""

    highlights: list[dict[str, Any]] = field(default_factory=list)
    duration: float = 3.0

    def __init__(self, highlights: list[dict[str, Any]] | None = None, duration: float = 3.0):
        super().__init__(event="highlight")
        self.highlights = highlights or []
        self.duration = duration

    def data_dict(self) -> dict[str, Any]:
        return {"highlights": self.highlights, "duration": self.duration}


@dataclass
class ClearHighlightsEvent(SSEEvent):
    """Swift should clear highlights."""

    def __init__(self):
        super().__init__(event="clear_highlights")

    def data_dict(self) -> dict[str, Any]:
        return {}


@dataclass
class SpeakEvent(SSEEvent):
    """Swift should speak text aloud."""

    text: str = ""
    rate: float = 0.5

    def __init__(self, text: str = "", rate: float = 0.5):
        super().__init__(event="speak")
        self.text = text
        self.rate = rate

    def data_dict(self) -> dict[str, Any]:
        return {"text": self.text, "rate": self.rate}


@dataclass
class MessageEvent(SSEEvent):
    """Final text response from agent."""

    content: str = ""

    def __init__(self, content: str = ""):
        super().__init__(event="message")
        self.content = content

    def data_dict(self) -> dict[str, Any]:
        return {"content": self.content}


@dataclass
class DoneEvent(SSEEvent):
    """Stream is complete."""

    def __init__(self):
        super().__init__(event="done")

    def data_dict(self) -> dict[str, Any]:
        return {}


@dataclass
class ErrorEvent(SSEEvent):
    """Something went wrong."""

    message: str = ""

    def __init__(self, message: str = ""):
        super().__init__(event="error")
        self.message = message

    def data_dict(self) -> dict[str, Any]:
        return {"message": self.message}


def sse_serialize(event: SSEEvent) -> str:
    """Serialize an SSE event to wire format.

    Format: event: <type>\ndata: <json>\n\n
    """
    data = json.dumps(event.data_dict(), separators=(",", ":"))
    return f"event: {event.event}\ndata: {data}\n\n"
