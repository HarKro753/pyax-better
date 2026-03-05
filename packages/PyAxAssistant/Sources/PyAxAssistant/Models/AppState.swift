import Foundation
import SwiftUI

/// Main application state using @Observable (modern SwiftUI pattern).
/// Stores raw JSON messages from the bridge for debug display.
@Observable
@MainActor
final class AppState {

    // MARK: - Connection State

    enum ConnectionStatus: Equatable {
        case disconnected
        case connecting
        case connected
    }

    var connectionStatus: ConnectionStatus = .disconnected

    // MARK: - Observed App

    var observedAppName: String?
    var observedAppPID: Int?

    // MARK: - Raw Message Stream

    /// Raw JSON messages from the bridge, newest last.
    private(set) var messages: [RawMessage] = []

    /// Maximum number of messages to keep in memory.
    private let maxMessages = 500

    /// Whether auto-scroll is enabled.
    var autoScroll = true

    /// Whether the stream is paused.
    var isPaused = false

    /// Filter text for searching messages.
    var filterText = ""

    /// Filtered messages based on search text.
    var filteredMessages: [RawMessage] {
        if filterText.isEmpty {
            return messages
        }
        return messages.filter { $0.json.localizedStandardContains(filterText) }
    }

    // MARK: - Actions

    func appendMessage(_ json: String) {
        guard !isPaused else { return }
        messages.append(RawMessage(id: UUID(), json: json))
        if messages.count > maxMessages {
            messages.removeFirst(messages.count - maxMessages)
        }
    }

    func clearEvents() {
        messages.removeAll()
    }

    func updateObservedApp(name: String?, pid: Int?) {
        observedAppName = name
        observedAppPID = pid
    }
}

/// A single raw JSON message for display.
struct RawMessage: Identifiable, Equatable {
    let id: UUID
    let json: String

    static func == (lhs: RawMessage, rhs: RawMessage) -> Bool {
        lhs.id == rhs.id
    }
}
