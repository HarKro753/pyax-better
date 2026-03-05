import Foundation

@MainActor
final class WebSocketConnection {

    // MARK: - Private State

    private var _webSocketTask: URLSessionWebSocketTask?
    private var _session: URLSession?
    private var _isListening = false
    private var _hasReceivedFirstMessage = false
    private var _reconnectTask: Task<Void, Never>?
    private var _reconnectAttempt = 0
    private let _configuration: BridgeConfiguration

    // MARK: - Callbacks

    var onMessage: ((URLSessionWebSocketTask.Message) -> Void)?
    var onConnectionStatusChanged: ((ConnectionStatus) -> Void)?
    var onDisconnected: (() -> Void)?

    // MARK: - Init

    init(configuration: BridgeConfiguration = .default) {
        self._configuration = configuration
    }

    // MARK: - Connection Lifecycle

    func connect() {
        onConnectionStatusChanged?(.connecting)
        _webSocketTask?.cancel(with: .goingAway, reason: nil)
        _session?.invalidateAndCancel()

        _session = URLSession(configuration: .default)
        _webSocketTask = _session?.webSocketTask(with: _configuration.webSocketURL)
        _webSocketTask?.resume()

        _isListening = true
        startListening()
        startPingLoop()
    }

    func disconnect() {
        _isListening = false
        _hasReceivedFirstMessage = false
        _reconnectAttempt = 0
        _reconnectTask?.cancel()
        _reconnectTask = nil
        _webSocketTask?.cancel(with: .goingAway, reason: nil)
        _webSocketTask = nil
        _session?.invalidateAndCancel()
        _session = nil

        onDisconnected?()
        onConnectionStatusChanged?(.disconnected)
    }

    func sendString(_ string: String) async {
        do {
            try await _webSocketTask?.send(.string(string))
        } catch {
            // Reconnection will handle failures
        }
    }

    // MARK: - Listening

    private func startListening() {
        guard _isListening else { return }

        _webSocketTask?.receive { [weak self] result in
            Task { @MainActor in
                guard let self, self._isListening else { return }

                switch result {
                case .success(let message):
                    if !self._hasReceivedFirstMessage {
                        self._hasReceivedFirstMessage = true
                        self._reconnectAttempt = 0
                        self.onConnectionStatusChanged?(.connected)
                    }
                    self.onMessage?(message)
                    self.startListening()
                case .failure:
                    self._hasReceivedFirstMessage = false
                    self.handleDisconnection()
                }
            }
        }
    }

    // MARK: - Keep-alive

    private func startPingLoop() {
        Task {
            while _isListening {
                try? await Task.sleep(for: _configuration.pingInterval)
                guard _isListening else { break }
                await sendString("{\"type\":\"ping\"}")
            }
        }
    }

    // MARK: - Reconnection

    private func handleDisconnection() {
        onConnectionStatusChanged?(.disconnected)
        onDisconnected?()

        _reconnectTask?.cancel()
        _reconnectAttempt += 1
        let maxDelaySeconds: Double = Double(_configuration.maxReconnectDelay.components.seconds)
        let delay: Double = min(Double(_reconnectAttempt), maxDelaySeconds)

        _reconnectTask = Task {
            try? await Task.sleep(for: .seconds(delay))
            guard !Task.isCancelled, _isListening else { return }
            connect()
        }
    }
}
