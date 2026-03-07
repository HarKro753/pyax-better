"""Tests for the bridge WebSocket client."""

import asyncio
import json

import pytest

from pyax_agent.bridge_client import BridgeClient


class TestBridgeClientInit:
    """Tests for BridgeClient initialization."""

    def test_default_url(self):
        client = BridgeClient()
        assert client.url == "ws://localhost:8765"
        assert client.connected is False

    def test_custom_url(self):
        client = BridgeClient(url="ws://localhost:9999")
        assert client.url == "ws://localhost:9999"

    def test_not_connected_initially(self):
        client = BridgeClient()
        assert client.connected is False


class TestBridgeClientCommands:
    """Tests for bridge command sending with a mock WebSocket."""

    @pytest.fixture
    def mock_bridge(self):
        """Create a bridge client with a mock WebSocket."""
        client = BridgeClient()
        client._connected = True

        # Mock WebSocket that captures sent messages and returns canned responses
        class MockWS:
            def __init__(self):
                self.sent: list[str] = []
                self._response: dict | None = None

            async def send(self, data: str):
                self.sent.append(data)
                msg = json.loads(data)
                if self._response and msg.get("id"):
                    # Simulate the receive loop resolving the future
                    req_id = msg["id"]
                    if req_id in client._pending:
                        response = {**self._response, "id": req_id, "type": "response"}
                        future = client._pending.pop(req_id)
                        if not future.done():
                            future.set_result(response)

            async def close(self):
                pass

            def set_response(self, resp: dict):
                self._response = resp

        ws = MockWS()
        client._ws = ws
        return client, ws

    @pytest.mark.asyncio
    async def test_send_command_not_connected(self):
        client = BridgeClient()
        with pytest.raises(ConnectionError):
            await client.send_command("get_tree")

    @pytest.mark.asyncio
    async def test_send_command_success(self, mock_bridge):
        client, ws = mock_bridge
        ws.set_response(
            {
                "command": "get_tree",
                "app": "Finder",
                "pid": 123,
                "tree": {"AXRole": "AXApplication"},
            }
        )

        result = await client.send_command("get_tree", depth=3)
        assert result["command"] == "get_tree"
        assert result["app"] == "Finder"

        # Verify the sent message
        sent = json.loads(ws.sent[0])
        assert sent["type"] == "command"
        assert sent["command"] == "get_tree"
        assert sent["depth"] == 3
        assert "id" in sent

    @pytest.mark.asyncio
    async def test_send_command_with_kwargs(self, mock_bridge):
        client, ws = mock_bridge
        ws.set_response(
            {
                "command": "find_elements",
                "results": [{"AXRole": "AXButton"}],
                "count": 1,
            }
        )

        result = await client.send_command(
            "find_elements",
            criteria={"role": "AXButton"},
            max_results=5,
        )
        assert result["count"] == 1

        sent = json.loads(ws.sent[0])
        assert sent["criteria"] == {"role": "AXButton"}
        assert sent["max_results"] == 5

    @pytest.mark.asyncio
    async def test_send_command_error_response(self, mock_bridge):
        client, ws = mock_bridge
        ws.set_response({"error": "No focused application"})

        result = await client.send_command("get_tree")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_bridge):
        client, ws = mock_bridge
        await client.disconnect()
        assert client.connected is False
        assert client._ws is None


class TestBridgeClientReceiveLoop:
    """Tests for the receive loop message routing."""

    @pytest.mark.asyncio
    async def test_response_routing(self):
        """Test that responses are routed to the correct pending future."""
        client = BridgeClient()
        client._connected = True

        # Create a pending future
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        client._pending["req-123"] = future

        # Simulate receiving a response
        msg = {"type": "response", "id": "req-123", "data": "test"}

        # Manually call the routing logic
        msg_type = msg.get("type")
        msg_id = msg.get("id")
        if msg_type == "response" and msg_id and msg_id in client._pending:
            f = client._pending.pop(msg_id)
            if not f.done():
                f.set_result(msg)

        result = await future
        assert result["data"] == "test"
        assert "req-123" not in client._pending

    @pytest.mark.asyncio
    async def test_ping(self):
        """Test ping sends the right message."""
        client = BridgeClient()
        assert await client.ping() is False  # Not connected

        # Mock connected state
        sent = []

        class MockWS:
            async def send(self, data: str):
                sent.append(json.loads(data))

            async def close(self):
                pass

        client._ws = MockWS()
        client._connected = True
        result = await client.ping()
        assert result is True
        assert sent[0] == {"type": "ping"}
