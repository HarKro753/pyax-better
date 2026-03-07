"""Event emitter for tool-to-SSE side-events.

Tools that need to emit SSE events to the Swift frontend (highlight, speak, etc.)
push events onto this queue. The agent loop drains the queue between processing
SDK messages and yields them into the SSE stream.
"""

from __future__ import annotations

import asyncio

from pyax_agent.models.sse import SSEEvent


class EventEmitter:
    """Thread-safe queue for SSE side-events emitted by tools."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[SSEEvent] = asyncio.Queue()

    async def emit(self, event: SSEEvent) -> None:
        """Push an SSE event onto the queue."""
        await self._queue.put(event)

    def drain(self) -> list[SSEEvent]:
        """Non-blocking drain: return all queued events and clear the queue."""
        events: list[SSEEvent] = []
        while not self._queue.empty():
            try:
                events.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events
