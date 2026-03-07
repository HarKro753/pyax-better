import SwiftUI

struct ChatView: View {
    @Environment(ChatState.self) private var chatState
    @Environment(VoiceService.self) private var voiceService

    @State private var _inputText = ""
    @FocusState private var _isInputFocused: Bool

    private let _bottomAnchorID = "chat-bottom"

    var body: some View {
        VStack(spacing: 0) {
            chatMessages

            Divider()
                .opacity(0.3)

            agentStatusBar

            Divider()
                .opacity(0.3)

            chatInput
        }
    }

    // MARK: - Message List

    private var chatMessages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    if chatState.messages.isEmpty {
                        ChatEmptyView()
                    }

                    ForEach(chatState.messages) { message in
                        ChatBubble(message: message)
                            .id(message.id)
                    }

                    Color.clear
                        .frame(height: 1)
                        .id(_bottomAnchorID)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
            }
            .scrollIndicators(.hidden)
            .onChange(of: chatState.messages.count) { _, _ in
                withAnimation(.easeOut(duration: 0.15)) {
                    proxy.scrollTo(_bottomAnchorID, anchor: .bottom)
                }
            }
        }
    }

    // MARK: - Agent Status Bar

    @ViewBuilder
    private var agentStatusBar: some View {
        switch chatState.agentStatus {
        case .idle:
            EmptyView()
        case .thinking(let status):
            AgentStatusIndicator(icon: "brain", text: formatThinkingStatus(status), color: .purple)
        case .callingTool(let tool):
            AgentStatusIndicator(icon: "wrench.and.screwdriver", text: tool, color: .orange)
        case .error(let message):
            AgentStatusIndicator(icon: "exclamationmark.triangle", text: message, color: .red)
        }
    }

    private func formatThinkingStatus(_ status: String) -> String {
        status.replacingOccurrences(of: "_", with: " ").capitalized
    }

    // MARK: - Input

    private var chatInput: some View {
        HStack(spacing: 8) {
            MicrophoneButton(
                isListening: voiceService.isListening,
                onPress: { voiceService.startListening() },
                onRelease: {
                    let text = voiceService.stopListening()
                    if !text.isEmpty {
                        _inputText = text
                        sendMessage()
                    }
                }
            )

            TextField("Ask the assistant...", text: $_inputText, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(.caption))
                .lineLimit(1...4)
                .focused($_isInputFocused)
                .onSubmit {
                    sendMessage()
                }

            if chatState.isProcessing {
                Button {
                    chatState.cancelRequest()
                } label: {
                    Image(systemName: "stop.circle.fill")
                        .font(.system(size: 16))
                        .foregroundStyle(.red)
                }
                .buttonStyle(.plain)
                .help("Stop agent")
            } else {
                Button {
                    sendMessage()
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 16))
                        .foregroundColor(_inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? .gray : .blue)
                }
                .buttonStyle(.plain)
                .disabled(_inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .help("Send message")
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    // MARK: - Actions

    private func sendMessage() {
        let text = _inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        _inputText = ""
        chatState.sendMessage(text)
    }
}

// MARK: - Chat Bubble

private struct ChatBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user {
                Spacer(minLength: 40)
            }

            VStack(alignment: alignment, spacing: 2) {
                if let label = roleLabel {
                    Text(label)
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundStyle(.secondary)
                }

                Text(message.content)
                    .font(.system(size: 12))
                    .foregroundStyle(textColor)
                    .textSelection(.enabled)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(bubbleColor)
                    .clipShape(.rect(cornerRadius: 10))
            }

            if message.role != .user {
                Spacer(minLength: 40)
            }
        }
    }

    private var alignment: HorizontalAlignment {
        message.role == .user ? .trailing : .leading
    }

    private var textColor: Color {
        switch message.role {
        case .user:
            return .white
        case .error:
            return .red
        case .toolCall, .toolResult:
            return .primary.opacity(0.7)
        default:
            return .primary
        }
    }

    private var bubbleColor: Color {
        switch message.role {
        case .user:
            return .blue
        case .error:
            return .red.opacity(0.15)
        case .toolCall, .toolResult:
            return .white.opacity(0.05)
        case .system:
            return .white.opacity(0.05)
        default:
            return .white.opacity(0.1)
        }
    }

    private var roleLabel: String? {
        switch message.role {
        case .toolCall(let tool):
            return "⚙️ \(tool)"
        case .toolResult(let tool):
            return "✅ \(tool)"
        case .thinking(let status):
            return "💭 \(status)"
        case .system:
            return nil
        default:
            return nil
        }
    }
}

// MARK: - Agent Status Indicator

private struct AgentStatusIndicator: View {
    let icon: String
    let text: String
    let color: Color

    @State private var _isAnimating = false

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 10))
                .foregroundStyle(color)
                .opacity(_isAnimating ? 0.4 : 1.0)
                .animation(
                    .easeInOut(duration: 0.8).repeatForever(autoreverses: true),
                    value: _isAnimating
                )

            Text(text)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(1)

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .onAppear { _isAnimating = true }
    }
}

// MARK: - Microphone Button

private struct MicrophoneButton: View {
    let isListening: Bool
    let onPress: () -> Void
    let onRelease: () -> Void

    @State private var _isPressed = false

    var body: some View {
        Image(systemName: isListening ? "mic.fill" : "mic")
            .font(.system(size: 14))
            .foregroundColor(isListening ? .red : .secondary)
            .frame(width: 22, height: 22)
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        if !_isPressed {
                            _isPressed = true
                            onPress()
                        }
                    }
                    .onEnded { _ in
                        _isPressed = false
                        onRelease()
                    }
            )
            .help(isListening ? "Release to send" : "Hold to speak")
    }
}

// MARK: - Empty State

private struct ChatEmptyView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 28))
                .foregroundStyle(.tertiary)

            Text("Ask the Assistant")
                .font(.system(.caption, weight: .semibold))
                .foregroundStyle(.secondary)

            Text("Type a message to interact with the accessibility agent. It can inspect UI, click buttons, read content, and more.")
                .font(.system(size: 10))
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 240)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
