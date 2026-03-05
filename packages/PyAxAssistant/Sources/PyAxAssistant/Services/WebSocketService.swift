import Foundation

@Observable
@MainActor
final class WebSocketService {

    // MARK: - Private State

    private let _connection: WebSocketConnection
    private let _parser: BridgeMessageParser
    private let _configuration: BridgeConfiguration
    private var _pendingCommands: [String: CheckedContinuation<BridgeResponse, Error>] = [:]

    // MARK: - Delegate

    weak var delegate: AppState?

    // MARK: - Init

    init(configuration: BridgeConfiguration = .default) {
        self._configuration = configuration
        self._connection = WebSocketConnection(configuration: configuration)
        self._parser = BridgeMessageParser()
        setupConnectionCallbacks()
    }

    // MARK: - Connection Lifecycle

    func connect() {
        _connection.connect()
    }

    func disconnect() {
        _connection.disconnect()
    }

    // MARK: - Bridge Commands

    func sendBridgeCommand(_ command: String, params: [String: Any] = [:]) async throws -> BridgeResponse {
        let requestId = UUID().uuidString

        var payload: [String: Any] = [
            "type": "command",
            "id": requestId,
            "command": command,
        ]
        for (key, value) in params {
            payload[key] = value
        }

        return try await withCheckedThrowingContinuation { continuation in
            _pendingCommands[requestId] = continuation

            Task {
                await sendRaw(payload)
            }

            Task {
                try? await Task.sleep(for: _configuration.commandTimeout)
                if let cont = _pendingCommands.removeValue(forKey: requestId) {
                    cont.resume(throwing: BridgeError.timeout)
                }
            }
        }
    }

    // MARK: - Convenience Commands

    func getTree(depth: Int = 5, includeActions: Bool = true) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_tree", params: [
            "depth": depth,
            "include_actions": includeActions,
        ])
    }

    func findElements(criteria: [String: String], maxResults: Int = 10) async throws -> BridgeResponse {
        try await sendBridgeCommand("find_elements", params: [
            "criteria": criteria,
            "max_results": maxResults,
        ])
    }

    func getElement(path: [Int], depth: Int = 1) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_element", params: [
            "path": path,
            "depth": depth,
        ])
    }

    func performAction(_ action: String, path: [Int]? = nil, criteria: [String: String]? = nil) async throws -> BridgeResponse {
        var params: [String: Any] = ["action": action]
        if let path { params["path"] = path }
        if let criteria { params["criteria"] = criteria }
        return try await sendBridgeCommand("perform_action", params: params)
    }

    func setAttribute(_ attribute: String, value: Any, path: [Int]? = nil, criteria: [String: String]? = nil) async throws -> BridgeResponse {
        var params: [String: Any] = ["attribute": attribute, "value": value]
        if let path { params["path"] = path }
        if let criteria { params["criteria"] = criteria }
        return try await sendBridgeCommand("set_attribute", params: params)
    }

    func getElementAtPosition(x: Double, y: Double) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_element_at_position", params: [
            "x": x,
            "y": y,
        ])
    }

    func getFocusedElement(depth: Int = 0) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_focused_element", params: [
            "depth": depth,
        ])
    }

    func getAppInfo() async throws -> BridgeResponse {
        try await sendBridgeCommand("get_app_info")
    }

    // MARK: - Private

    private func sendRaw(_ command: [String: Any]) async {
        guard let data = try? JSONSerialization.data(withJSONObject: command),
              let string = String(data: data, encoding: .utf8)
        else { return }

        await _connection.sendString(string)
    }

    private func setupConnectionCallbacks() {
        _connection.onConnectionStatusChanged = { [weak self] status in
            self?.delegate?.updateConnectionStatus(status)
        }

        _connection.onDisconnected = { [weak self] in
            self?.cancelAllPendingCommands()
        }

        _connection.onMessage = { [weak self] message in
            self?.handleRawMessage(message)
        }
    }

    private func handleRawMessage(_ message: URLSessionWebSocketTask.Message) {
        guard let parsed = _parser.parse(message) else { return }

        switch parsed.bridgeMessage {
        case .pong:
            break
        default:
            print("[Event] \(parsed.rawText)")
            delegate?.appendMessage(parsed.rawText)
        }

        switch parsed.bridgeMessage {
        case .appChanged(let appName, let pid):
            delegate?.updateObservedApp(name: appName, pid: pid)
        case .response(let requestId, let json):
            resolveCommand(requestId: requestId, result: .success(BridgeResponse(json: json)))
        case .error(let requestId, let message):
            resolveCommand(requestId: requestId, result: .failure(BridgeError.bridgeError(message)))
        case .event, .pong, .unknown:
            break
        }
    }

    private func resolveCommand(requestId: String, result: Result<BridgeResponse, Error>) {
        guard let continuation = _pendingCommands.removeValue(forKey: requestId) else { return }

        switch result {
        case .success(let response):
            continuation.resume(returning: response)
        case .failure(let error):
            continuation.resume(throwing: error)
        }
    }

    private func cancelAllPendingCommands() {
        for (_, continuation) in _pendingCommands {
            continuation.resume(throwing: BridgeError.disconnected)
        }
        _pendingCommands.removeAll()
    }
}
