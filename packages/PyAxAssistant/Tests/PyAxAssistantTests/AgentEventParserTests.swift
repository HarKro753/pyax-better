import Testing
import Foundation
@testable import PyAxAssistant

@Suite("AgentEventParser")
struct AgentEventParserTests {

    let sut = AgentEventParser()

    // MARK: - Thinking

    @Test("Parses thinking event")
    func parsesThinkingEvent() {
        let event = sut.parse(eventType: "thinking", data: #"{"status":"reasoning"}"#)

        guard case .thinking(let status) = event else {
            Issue.record("Expected thinking event")
            return
        }
        #expect(status == "reasoning")
    }

    @Test("Thinking event defaults to analyzing_request")
    func thinkingEventDefaults() {
        let event = sut.parse(eventType: "thinking", data: #"{}"#)

        guard case .thinking(let status) = event else {
            Issue.record("Expected thinking event")
            return
        }
        #expect(status == "analyzing_request")
    }

    // MARK: - Tool Call

    @Test("Parses tool_call event")
    func parsesToolCallEvent() {
        let event = sut.parse(eventType: "tool_call", data: #"{"tool":"get_ui_tree","input":{"depth":5}}"#)

        guard case .toolCall(let tool, let inputJSON) = event else {
            Issue.record("Expected toolCall event")
            return
        }
        #expect(tool == "get_ui_tree")
        #expect(inputJSON.contains("5"))
    }

    @Test("Tool call with empty input")
    func toolCallEmptyInput() {
        let event = sut.parse(eventType: "tool_call", data: #"{"tool":"click_element"}"#)

        guard case .toolCall(let tool, _) = event else {
            Issue.record("Expected toolCall event")
            return
        }
        #expect(tool == "click_element")
    }

    // MARK: - Tool Result

    @Test("Parses tool_result event")
    func parsesToolResultEvent() {
        let event = sut.parse(eventType: "tool_result", data: #"{"tool":"find_elements","result":{"elements":[]}}"#)

        guard case .toolResult(let tool, _) = event else {
            Issue.record("Expected toolResult event")
            return
        }
        #expect(tool == "find_elements")
    }

    // MARK: - Message

    @Test("Parses message event")
    func parsesMessageEvent() {
        let event = sut.parse(eventType: "message", data: #"{"content":"Hello, I found the button."}"#)

        guard case .message(let content) = event else {
            Issue.record("Expected message event")
            return
        }
        #expect(content == "Hello, I found the button.")
    }

    @Test("Message event defaults to empty string")
    func messageEventDefaults() {
        let event = sut.parse(eventType: "message", data: #"{}"#)

        guard case .message(let content) = event else {
            Issue.record("Expected message event")
            return
        }
        #expect(content == "")
    }

    // MARK: - Done

    @Test("Parses done event")
    func parsesDoneEvent() {
        let event = sut.parse(eventType: "done", data: #"{}"#)

        guard case .done = event else {
            Issue.record("Expected done event")
            return
        }
    }

    // MARK: - Error

    @Test("Parses error event")
    func parsesErrorEvent() {
        let event = sut.parse(eventType: "error", data: #"{"message":"Bridge disconnected"}"#)

        guard case .error(let message) = event else {
            Issue.record("Expected error event")
            return
        }
        #expect(message == "Bridge disconnected")
    }

    @Test("Error event defaults to Unknown error")
    func errorEventDefaults() {
        let event = sut.parse(eventType: "error", data: #"{}"#)

        guard case .error(let message) = event else {
            Issue.record("Expected error event")
            return
        }
        #expect(message == "Unknown error")
    }

    // MARK: - Highlight

    @Test("Parses highlight event with rects")
    func parsesHighlightEvent() {
        let data = #"{"highlights":[{"x":100,"y":200,"width":50,"height":30,"color":"red","label":"Button"}],"duration":5.0}"#
        let event = sut.parse(eventType: "highlight", data: data)

        guard case .highlight(let rects, let duration) = event else {
            Issue.record("Expected highlight event")
            return
        }
        #expect(rects.count == 1)
        #expect(rects[0].x == 100)
        #expect(rects[0].y == 200)
        #expect(rects[0].width == 50)
        #expect(rects[0].height == 30)
        #expect(rects[0].color == "red")
        #expect(rects[0].label == "Button")
        #expect(duration == 5.0)
    }

    @Test("Highlight event defaults")
    func highlightEventDefaults() {
        let event = sut.parse(eventType: "highlight", data: #"{}"#)

        guard case .highlight(let rects, let duration) = event else {
            Issue.record("Expected highlight event")
            return
        }
        #expect(rects.isEmpty)
        #expect(duration == 3.0)
    }

    // MARK: - Speak

    @Test("Parses speak event")
    func parsesSpeakEvent() {
        let event = sut.parse(eventType: "speak", data: #"{"text":"Hello Alex","rate":0.7}"#)

        guard case .speak(let text, let rate) = event else {
            Issue.record("Expected speak event")
            return
        }
        #expect(text == "Hello Alex")
        #expect(rate == 0.7)
    }

    @Test("Speak event defaults")
    func speakEventDefaults() {
        let event = sut.parse(eventType: "speak", data: #"{}"#)

        guard case .speak(let text, let rate) = event else {
            Issue.record("Expected speak event")
            return
        }
        #expect(text == "")
        #expect(rate == 0.5)
    }

    // MARK: - Clear Highlights

    @Test("Parses clear_highlights event")
    func parsesClearHighlightsEvent() {
        let event = sut.parse(eventType: "clear_highlights", data: #"{}"#)

        guard case .clearHighlights = event else {
            Issue.record("Expected clearHighlights event")
            return
        }
    }

    // MARK: - Edge Cases

    @Test("Returns nil for unknown event type")
    func unknownEventType() {
        let event = sut.parse(eventType: "unknown_type", data: #"{}"#)
        #expect(event == nil)
    }

    @Test("Returns nil for invalid JSON")
    func invalidJSON() {
        let event = sut.parse(eventType: "message", data: "not-json")
        #expect(event == nil)
    }

    @Test("Returns nil for empty data")
    func emptyData() {
        let event = sut.parse(eventType: "message", data: "")
        #expect(event == nil)
    }
}
