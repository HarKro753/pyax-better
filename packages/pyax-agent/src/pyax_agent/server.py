"""HTTP server with SSE streaming for the pyax agent.

Provides three endpoints:
- POST /chat   → SSE stream of agent thinking, tool calls, and responses
- POST /stop   → Cancel the current agent loop
- GET  /health → Status check
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from pyax_agent.agent import AgentLoop
from pyax_agent.bridge_client import BridgeClient
from pyax_agent.config import AgentConfig, get_config
from pyax_agent.memory import MemoryManager
from pyax_agent.models.api import ChatRequest, ErrorResponse
from pyax_agent.models.sse import DoneEvent, ErrorEvent, sse_serialize

logger = logging.getLogger(__name__)


class AgentServer:
    """The pyax agent HTTP server.

    Manages the agent loop, bridge client, and HTTP endpoints.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or get_config()
        self.bridge = BridgeClient(url=self.config.bridge_url)
        self._agent: AgentLoop | None = None
        self._start_time = time.time()
        self._conversation_history: dict[str, list[dict[str, Any]]] = {}

        # Create memory manager if memory_dir is configured
        self._memory_manager: MemoryManager | None = None
        if self.config.memory_dir:
            self._memory_manager = MemoryManager(self.config.memory_dir)
            self._memory_manager.ensure_files()

    @property
    def agent(self) -> AgentLoop:
        """Lazy-initialize the agent loop."""
        if self._agent is None:
            self._agent = AgentLoop(
                config=self.config,
                bridge=self.bridge,
                memory_manager=self._memory_manager,
            )
        return self._agent

    async def chat(self, request: Request) -> StreamingResponse | JSONResponse:
        """Handle POST /chat — run the agent and stream SSE events."""
        try:
            body = await request.json()
        except Exception:
            err = ErrorResponse(error="Invalid JSON body")
            return JSONResponse(err.to_dict(), status_code=400)

        chat_req = ChatRequest.from_dict(body)
        errors = chat_req.validate()
        if errors:
            err = ErrorResponse(error="; ".join(errors))
            return JSONResponse(err.to_dict(), status_code=400)

        # Get or create conversation history
        conv_id = chat_req.conversation_id or "default"
        history = self._conversation_history.get(conv_id, [])

        async def event_stream():
            try:
                async for event in self.agent.run(
                    message=chat_req.message,
                    conversation_history=history,
                ):
                    yield sse_serialize(event)
            except Exception as e:
                logger.error("Chat stream error: %s", e)
                yield sse_serialize(ErrorEvent(message=str(e)))
                yield sse_serialize(DoneEvent())

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def stop(self, request: Request) -> JSONResponse:
        """Handle POST /stop — cancel the current agent loop."""
        if self._agent:
            self._agent.cancel()
        return JSONResponse({"stopped": True})

    async def health(self, request: Request) -> JSONResponse:
        """Handle GET /health — return server status."""
        uptime = time.time() - self._start_time
        return JSONResponse(
            {
                "status": "ok",
                "bridge_connected": self.bridge.connected,
                "model": self.config.model,
                "uptime_seconds": round(uptime, 1),
            }
        )


def create_app(
    config: AgentConfig | None = None,
    server: AgentServer | None = None,
) -> Starlette:
    """Create and return the Starlette ASGI application.

    Args:
        config: Agent configuration. Used only if server is not provided.
        server: Optional pre-configured AgentServer instance (useful for testing).
    """
    if server is None:
        server = AgentServer(config=config)

    routes = [
        Route("/chat", server.chat, methods=["POST"]),
        Route("/stop", server.stop, methods=["POST"]),
        Route("/health", server.health, methods=["GET"]),
    ]

    return Starlette(routes=routes)


# Default app instance for uvicorn
app = create_app()
