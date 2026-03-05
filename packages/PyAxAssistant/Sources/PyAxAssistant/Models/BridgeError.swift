import Foundation

enum BridgeError: Error, LocalizedError {
    case timeout
    case disconnected
    case bridgeError(String)

    var errorDescription: String? {
        switch self {
        case .timeout:
            return "Bridge command timed out"
        case .disconnected:
            return "WebSocket disconnected"
        case .bridgeError(let message):
            return "Bridge error: \(message)"
        }
    }
}
