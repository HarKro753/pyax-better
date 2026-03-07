import Testing
import Foundation
@testable import PyAxAssistant

@Suite("ChatMessage")
struct ChatMessageTests {

    @Test("Creates user message with defaults")
    func userMessage() {
        let msg = ChatMessage(role: .user, content: "Hello")

        #expect(msg.role == .user)
        #expect(msg.content == "Hello")
    }

    @Test("Creates assistant message")
    func assistantMessage() {
        let msg = ChatMessage(role: .assistant, content: "I'll help you")

        #expect(msg.role == .assistant)
        #expect(msg.content == "I'll help you")
    }

    @Test("Creates error message")
    func errorMessage() {
        let msg = ChatMessage(role: .error, content: "Something went wrong")

        #expect(msg.role == .error)
        #expect(msg.content == "Something went wrong")
    }

    @Test("Creates tool call message")
    func toolCallMessage() {
        let msg = ChatMessage(role: .toolCall(tool: "get_ui_tree"), content: "{}")

        if case .toolCall(let tool) = msg.role {
            #expect(tool == "get_ui_tree")
        } else {
            Issue.record("Expected toolCall role")
        }
    }

    @Test("Creates tool result message")
    func toolResultMessage() {
        let msg = ChatMessage(role: .toolResult(tool: "click_element"), content: "success")

        if case .toolResult(let tool) = msg.role {
            #expect(tool == "click_element")
        } else {
            Issue.record("Expected toolResult role")
        }
    }

    @Test("Equality is based on id and content")
    func equality() {
        let id = UUID()
        let msg1 = ChatMessage(id: id, role: .user, content: "Hello")
        let msg2 = ChatMessage(id: id, role: .user, content: "Hello")
        let msg3 = ChatMessage(id: id, role: .user, content: "Different")

        #expect(msg1 == msg2)
        #expect(msg1 != msg3)
    }

    @Test("Different ids are not equal")
    func differentIds() {
        let msg1 = ChatMessage(role: .user, content: "Same content")
        let msg2 = ChatMessage(role: .user, content: "Same content")

        #expect(msg1 != msg2)
    }
}

@Suite("AgentStatus")
struct AgentStatusTests {

    @Test("Idle status")
    func idleStatus() {
        let status = AgentStatus.idle
        #expect(status == .idle)
    }

    @Test("Thinking status")
    func thinkingStatus() {
        let status = AgentStatus.thinking(status: "reasoning")
        #expect(status == .thinking(status: "reasoning"))
    }

    @Test("Calling tool status")
    func callingToolStatus() {
        let status = AgentStatus.callingTool(tool: "get_ui_tree")
        #expect(status == .callingTool(tool: "get_ui_tree"))
    }

    @Test("Error status")
    func errorStatus() {
        let status = AgentStatus.error(message: "Failed")
        #expect(status == .error(message: "Failed"))
    }

    @Test("Different thinking statuses are not equal")
    func differentThinkingStatuses() {
        #expect(AgentStatus.thinking(status: "reasoning") != AgentStatus.thinking(status: "analyzing"))
    }
}

@Suite("HighlightRect")
struct HighlightRectTests {

    @Test("Creates from dictionary")
    func fromDictionary() {
        let dict: [String: Any] = [
            "x": 100.0,
            "y": 200.0,
            "width": 50.0,
            "height": 30.0,
            "color": "red",
            "label": "Submit",
        ]
        let rect = HighlightRect(from: dict)

        #expect(rect.x == 100.0)
        #expect(rect.y == 200.0)
        #expect(rect.width == 50.0)
        #expect(rect.height == 30.0)
        #expect(rect.color == "red")
        #expect(rect.label == "Submit")
    }

    @Test("Dictionary defaults for missing values")
    func dictionaryDefaults() {
        let rect = HighlightRect(from: [:])

        #expect(rect.x == 0)
        #expect(rect.y == 0)
        #expect(rect.width == 0)
        #expect(rect.height == 0)
        #expect(rect.color == "blue")
        #expect(rect.label == nil)
    }

    @Test("Creates with direct initializer")
    func directInit() {
        let rect = HighlightRect(x: 10, y: 20, width: 30, height: 40, color: "green", label: "Test")

        #expect(rect.x == 10)
        #expect(rect.y == 20)
        #expect(rect.width == 30)
        #expect(rect.height == 40)
        #expect(rect.color == "green")
        #expect(rect.label == "Test")
    }

    @Test("Equatable works correctly")
    func equatable() {
        let rect1 = HighlightRect(x: 10, y: 20, width: 30, height: 40)
        let rect2 = HighlightRect(x: 10, y: 20, width: 30, height: 40)
        let rect3 = HighlightRect(x: 10, y: 20, width: 30, height: 50)

        #expect(rect1 == rect2)
        #expect(rect1 != rect3)
    }
}
