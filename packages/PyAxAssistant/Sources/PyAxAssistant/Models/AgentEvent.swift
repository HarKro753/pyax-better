import Foundation

/// Parsed SSE events from the pyax-agent server.
/// Maps 1:1 to the Python agent's 9 SSE event types.
enum AgentEvent: Sendable {
    case thinking(status: String)
    case toolCall(tool: String, inputJSON: String)
    case toolResult(tool: String, resultJSON: String)
    case message(content: String)
    case done
    case error(message: String)
    case highlight(rects: [HighlightRect], duration: Double)
    case speak(text: String, rate: Double)
    case clearHighlights
}

/// Represents a single highlight rectangle from the agent.
struct HighlightRect: Sendable, Equatable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let color: String
    let label: String?

    init(x: Double, y: Double, width: Double, height: Double, color: String = "blue", label: String? = nil) {
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.label = label
    }

    init(from dict: [String: Any]) {
        self.x = dict["x"] as? Double ?? 0
        self.y = dict["y"] as? Double ?? 0
        self.width = dict["width"] as? Double ?? 0
        self.height = dict["height"] as? Double ?? 0
        self.color = dict["color"] as? String ?? "blue"
        self.label = dict["label"] as? String
    }
}
