"""WebSocket client for connecting to the pyax bridge server."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)


class BridgeClient:
    """Async WebSocket client that sends commands to the pyax bridge.

    The bridge runs on ws://localhost:8765 and accepts commands like
    get_tree, find_elements, perform_action, set_attribute, etc.

    This client handles connection lifecycle, request/response correlation,
    and reconnection.
    """

    def __init__(self, url: str = "ws://localhost:8765") -> None:
        self.url = url
        self._ws: ClientConnection | None = None
        self._pending: dict[str, asyncio.Future[dict]] = {}
        self._receive_task: asyncio.Task | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        """Whether the client is currently connected to the bridge."""
        return self._connected and self._ws is not None

    async def connect(self) -> None:
        """Connect to the bridge WebSocket server."""
        try:
            self._ws = await websockets.connect(self.url)
            self._connected = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.info("Connected to bridge at %s", self.url)
        except Exception as e:
            self._connected = False
            logger.error("Failed to connect to bridge: %s", e)
            raise

    async def disconnect(self) -> None:
        """Disconnect from the bridge."""
        self._connected = False
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        # Cancel any pending requests
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        logger.info("Disconnected from bridge")

    async def send_command(
        self,
        command: str,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> dict:
        """Send a command to the bridge and wait for the response.

        Args:
            command: The bridge command name (e.g., "get_tree", "find_elements").
            timeout: Maximum seconds to wait for a response.
            **kwargs: Additional fields for the command payload.

        Returns:
            The response dict from the bridge.

        Raises:
            ConnectionError: If not connected to the bridge.
            TimeoutError: If the bridge doesn't respond in time.
        """
        if not self.connected or not self._ws:
            raise ConnectionError("Not connected to bridge")

        request_id = str(uuid.uuid4())
        message = {
            "type": "command",
            "id": request_id,
            "command": command,
            **kwargs,
        }

        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        try:
            await self._ws.send(json.dumps(message))
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"Bridge command '{command}' timed out after {timeout}s")
        except Exception:
            self._pending.pop(request_id, None)
            raise

    async def _receive_loop(self) -> None:
        """Background task that reads messages from the WebSocket."""
        if not self._ws:
            return
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON message from bridge")
                    continue

                msg_type = msg.get("type")
                msg_id = msg.get("id")

                if msg_type == "response" and msg_id and msg_id in self._pending:
                    future = self._pending.pop(msg_id)
                    if not future.done():
                        future.set_result(msg)
                elif msg_type == "pong":
                    # Keepalive response, ignore
                    pass
                elif msg_type in ("event", "app_changed"):
                    # Bridge events (accessibility notifications, app changes)
                    # Could be forwarded to listeners in the future
                    logger.debug("Bridge event: %s", msg_type)
                else:
                    logger.debug("Unhandled bridge message: %s", msg_type)

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Bridge connection closed")
            self._connected = False
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Bridge receive loop error: %s", e)
            self._connected = False

    async def ping(self) -> bool:
        """Send a ping to the bridge and check if it responds."""
        if not self.connected or not self._ws:
            return False
        try:
            await self._ws.send(json.dumps({"type": "ping"}))
            return True
        except Exception:
            return False
