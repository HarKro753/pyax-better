import Foundation

/// Represents a single accessibility event received from the Python bridge.
struct AccessibilityEvent: Identifiable, Equatable {
    let id: UUID
    let app: String
    let notification: String
    let role: String?
    let title: String?
    let value: String?
    let timestamp: Date

    /// Human-readable label for the event notification type.
    var notificationLabel: String {
        // Strip "AX" prefix for cleaner display
        if notification.hasPrefix("AX") {
            return String(notification.dropFirst(2))
        }
        return notification
    }

    /// Short description of the element for display.
    var elementDescription: String {
        let parts = [role, title, value].compactMap { $0 }.filter { !$0.isEmpty }
        return parts.isEmpty ? "Unknown Element" : parts.joined(separator: " - ")
    }

    /// Icon name based on the event notification type.
    var iconName: String {
        switch notification {
        case let n where n.contains("Focus"):
            return "scope"
        case let n where n.contains("Value"):
            return "pencil"
        case let n where n.contains("Title"):
            return "textformat"
        case let n where n.contains("Created"):
            return "plus.circle"
        case let n where n.contains("Destroyed"):
            return "minus.circle"
        case let n where n.contains("Moved"), let n where n.contains("Resized"):
            return "arrow.up.left.and.arrow.down.right"
        case let n where n.contains("Load"):
            return "arrow.clockwise"
        case let n where n.contains("Selected"):
            return "checkmark.circle"
        case let n where n.contains("LiveRegion"):
            return "antenna.radiowaves.left.and.right"
        default:
            return "bell"
        }
    }

    /// Color category based on event type for visual distinction.
    var category: EventCategory {
        switch notification {
        case let n where n.contains("Focus"):
            return .focus
        case let n where n.contains("Value") || n.contains("Title"):
            return .change
        case let n where n.contains("Created") || n.contains("Load"):
            return .lifecycle
        case let n where n.contains("Destroyed"):
            return .lifecycle
        case let n where n.contains("Moved") || n.contains("Resized"):
            return .layout
        case let n where n.contains("Selected"):
            return .selection
        default:
            return .other
        }
    }

    static func == (lhs: AccessibilityEvent, rhs: AccessibilityEvent) -> Bool {
        lhs.id == rhs.id
    }
}

/// Categories of accessibility events for color-coding.
enum EventCategory {
    case focus
    case change
    case lifecycle
    case layout
    case selection
    case other
}
