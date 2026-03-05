import Foundation

/// Service that manages the WebSocket connection to the Python bridge server.
/// Supports both passive event streaming and active command/response protocol.
///
/// ## Command Protocol
/// Send commands via `sendBridgeCommand` to query the UI tree, find elements,
/// and perform actions (click, type, etc.) on the focused application.
///
/// Commands are sent as:
/// ```json
/// {"type": "command", "id": "<uuid>", "command": "get_tree", ...}
/// ```
/// Responses come back as:
/// ```json
/// {"type": "response", "id": "<uuid>", "command": "get_tree", "tree": {...}}
/// ```
@Observable
@MainActor
final class WebSocketService {

    // MARK: - Configuration

    private let url: URL
    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession?
    private var isListening = false
    private var reconnectTask: Task<Void, Never>?
    private var reconnectAttempt = 0

    /// Pending command continuations keyed by request ID.
    /// We use `any Sendable` to avoid data race warnings with `[String: Any]`.
    private var pendingCommands: [String: CheckedContinuation<BridgeResponse, Error>] = [:]

    /// Callback for every raw JSON message received (for debug display).
    var onRawMessage: ((String) -> Void)?

    /// Callback for app change notifications (to update observed app name).
    var onAppChanged: ((String, Int) -> Void)?

    /// Callback for connection status changes.
    var onConnectionStatusChanged: ((AppState.ConnectionStatus) -> Void)?

    /// Callback for command responses (for agent processing).
    var onResponse: (([String: Any]) -> Void)?

    // MARK: - Init

    init(host: String = "localhost", port: Int = 8765) {
        self.url = URL(string: "ws://\(host):\(port)")!
    }

    // MARK: - Connection

    func connect() {
        onConnectionStatusChanged?(.connecting)

        // Tear down any existing connection first
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        session?.invalidateAndCancel()

        session = URLSession(configuration: .default)
        webSocketTask = session?.webSocketTask(with: url)
        webSocketTask?.resume()

        isListening = true
        // Don't set .connected yet — wait until we successfully receive the first message.
        // The startListening() receive call will confirm the connection is alive.

        startListening()
        startPingLoop()
    }

    func disconnect() {
        isListening = false
        hasReceivedFirstMessage = false
        reconnectAttempt = 0
        reconnectTask?.cancel()
        reconnectTask = nil
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        session?.invalidateAndCancel()
        session = nil

        // Cancel all pending commands
        for (_, continuation) in pendingCommands {
            continuation.resume(throwing: BridgeError.disconnected)
        }
        pendingCommands.removeAll()

        onConnectionStatusChanged?(.disconnected)
    }

    // MARK: - Sending Raw

    func sendRaw(_ command: [String: Any]) async {
        guard let data = try? JSONSerialization.data(withJSONObject: command),
              let string = String(data: data, encoding: .utf8)
        else { return }

        do {
            try await webSocketTask?.send(.string(string))
        } catch {
            // Silently fail — reconnection will handle it
        }
    }

    // MARK: - Bridge Commands (Request/Response)

    /// Send a command to the Python bridge and wait for the response.
    /// This is the primary way for the agent/UI to interact with accessibility.
    ///
    /// Example:
    /// ```swift
    /// let tree = try await webSocket.sendBridgeCommand("get_tree", params: ["depth": 3])
    /// ```
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
            pendingCommands[requestId] = continuation

            Task {
                await sendRaw(payload)
            }

