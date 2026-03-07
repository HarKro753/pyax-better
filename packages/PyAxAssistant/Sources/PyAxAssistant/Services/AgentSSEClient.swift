import Foundation

/// Connects to the pyax-agent HTTP server and streams SSE events.
///
/// Sends user messages via `POST /chat` and parses the SSE response stream
/// into typed `AgentEvent` values delivered via an `AsyncStream`.
@MainActor
final class AgentSSEClient {

    // MARK: - Private State

    private let _configuration: BridgeConfiguration
    private let _parser: AgentEventParser
    private var _currentTask: Task<Void, Never>?
    private let _session: URLSession

    // MARK: - Init

    init(configuration: BridgeConfiguration = .default) {
        self._configuration = configuration
        self._parser = AgentEventParser()

        let sessionConfig = URLSessionConfiguration.default
        sessionConfig.timeoutIntervalForRequest = configuration.agentRequestTimeout.asSeconds
        sessionConfig.timeoutIntervalForResource = configuration.agentRequestTimeout.asSeconds
        self._session = URLSession(configuration: sessionConfig)
    }

    // MARK: - Public API

    /// Send a chat message to the agent and receive SSE events as an async stream.
    func sendMessage(_ message: String, conversationId: String = "default") -> AsyncStream<AgentEvent> {
        cancelCurrentRequest()

        return AsyncStream { continuation in
            let task = Task {
                await performRequest(message: message, conversationId: conversationId, continuation: continuation)
            }
            _currentTask = task

            continuation.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }

    /// Cancel the current agent request.
    func cancelCurrentRequest() {
        _currentTask?.cancel()
        _currentTask = nil
    }

    /// Stop the agent loop on the server.
    func stopAgent() async {
        cancelCurrentRequest()
        var request = URLRequest(url: _configuration.agentStopURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        _ = try? await _session.data(for: request)
    }

    /// Check if the agent server is healthy.
    func checkHealth() async -> Bool {
        var request = URLRequest(url: _configuration.agentHealthURL)
        request.httpMethod = "GET"
        request.timeoutInterval = 3

        do {
            let (data, response) = try await _session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let status = json["status"] as? String,
                  status == "ok"
            else {
                print("[Agent] Health check failed: unexpected response")
                return false
            }
            print("[Agent] Health check passed")
            return true
        } catch {
            print("[Agent] Health check failed: \(error.localizedDescription)")
            return false
        }
    }

    // MARK: - Private

    private func performRequest(
        message: String,
        conversationId: String,
        continuation: AsyncStream<AgentEvent>.Continuation
    ) async {
        let url = _configuration.agentChatURL
        print("[Agent] POST \(url.absoluteString)")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")

        let body: [String: String] = [
            "message": message,
            "conversation_id": conversationId,
        ]

        guard let bodyData = try? JSONSerialization.data(withJSONObject: body) else {
            let msg = "Failed to encode request body"
            print("[Agent] ERROR: \(msg)")
            continuation.yield(.error(message: msg))
            continuation.yield(.done)
            continuation.finish()
            return
        }
        request.httpBody = bodyData

        do {
            let (bytes, response) = try await _session.bytes(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                let msg = "Invalid response from agent server"
                print("[Agent] ERROR: \(msg)")
                continuation.yield(.error(message: msg))
                continuation.yield(.done)
                continuation.finish()
                return
            }

            guard httpResponse.statusCode == 200 else {
                let msg = "Agent returned HTTP \(httpResponse.statusCode)"
                print("[Agent] ERROR: \(msg)")
                continuation.yield(.error(message: msg))
                continuation.yield(.done)
                continuation.finish()
                return
            }

            print("[Agent] SSE stream connected")

            var currentEventType: String?
            var currentData: String?

            for try await line in bytes.lines {
                guard !Task.isCancelled else { break }

                if line.hasPrefix("event: ") {
                    currentEventType = String(line.dropFirst(7))
                } else if line.hasPrefix("data: ") {
                    currentData = String(line.dropFirst(6))
                } else if line.isEmpty {
                    if let eventType = currentEventType, let data = currentData {
                        if let event = _parser.parse(eventType: eventType, data: data) {
                            print("[Agent] Event: \(eventType)")
                            continuation.yield(event)
                        }
                    }
                    currentEventType = nil
                    currentData = nil
                }
            }

            print("[Agent] SSE stream ended")
            continuation.finish()
        } catch is CancellationError {
            print("[Agent] Request cancelled")
            continuation.finish()
        } catch let urlError as URLError where urlError.code == .cannotConnectToHost || urlError.code == .networkConnectionLost || urlError.code == .notConnectedToInternet {
            let msg = "Cannot reach agent server at \(url.host ?? "localhost"):\(url.port ?? 8766). Is pyax-agent running?"
            print("[Agent] ERROR: \(msg)")
            if !Task.isCancelled {
                continuation.yield(.error(message: msg))
                continuation.yield(.done)
            }
            continuation.finish()
        } catch {
            let msg = "Connection error: \(error.localizedDescription)"
            print("[Agent] ERROR: \(msg)")
            if !Task.isCancelled {
                continuation.yield(.error(message: msg))
                continuation.yield(.done)
            }
            continuation.finish()
        }
    }
}

// MARK: - Duration Extension

extension Duration {
    var asSeconds: TimeInterval {
        let components = self.components
        return Double(components.seconds) + Double(components.attoseconds) / 1e18
    }
}
