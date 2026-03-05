import Foundation

struct BridgeMessageParser {

    func parse(_ message: URLSessionWebSocketTask.Message) -> (rawText: String, bridgeMessage: BridgeMessage)? {
        let rawText: String
        let data: Data

        switch message {
        case .string(let text):
            rawText = text
            guard let textData = text.data(using: .utf8) else { return nil }
            data = textData
        case .data(let binaryData):
            data = binaryData
            rawText = String(data: binaryData, encoding: .utf8) ?? "<binary>"
        @unknown default:
            return nil
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String
        else { return nil }

        let bridgeMessage = parseType(type, from: json)
        return (rawText, bridgeMessage)
    }

    // MARK: - Private

    private func parseType(_ type: String, from json: [String: Any]) -> BridgeMessage {
        switch type {
        case "app_changed":
            return parseAppChanged(from: json)
        case "response":
            return parseResponse(from: json)
        case "pong":
            return .pong
        case "event":
            return .event(json: json)
        default:
            return .unknown(type: type)
        }
    }

    private func parseAppChanged(from json: [String: Any]) -> BridgeMessage {
        guard let app = json["app"] as? String,
              let pid = json["pid"] as? Int
        else { return .unknown(type: "app_changed") }
        return .appChanged(appName: app, pid: pid)
    }

    private func parseResponse(from json: [String: Any]) -> BridgeMessage {
        guard let requestId = json["id"] as? String else {
            return .unknown(type: "response")
        }

        if let errorMessage = json["error"] as? String {
            return .error(requestId: requestId, message: errorMessage)
        }

        return .response(requestId: requestId, json: json)
    }
}
