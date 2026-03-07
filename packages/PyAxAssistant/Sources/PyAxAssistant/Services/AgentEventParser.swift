import Foundation

/// Stateless parser for SSE events from the pyax-agent server.
///
/// SSE format: `event: <type>\ndata: <json>\n\n`
struct AgentEventParser {

    func parse(eventType: String, data: String) -> AgentEvent? {
        guard let jsonData = data.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any]
        else {
            return nil
        }

        switch eventType {
        case "thinking":
            let status = json["status"] as? String ?? "analyzing_request"
            return .thinking(status: status)

        case "tool_call":
            let tool = json["tool"] as? String ?? ""
            let inputJSON = serializeValue(json["input"])
            return .toolCall(tool: tool, inputJSON: inputJSON)

        case "tool_result":
            let tool = json["tool"] as? String ?? ""
            let resultJSON = serializeValue(json["result"])
            return .toolResult(tool: tool, resultJSON: resultJSON)

        case "message":
            let content = json["content"] as? String ?? ""
            return .message(content: content)

        case "done":
            return .done

        case "error":
            let message = json["message"] as? String ?? "Unknown error"
            return .error(message: message)

        case "highlight":
            let rawHighlights = json["highlights"] as? [[String: Any]] ?? []
            let rects = rawHighlights.map { HighlightRect(from: $0) }
            let duration = json["duration"] as? Double ?? 3.0
            return .highlight(rects: rects, duration: duration)

        case "speak":
            let text = json["text"] as? String ?? ""
            let rate = json["rate"] as? Double ?? 0.5
            return .speak(text: text, rate: rate)

        case "clear_highlights":
            return .clearHighlights

        default:
            return nil
        }
    }

    // MARK: - Private

    private func serializeValue(_ value: Any?) -> String {
        guard let value else { return "{}" }
        guard JSONSerialization.isValidJSONObject(["v": value]),
              let data = try? JSONSerialization.data(withJSONObject: value),
              let string = String(data: data, encoding: .utf8)
        else {
            return String(describing: value)
        }
        return string
    }
}
