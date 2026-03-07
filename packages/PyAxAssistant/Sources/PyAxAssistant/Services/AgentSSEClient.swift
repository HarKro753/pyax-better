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

        let config = _configuration
        let parser = _parser
        let session = _session

        return AsyncStream { continuation in
            let task = Task.detached {
                await Self.performRequest(
                    message: message,
                    conversationId: conversationId,
                    configuration: config,
                    parser: parser,
                    session: session,
                    continuation: continuation
                )
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

    private static func performRequest(
        message: String,
        conversationId: String,
        configuration: BridgeConfiguration,
        parser: AgentEventParser,
        session: URLSession,
        continuation: AsyncStream<AgentEvent>.Continuation
    ) async {
        let url = configuration.agentChatURL
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
            continuation.finish()
            return
        }
        request.httpBody = bodyData

        do {
            let (bytes, response) = try await session.bytes(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                let msg = "Invalid response from agent server"
                print("[Agent] ERROR: \(msg)")
                continuation.yield(.error(message: msg))
                continuation.finish()
                return
            }

            guard httpResponse.statusCode == 200 else {
                let msg = "Agent returned HTTP \(httpResponse.statusCode)"
                print("[Agent] ERROR: \(msg)")
                continuation.yield(.error(message: msg))
                continuation.finish()
                return
            }

            print("[Agent] SSE stream connected, reading lines...")

            var currentEventType: String?
            var currentData: String?
            var lineCount = 0
            var buffer = ""

            for try await byte in bytes {
                guard !Task.isCancelled else {
                    print("[Agent] Task cancelled during read")
                    break
                }

                let char = Character(UnicodeScalar(byte))
                if char == "\n" {
                    let line = buffer
                    buffer = ""
                    lineCount += 1

                    if line.hasPrefix("event: ") {
                        currentEventType = String(line.dropFirst(7))
                    } else if line.hasPrefix("data: ") {
                        currentData = String(line.dropFirst(6))
                    } else if line.isEmpty {
                        if let eventType = currentEventType, let data = currentData {
                            if let event = parser.parse(eventType: eventType, data: data) {
                                logEvent(event)
                                continuation.yield(event)
                            } else {
                                print("[Agent] Failed to parse SSE: event=\(eventType)")
                            }
                        }
                        currentEventType = nil
                        currentData = nil
                    }
                } else {
                    buffer.append(char)
                }
            }

            print("[Agent] SSE stream ended after \(lineCount) lines")
            continuation.finish()
        } catch is CancellationError {
            print("[Agent] Request cancelled")
            continuation.finish()
        } catch let urlError as URLError where urlError.code == .cannotConnectToHost || urlError.code == .networkConnectionLost || urlError.code == .notConnectedToInternet {
            let msg = "Cannot reach agent server at \(url.host ?? "localhost"):\(url.port ?? 8766). Is pyax-agent running?"
            print("[Agent] ERROR: \(msg)")
            if !Task.isCancelled {
                continuation.yield(.error(message: msg))
            }
            continuation.finish()
        } catch {
            let msg = "Connection error: \(error.localizedDescription)"
            print("[Agent] ERROR: \(msg)")
            if !Task.isCancelled {
                continuation.yield(.error(message: msg))
            }
            continuation.finish()
        }
    }

    private static func logEvent(_ event: AgentEvent) {
        switch event {
        case .thinking(let status):
            print("[Agent] 💭 Thinking: \(status)")
        case .toolCall(let tool, let inputJSON):
            print("[Agent] 🔧 Tool call: \(tool) | \(inputJSON.prefix(200))")
        case .toolResult(let tool, let resultJSON):
            print("[Agent] ✅ Tool result: \(tool) | \(resultJSON.prefix(200))")
        case .message(let content):
            print("[Agent] 💬 \(content.prefix(200))")
        case .done:
            print("[Agent] ✓ Done")
        case .error(let message):
            print("[Agent] ❌ Error: \(message)")
        case .highlight(let rects, let duration):
            print("[Agent] 🔍 Highlight \(rects.count) elements for \(duration)s")
        case .speak(let text, _):
            print("[Agent] 🔊 Speak: \(text.prefix(100))")
        case .clearHighlights:
            print("[Agent] 🔍 Clear highlights")
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
