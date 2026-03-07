import Foundation

/// A single message in the chat conversation.
struct ChatMessage: Identifiable, Equatable {
    let id: UUID
    let role: ChatRole
    let content: String
    let timestamp: Date

    init(id: UUID = UUID(), role: ChatRole, content: String, timestamp: Date = Date()) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
    }

    static func == (lhs: ChatMessage, rhs: ChatMessage) -> Bool {
        lhs.id == rhs.id && lhs.content == rhs.content
    }
}

/// The role of a chat message sender.
enum ChatRole: Equatable {
    case user
    case assistant
    case system
    case toolCall(tool: String)
    case toolResult(tool: String)
    case thinking(status: String)
    case error
}

/// The current state of the agent processing.
enum AgentStatus: Equatable {
    case idle
    case thinking(status: String)
    case callingTool(tool: String)
    case error(message: String)
}
