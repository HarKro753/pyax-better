import Foundation

struct BridgeResponse: @unchecked Sendable {
    private let _json: [String: Any]

    var json: [String: Any] { _json }

    init(json: [String: Any]) {
        self._json = json
    }

    subscript(key: String) -> Any? {
        _json[key]
    }

    var command: String? { _json["command"] as? String }
    var error: String? { _json["error"] as? String }
    var isSuccess: Bool { _json["error"] == nil }
}
