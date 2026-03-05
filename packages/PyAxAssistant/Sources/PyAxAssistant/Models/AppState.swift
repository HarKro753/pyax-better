import Foundation
import SwiftUI

/// Main application state using @Observable (modern SwiftUI pattern).
/// Owns the event stream, connection state, and currently observed app info.
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

    // MARK: - Event Stream

    private(set) var events: [AccessibilityEvent] = []

    /// Maximum number of events to keep in memory to prevent unbounded growth.
    private let maxEvents = 500

    /// Whether auto-scroll is enabled (follows new events).
    var autoScroll = true

    /// Whether the event stream is paused.
    var isPaused = false

    /// Filter text for searching events.
    var filterText = ""

    /// Filtered events based on search text.
    var filteredEvents: [AccessibilityEvent] {
        if filterText.isEmpty {
            return events
        }
        return events.filter { event in
            event.notification.localizedStandardContains(filterText)
                || (event.role?.localizedStandardContains(filterText) ?? false)
                || (event.title?.localizedStandardContains(filterText) ?? false)
                || (event.value?.localizedStandardContains(filterText) ?? false)
        }
    }

    // MARK: - Actions

    func appendEvent(_ event: AccessibilityEvent) {
        guard !isPaused else { return }
        events.append(event)
        // Trim old events to keep memory bounded
        if events.count > maxEvents {
            events.removeFirst(events.count - maxEvents)
        }
    }

    func clearEvents() {
        events.removeAll()
    }

    func updateObservedApp(name: String?, pid: Int?) {
        observedAppName = name
        observedAppPID = pid
    }
}
