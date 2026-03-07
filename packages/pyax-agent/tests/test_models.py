"""Tests for API and SSE models."""

import json

from pyax_agent.models.api import ChatMessage, ChatRequest, ErrorResponse
from pyax_agent.models.sse import (
    ClearHighlightsEvent,
    DoneEvent,
    ErrorEvent,
    HighlightEvent,
    MessageEvent,
    SpeakEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    sse_serialize,
)


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_creation(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_to_dict(self):
        msg = ChatMessage(role="assistant", content="Hi there")
        d = msg.to_dict()
        assert d == {"role": "assistant", "content": "Hi there"}


class TestChatRequest:
    """Tests for ChatRequest model."""

    def test_from_dict_full(self):
        req = ChatRequest.from_dict(
            {
                "message": "Click the button",
                "conversation_id": "conv-123",
            }
        )
        assert req.message == "Click the button"
        assert req.conversation_id == "conv-123"

    def test_from_dict_minimal(self):
        req = ChatRequest.from_dict({"message": "Hello"})
        assert req.message == "Hello"
        assert req.conversation_id == ""

    def test_from_dict_empty(self):
        req = ChatRequest.from_dict({})
        assert req.message == ""
        assert req.conversation_id == ""

    def test_validate_valid(self):
        req = ChatRequest(message="Click the button")
        assert req.validate() == []

    def test_validate_empty_message(self):
        req = ChatRequest(message="")
        errors = req.validate()
        assert len(errors) == 1
        assert "message" in errors[0]

    def test_validate_whitespace_message(self):
        req = ChatRequest(message="   ")
        errors = req.validate()
        assert len(errors) == 1

    def test_validate_with_conversation_id(self):
        req = ChatRequest(message="Hello", conversation_id="conv-1")
        assert req.validate() == []


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_creation(self):
        err = ErrorResponse(error="Bad request")
        assert err.error == "Bad request"
        assert err.status_code == 400

    def test_custom_status(self):
        err = ErrorResponse(error="Not found", status_code=404)
        assert err.status_code == 404

    def test_to_dict(self):
        err = ErrorResponse(error="Server error")
        assert err.to_dict() == {"error": "Server error"}


class TestThinkingEvent:
    """Tests for ThinkingEvent."""

    def test_default_status(self):
        event = ThinkingEvent()
        assert event.event == "thinking"
        assert event.status == "analyzing_request"

    def test_custom_status(self):
        event = ThinkingEvent(status="executing_tool")
        assert event.status == "executing_tool"

    def test_data_dict(self):
        event = ThinkingEvent(status="planning")
        assert event.data_dict() == {"status": "planning"}


class TestToolCallEvent:
    """Tests for ToolCallEvent."""

    def test_creation(self):
        event = ToolCallEvent(tool="find_elements", input={"criteria": {"role": "AXButton"}})
        assert event.event == "tool_call"
        assert event.tool == "find_elements"
        assert event.input == {"criteria": {"role": "AXButton"}}

    def test_default_input(self):
        event = ToolCallEvent(tool="get_ui_tree")
        assert event.input == {}

    def test_data_dict(self):
        event = ToolCallEvent(tool="click_element", input={"path": [0, 1]})
        d = event.data_dict()
        assert d == {"tool": "click_element", "input": {"path": [0, 1]}}


class TestToolResultEvent:
    """Tests for ToolResultEvent."""

    def test_creation(self):
        result = {"app": "Safari", "results": [], "count": 0}
        event = ToolResultEvent(tool="find_elements", result=result)
        assert event.event == "tool_result"
        assert event.tool == "find_elements"
        assert event.result == result

    def test_data_dict(self):
        event = ToolResultEvent(tool="get_ui_tree", result={"tree": {}})
        d = event.data_dict()
        assert d == {"tool": "get_ui_tree", "result": {"tree": {}}}


class TestHighlightEvent:
    """Tests for HighlightEvent."""

    def test_creation(self):
        highlights = [{"x": 100, "y": 200, "w": 50, "h": 30, "color": "#FF0000"}]
        event = HighlightEvent(highlights=highlights, duration=5.0)
        assert event.event == "highlight"
        assert event.highlights == highlights
        assert event.duration == 5.0

    def test_defaults(self):
        event = HighlightEvent()
        assert event.highlights == []
        assert event.duration == 3.0

    def test_data_dict(self):
        event = HighlightEvent(
            highlights=[{"x": 0, "y": 0, "w": 100, "h": 100}],
            duration=2.0,
        )
        d = event.data_dict()
        assert d["highlights"] == [{"x": 0, "y": 0, "w": 100, "h": 100}]
        assert d["duration"] == 2.0


class TestClearHighlightsEvent:
    """Tests for ClearHighlightsEvent."""

    def test_creation(self):
        event = ClearHighlightsEvent()
        assert event.event == "clear_highlights"

    def test_data_dict(self):
        event = ClearHighlightsEvent()
        assert event.data_dict() == {}


class TestSpeakEvent:
    """Tests for SpeakEvent."""

    def test_creation(self):
        event = SpeakEvent(text="Hello world", rate=0.3)
        assert event.event == "speak"
        assert event.text == "Hello world"
        assert event.rate == 0.3

    def test_defaults(self):
        event = SpeakEvent()
        assert event.text == ""
        assert event.rate == 0.5

    def test_data_dict(self):
        event = SpeakEvent(text="Clicked the button", rate=0.4)
        assert event.data_dict() == {"text": "Clicked the button", "rate": 0.4}


class TestMessageEvent:
    """Tests for MessageEvent."""

    def test_creation(self):
        event = MessageEvent(content="I clicked the Submit button.")
        assert event.event == "message"
        assert event.content == "I clicked the Submit button."

    def test_data_dict(self):
        event = MessageEvent(content="Done!")
        assert event.data_dict() == {"content": "Done!"}


class TestDoneEvent:
    """Tests for DoneEvent."""

    def test_creation(self):
        event = DoneEvent()
        assert event.event == "done"

    def test_data_dict(self):
        event = DoneEvent()
        assert event.data_dict() == {}


class TestErrorEvent:
    """Tests for ErrorEvent."""

    def test_creation(self):
        event = ErrorEvent(message="Something went wrong")
        assert event.event == "error"
        assert event.message == "Something went wrong"

    def test_data_dict(self):
        event = ErrorEvent(message="Timeout")
        assert event.data_dict() == {"message": "Timeout"}


class TestSSESerialize:
    """Tests for SSE serialization."""

    def test_thinking_event(self):
        event = ThinkingEvent(status="analyzing_request")
        result = sse_serialize(event)
        assert result.startswith("event: thinking\n")
        assert "data: " in result
        assert result.endswith("\n\n")
        data = json.loads(result.split("data: ")[1].strip())
        assert data == {"status": "analyzing_request"}

    def test_message_event(self):
        event = MessageEvent(content="Hello!")
        result = sse_serialize(event)
        assert "event: message\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert data == {"content": "Hello!"}

    def test_done_event(self):
        event = DoneEvent()
        result = sse_serialize(event)
        assert "event: done\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert data == {}

    def test_error_event(self):
        event = ErrorEvent(message="fail")
        result = sse_serialize(event)
        assert "event: error\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert data == {"message": "fail"}

    def test_tool_call_event(self):
        event = ToolCallEvent(tool="find_elements", input={"criteria": {"role": "AXButton"}})
        result = sse_serialize(event)
        assert "event: tool_call\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert data["tool"] == "find_elements"
        assert data["input"]["criteria"]["role"] == "AXButton"

    def test_highlight_event(self):
        event = HighlightEvent(
            highlights=[{"x": 10, "y": 20, "w": 30, "h": 40}],
            duration=2.5,
        )
        result = sse_serialize(event)
        assert "event: highlight\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert len(data["highlights"]) == 1
        assert data["duration"] == 2.5

    def test_speak_event(self):
        event = SpeakEvent(text="Hello", rate=0.4)
        result = sse_serialize(event)
        assert "event: speak\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert data["text"] == "Hello"
        assert data["rate"] == 0.4

    def test_compact_json(self):
        """SSE data should use compact JSON (no extra spaces)."""
        event = MessageEvent(content="test")
        result = sse_serialize(event)
        data_line = result.split("data: ")[1].strip()
        # Compact JSON has no spaces after : or ,
        assert ": " not in data_line or data_line == '{"content":"test"}'
        assert data_line == '{"content":"test"}'
