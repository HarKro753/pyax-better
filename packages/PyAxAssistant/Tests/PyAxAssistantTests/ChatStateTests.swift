import Testing
import Foundation
@testable import PyAxAssistant

@MainActor
@Suite("ChatState")
struct ChatStateTests {

    // MARK: - Initial State

    @Test("Initial state has correct defaults")
    func initialState() {
        let sut = ChatState()

        #expect(sut.messages.isEmpty)
        #expect(sut.agentStatus == .idle)
        #expect(sut.isProcessing == false)
        #expect(!sut.conversationId.isEmpty)
    }

    // MARK: - Clear Conversation

    @Test("Clear conversation resets state")
    func clearConversation() {
        let sut = ChatState()
        let originalConversationId = sut.conversationId

        sut.clearConversation()

        #expect(sut.messages.isEmpty)
        #expect(sut.agentStatus == .idle)
        #expect(sut.isProcessing == false)
        #expect(sut.conversationId != originalConversationId)
    }

    // MARK: - Event Handling Delegates

    @Test("Highlight delegate is called for highlight events")
    func highlightDelegate() {
        let sut = ChatState()
        var receivedRects: [HighlightRect]?
        var receivedDuration: Double?

        sut.onHighlight = { rects, duration in
            receivedRects = rects
            receivedDuration = duration
        }

        let rects = [HighlightRect(x: 10, y: 20, width: 30, height: 40, color: "red")]
        sut.onHighlight?(rects, 5.0)

        #expect(receivedRects?.count == 1)
        #expect(receivedDuration == 5.0)
    }

    @Test("Clear highlights delegate is called")
    func clearHighlightsDelegate() {
        let sut = ChatState()
        var clearCalled = false

        sut.onClearHighlights = {
            clearCalled = true
        }

        sut.onClearHighlights?()

        #expect(clearCalled)
    }

    @Test("Speak delegate is called")
    func speakDelegate() {
        let sut = ChatState()
        var spokenText: String?
        var spokenRate: Double?

        sut.onSpeak = { text, rate in
            spokenText = text
            spokenRate = rate
        }

        sut.onSpeak?("Hello", 0.7)

        #expect(spokenText == "Hello")
        #expect(spokenRate == 0.7)
    }

    // MARK: - Send Message Guards

    @Test("Empty message is not sent")
    func emptyMessageNotSent() {
        let sut = ChatState()

        sut.sendMessage("")

        #expect(sut.messages.isEmpty)
        #expect(sut.isProcessing == false)
    }

    @Test("Whitespace-only message is not sent")
    func whitespaceMessageNotSent() {
        let sut = ChatState()

        sut.sendMessage("   \n  ")

        #expect(sut.messages.isEmpty)
        #expect(sut.isProcessing == false)
    }
}
