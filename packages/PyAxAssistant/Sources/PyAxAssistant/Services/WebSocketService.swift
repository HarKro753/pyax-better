import Foundation

/// Service that manages the WebSocket connection to the Python bridge server.
/// Uses native URLSessionWebSocketTask for zero-dependency WebSocket support.
@Observable
@MainActor
final class WebSocketService {

    // MARK: - Configuration

    private let url: URL
    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession?
    private var isListening = false
    private var reconnectTask: Task<Void, Never>?

    /// Callback for received events.
    var onEvent: ((AccessibilityEvent) -> Void)?

    /// Callback for app change notifications.
    var onAppChanged: ((String, Int) -> Void)?

    /// Callback for connection status changes.
    var onConnectionStatusChanged: ((AppState.ConnectionStatus) -> Void)?

    // MARK: - Init

    init(host: String = "localhost", port: Int = 8765) {
        self.url = URL(string: "ws://\(host):\(port)")!
    }

    // MARK: - Connection

    func connect() {
        onConnectionStatusChanged?(.connecting)

        session = URLSession(configuration: .default)
        webSocketTask = session?.webSocketTask(with: url)
        webSocketTask?.resume()

        isListening = true
        onConnectionStatusChanged?(.connected)

        startListening()
        startPingLoop()
    }

    func disconnect() {
        isListening = false
        reconnectTask?.cancel()
        reconnectTask = nil
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        session?.invalidateAndCancel()
        session = nil
        onConnectionStatusChanged?(.disconnected)
    }

    // MARK: - Sending

    func sendCommand(_ command: [String: Any]) async {
        guard let data = try? JSONSerialization.data(withJSONObject: command),
              let string = String(data: data, encoding: .utf8)
        else { return }

        do {
            try await webSocketTask?.send(.string(string))
        } catch {
            print("[WebSocket] Send error: \(error)")
        }
    }

    // MARK: - Receiving

    private func startListening() {
        guard isListening else { return }

        webSocketTask?.receive { [weak self] result in
            Task { @MainActor in
                guard let self, self.isListening else { return }

                switch result {
                case .success(let message):
                    self.handleMessage(message)
                    self.startListening() // Continue listening
                case .failure(let error):
                    print("[WebSocket] Receive error: \(error)")
                    self.handleDisconnection()
                }
            }
        }
    }

    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        let data: Data
        switch message {
        case .string(let text):
            guard let textData = text.data(using: .utf8) else { return }
            data = textData
        case .data(let binaryData):
            data = binaryData
        @unknown default:
            return
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String
        else { return }

        switch type {
        case "event":
            parseEvent(from: json)
        case "app_changed":
            parseAppChanged(from: json)
        case "pong":
            break // Ping/pong handled
        default:
            break
        }
    }

    private func parseEvent(from json: [String: Any]) {
        let app = json["app"] as? String ?? "Unknown"
        let notification = json["notification"] as? String ?? "Unknown"
        let element = json["element"] as? [String: Any] ?? [:]
        let timestampStr = json["timestamp"] as? String
        let timestamp = parseTimestamp(timestampStr) ?? Date()

        let event = AccessibilityEvent(
            id: UUID(),
            app: app,
            notification: notification,
            role: element["role"] as? String,
            title: element["title"] as? String,
            value: element["value"] as? String,
            timestamp: timestamp
        )

        onEvent?(event)
    }

    private func parseAppChanged(from json: [String: Any]) {
        guard let app = json["app"] as? String,
              let pid = json["pid"] as? Int
        else { return }

        onAppChanged?(app, pid)
    }

    private func parseTimestamp(_ string: String?) -> Date? {
        guard let string else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: string)
    }

    // MARK: - Keep-alive

    private func startPingLoop() {
        Task {
            while isListening {
                try? await Task.sleep(for: .seconds(15))
                guard isListening else { break }
                await sendCommand(["type": "ping"])
            }
        }
    }

    // MARK: - Reconnection

    private func handleDisconnection() {
        onConnectionStatusChanged?(.disconnected)

        reconnectTask?.cancel()
        reconnectTask = Task {
            // Wait before reconnecting
            try? await Task.sleep(for: .seconds(2))
            guard !Task.isCancelled, isListening else { return }
            print("[WebSocket] Attempting reconnection...")
            connect()
        }
    }
}
