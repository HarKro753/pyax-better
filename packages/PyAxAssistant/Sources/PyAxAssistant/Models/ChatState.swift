import Foundation

/// Manages chat conversation state and agent interaction.
///
/// Owns the message list, agent status, and conversation tracking.
/// Delegates network communication to `AgentSSEClient`.
@Observable
@MainActor
final class ChatState {

    // MARK: - Private State

    private var _messages: [ChatMessage] = []
    private var _agentStatus: AgentStatus = .idle
    private var _conversationId: String
    private var _isProcessing = false
    private let _client: AgentSSEClient
    private let _configuration: BridgeConfiguration
    private var _currentAssistantMessageId: UUID?
    private var _currentAssistantContent = ""

    // MARK: - Read Access

    var messages: [ChatMessage] { _messages }
    var agentStatus: AgentStatus { _agentStatus }
    var conversationId: String { _conversationId }
    var isProcessing: Bool { _isProcessing }

    // MARK: - Init

    init(configuration: BridgeConfiguration = .default, client: AgentSSEClient? = nil) {
        self._configuration = configuration
        self._client = client ?? AgentSSEClient(configuration: configuration)
        self._conversationId = UUID().uuidString
    }

    // MARK: - Actions

    /// Send a user message to the agent and stream the response.
    func sendMessage(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !_isProcessing else { return }

        print("[Chat] Sending: \(trimmed.prefix(80))")

        let userMessage = ChatMessage(role: .user, content: trimmed)
        _messages.append(userMessage)
        _isProcessing = true
        _agentStatus = .thinking(status: "connecting")
        _currentAssistantMessageId = nil
        _currentAssistantContent = ""

        Task {
            let healthy = await _client.checkHealth()
            if !healthy {
                let msg = "Agent server is not running. Start pyax-agent on port \(_configuration.agentPort) first."
                print("[Chat] ERROR: \(msg)")
                _agentStatus = .error(message: msg)
                let errorMessage = ChatMessage(role: .error, content: msg)
                _messages.append(errorMessage)
                finishProcessing()
                return
            }

            _agentStatus = .thinking(status: "analyzing_request")

            let stream = _client.sendMessage(trimmed, conversationId: _conversationId)
            for await event in stream {
                handleEvent(event)
            }
            finishProcessing()
        }
    }

    /// Cancel the current agent request.
    func cancelRequest() {
        print("[Chat] Cancelling request")
        _client.cancelCurrentRequest()
        Task {
            await _client.stopAgent()
        }
        finishProcessing()

        let cancelMessage = ChatMessage(role: .system, content: "Request cancelled")
        _messages.append(cancelMessage)
    }

    /// Clear all messages and start a new conversation.
    func clearConversation() {
        print("[Chat] Clearing conversation")
        _messages.removeAll()
        _conversationId = UUID().uuidString
        _agentStatus = .idle
        _isProcessing = false
        _currentAssistantMessageId = nil
        _currentAssistantContent = ""
    }

    // MARK: - Event Handling

    /// Delegate for highlight events — set by the app to forward to HighlightOverlayWindow.
    var onHighlight: (([HighlightRect], Double) -> Void)?

    /// Delegate for clear highlights — set by the app to forward to HighlightOverlayWindow.
    var onClearHighlights: (() -> Void)?

    /// Delegate for speak events — set by the app to forward to VoiceService.
    var onSpeak: ((String, Double) -> Void)?

    private func handleEvent(_ event: AgentEvent) {
        switch event {
        case .thinking(let status):
            print("[Chat] Thinking: \(status)")
            _agentStatus = .thinking(status: status)

        case .toolCall(let tool, let inputJSON):
            print("[Chat] Tool call: \(tool)")
            _agentStatus = .callingTool(tool: tool)
            let toolMessage = ChatMessage(
                role: .toolCall(tool: tool),
                content: inputJSON
            )
            _messages.append(toolMessage)

        case .toolResult(let tool, let resultJSON):
            print("[Chat] Tool result: \(tool)")
            let resultMessage = ChatMessage(
                role: .toolResult(tool: tool),
                content: resultJSON
            )
            _messages.append(resultMessage)

        case .message(let content):
            print("[Chat] Message: \(content.prefix(80))")
            appendOrUpdateAssistantMessage(content)

        case .done:
            print("[Chat] Done")

        case .error(let message):
            print("[Chat] ERROR: \(message)")
            _agentStatus = .error(message: message)
            let errorMessage = ChatMessage(role: .error, content: message)
            _messages.append(errorMessage)

        case .highlight(let rects, let duration):
            print("[Chat] Highlight \(rects.count) rects for \(duration)s")
            onHighlight?(rects, duration)

        case .speak(let text, let rate):
            print("[Chat] Speak: \(text.prefix(80)) (rate: \(rate))")
            onSpeak?(text, rate)

        case .clearHighlights:
            print("[Chat] Clear highlights")
            onClearHighlights?()
        }

        trimMessagesIfNeeded()
    }

    // MARK: - Private

    private func appendOrUpdateAssistantMessage(_ content: String) {
        _currentAssistantContent += content

        if let existingId = _currentAssistantMessageId,
           let index = _messages.firstIndex(where: { $0.id == existingId }) {
            _messages[index] = ChatMessage(
                id: existingId,
                role: .assistant,
                content: _currentAssistantContent
            )
        } else {
            let newId = UUID()
            _currentAssistantMessageId = newId
            let assistantMessage = ChatMessage(
                id: newId,
                role: .assistant,
                content: _currentAssistantContent
            )
            _messages.append(assistantMessage)
        }
    }

    private func finishProcessing() {
        _isProcessing = false
        _agentStatus = .idle
        _currentAssistantMessageId = nil
        _currentAssistantContent = ""
    }

    private func trimMessagesIfNeeded() {
        if _messages.count > _configuration.maxChatMessages {
            _messages.removeFirst(_messages.count - _configuration.maxChatMessages)
        }
    }
}
