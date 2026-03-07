"""Tests for the HTTP server endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from pyax_agent.config import AgentConfig
from pyax_agent.models.sse import DoneEvent, MessageEvent, ThinkingEvent
from pyax_agent.server import AgentServer, create_app


def make_config(**kwargs) -> AgentConfig:
    return AgentConfig(**kwargs)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_check(self):
        config = make_config()
        app = create_app(config=config)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["bridge_connected"] is False
        assert data["model"] == "claude-sonnet-4-20250514"
        assert "uptime_seconds" in data

    def test_health_custom_model(self):
        config = make_config(model="claude-opus-4-20250514")
        app = create_app(config=config)
        client = TestClient(app)
        response = client.get("/health")
        assert response.json()["model"] == "claude-opus-4-20250514"


class TestStopEndpoint:
    """Tests for POST /stop."""

    def test_stop_no_agent(self):
        config = make_config()
        app = create_app(config=config)
        client = TestClient(app)
        response = client.post("/stop")
        assert response.status_code == 200
        assert response.json() == {"stopped": True}


class TestChatEndpoint:
    """Tests for POST /chat."""

    def test_invalid_json(self):
        config = make_config()
        app = create_app(config=config)
        client = TestClient(app)
        response = client.post(
            "/chat",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400

    def test_empty_message(self):
        config = make_config()
        app = create_app(config=config)
        client = TestClient(app)
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_missing_message(self):
        config = make_config()
        app = create_app(config=config)
        client = TestClient(app)
        response = client.post("/chat", json={})
        assert response.status_code == 400

    def test_chat_returns_sse_stream(self):
        """Test that /chat returns an SSE stream with proper content type."""
        config = make_config()
        server = AgentServer(config=config)

        # Mock the agent to return a simple response
        mock_agent = AsyncMock()

        async def mock_run(*args, **kwargs):
            yield ThinkingEvent(status="analyzing_request")
            yield MessageEvent(content="Hello!")
            yield DoneEvent()

        mock_agent.run = mock_run
        server._agent = mock_agent

        app = create_app(server=server)
        client = TestClient(app)
        response = client.post("/chat", json={"message": "Hello"})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE events from the response
        text = response.text
        assert "event: thinking" in text
        assert "event: message" in text
        assert "event: done" in text

    def test_chat_sse_headers(self):
        """Test that SSE responses have proper cache control headers."""
        config = make_config()
        server = AgentServer(config=config)

        async def mock_run(*args, **kwargs):
            yield DoneEvent()

        mock_agent = AsyncMock()
        mock_agent.run = mock_run
        server._agent = mock_agent

        app = create_app(server=server)
        client = TestClient(app)
        response = client.post("/chat", json={"message": "Hi"})
        assert response.headers["Cache-Control"] == "no-cache"


class TestAgentServer:
    """Tests for AgentServer internal logic."""

    def test_lazy_agent_init(self):
        server = AgentServer(config=make_config())
        assert server._agent is None
        agent = server.agent
        assert server._agent is not None
        # Second access returns same instance
        assert server.agent is agent

    def test_bridge_created_with_config_url(self):
        config = make_config(bridge_url="ws://localhost:9999")
        server = AgentServer(config=config)
        assert server.bridge.url == "ws://localhost:9999"
