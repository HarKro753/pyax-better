import SwiftUI

/// A single event bubble displayed in the chat-style event stream.
/// Extracted as a separate struct for optimal SwiftUI diffing performance.
struct EventBubbleView: View {
    let event: AccessibilityEvent

    private static let timeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss.SSS"
        return f
    }()

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            // Event type icon
            Image(systemName: event.iconName)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(categoryColor)
                .frame(width: 28, height: 28)
                .background(categoryColor.opacity(0.15))
                .clipShape(.rect(cornerRadius: 8))

            // Event content
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(event.notificationLabel)
                        .font(.system(.subheadline, design: .monospaced, weight: .semibold))
                        .foregroundStyle(categoryColor)

                    Spacer()

                    Text(Self.timeFormatter.string(from: event.timestamp))
                        .font(.system(.caption2, design: .monospaced))
                        .foregroundStyle(.secondary)
                }

                if let role = event.role, !role.isEmpty {
                    HStack(spacing: 4) {
                        Text(role)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(.primary)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(.quaternary)
                            .clipShape(.rect(cornerRadius: 4))

                        if let title = event.title, !title.isEmpty {
                            Text(title)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                    }
                }

                if let value = event.value, !value.isEmpty, value != "None" {
                    Text(value)
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .lineLimit(2)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    private var categoryColor: Color {
        switch event.category {
        case .focus:
            return .blue
        case .change:
            return .orange
        case .lifecycle:
            return .green
        case .layout:
            return .purple
        case .selection:
            return .cyan
        case .other:
            return .gray
        }
    }
}