            // Timeout after 10 seconds
            Task {
                try? await Task.sleep(for: .seconds(10))
                if let cont = pendingCommands.removeValue(forKey: requestId) {
                    cont.resume(throwing: BridgeError.timeout)
                }
            }
        }
    }

    // MARK: - Convenience Command Methods

    /// Get the full UI tree of the focused app.
    func getTree(depth: Int = 5, includeActions: Bool = true) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_tree", params: [
            "depth": depth,
            "include_actions": includeActions,
        ])
    }

    /// Find elements matching search criteria.
    /// Criteria keys: role, title, value, identifier, description, dom_id
    /// Values support wildcards: "Save*", "*button*", "*Cancel"
    func findElements(criteria: [String: String], maxResults: Int = 10) async throws -> BridgeResponse {
        try await sendBridgeCommand("find_elements", params: [
            "criteria": criteria,
            "max_results": maxResults,
        ])
    }

    /// Get detailed info about a specific element by its path.
    func getElement(path: [Int], depth: Int = 1) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_element", params: [
            "path": path,
            "depth": depth,
        ])
    }

    /// Perform an action on an element (e.g. "AXPress" to click a button).
    func performAction(_ action: String, path: [Int]? = nil, criteria: [String: String]? = nil) async throws -> BridgeResponse {
        var params: [String: Any] = ["action": action]
        if let path { params["path"] = path }
        if let criteria { params["criteria"] = criteria }
        return try await sendBridgeCommand("perform_action", params: params)
    }

    /// Set an attribute value on an element (e.g. type into a text field).
    func setAttribute(_ attribute: String, value: Any, path: [Int]? = nil, criteria: [String: String]? = nil) async throws -> BridgeResponse {
        var params: [String: Any] = ["attribute": attribute, "value": value]
        if let path { params["path"] = path }
        if let criteria { params["criteria"] = criteria }
        return try await sendBridgeCommand("set_attribute", params: params)
    }

    /// Get the element at a screen position.
    func getElementAtPosition(x: Double, y: Double) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_element_at_position", params: [
            "x": x,
            "y": y,
        ])
    }

    /// Get the currently focused UI element.
    func getFocusedElement(depth: Int = 0) async throws -> BridgeResponse {
        try await sendBridgeCommand("get_focused_element", params: [
            "depth": depth,
        ])
    }

    /// Get info about the focused app (windows, menu bar, etc.).
    func getAppInfo() async throws -> BridgeResponse {
        try await sendBridgeCommand("get_app_info")
    }

    // MARK: - Receiving

    private var hasReceivedFirstMessage = false

    private func startListening() {
        guard isListening else { return }

        webSocketTask?.receive { [weak self] result in
            Task { @MainActor in
                guard let self, self.isListening else { return }

                switch result {
                case .success(let message):
                    // Mark as connected on first successful receive
                    if !self.hasReceivedFirstMessage {
                        self.hasReceivedFirstMessage = true
                        self.reconnectAttempt = 0
                        self.onConnectionStatusChanged?(.connected)
                    }
                    self.handleMessage(message)
                    self.startListening() // Continue listening
                case .failure:
                    self.hasReceivedFirstMessage = false
                    self.handleDisconnection()
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        let rawText: String
        let data: Data

        switch message {
        case .string(let text):
            rawText = text
            guard let textData = text.data(using: .utf8) else { return }
            data = textData
        case .data(let binaryData):
            data = binaryData
            rawText = String(data: binaryData, encoding: .utf8) ?? "<binary>"
        @unknown default:
            return
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String
        else { return }

        // Forward raw JSON to the UI and console (skip pong noise)
        if type != "pong" {
            print(rawText)
            onRawMessage?(rawText)
        }

        // Handle specific message types
        switch type {
        case "app_changed":
            parseAppChanged(from: json)
        case "response":
            handleResponse(json)
        case "pong", "event":
            break // Events already forwarded as raw JSON
        default:
            break
        }
    }

    private func handleResponse(_ json: [String: Any]) {
        guard let requestId = json["id"] as? String else { return }

        if let error = json["error"] as? String {
            if let continuation = pendingCommands.removeValue(forKey: requestId) {
                continuation.resume(throwing: BridgeError.bridgeError(error))
            }
        } else {
            if let continuation = pendingCommands.removeValue(forKey: requestId) {
                continuation.resume(returning: BridgeResponse(json: json))
            }
        }

        onResponse?(json)
    }

    private func parseAppChanged(from json: [String: Any]) {
        guard let app = json["app"] as? String,
              let pid = json["pid"] as? Int
        else { return }
        onAppChanged?(app, pid)
    }

    // MARK: - Keep-alive

    private func startPingLoop() {
        Task {
            while isListening {
                try? await Task.sleep(for: .seconds(15))
                guard isListening else { break }
                await sendRaw(["type": "ping"])
            }
        }
    }

    // MARK: - Reconnection

    private func handleDisconnection() {
        onConnectionStatusChanged?(.disconnected)

        // Cancel all pending commands
        for (_, continuation) in pendingCommands {
            continuation.resume(throwing: BridgeError.disconnected)
        }
        pendingCommands.removeAll()

        reconnectTask?.cancel()
        reconnectAttempt += 1
        let attempt = reconnectAttempt
        let delay = min(Double(attempt), 5.0)

        reconnectTask = Task {
            try? await Task.sleep(for: .seconds(delay))
            guard !Task.isCancelled, isListening else { return }
            connect()
        }
    }
}

// MARK: - Bridge Response

/// Sendable wrapper around a JSON response dictionary.
/// Needed because `[String: Any]` is not `Sendable`, but we need to pass it
/// through `CheckedContinuation` across actor boundaries.
struct BridgeResponse: @unchecked Sendable {
    let json: [String: Any]

    subscript(key: String) -> Any? {
        json[key]
    }

    var command: String? { json["command"] as? String }
    var error: String? { json["error"] as? String }
    var isSuccess: Bool { json["error"] == nil }
}

// MARK: - Errors

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
