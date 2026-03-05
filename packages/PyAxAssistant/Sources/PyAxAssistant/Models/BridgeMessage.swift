import Foundation

enum BridgeMessage {
    case appChanged(appName: String, pid: Int)
    case response(requestId: String, json: [String: Any])
    case error(requestId: String, message: String)
    case event(json: [String: Any])
    case pong
    case unknown(type: String)
}
