import SwiftUI

/// A single event bubble displayed in the chat-style event stream.
/// Styled for the translucent overlay — uses subtle, glassy elements.
struct EventBubbleView: View {
    let event: AccessibilityEvent

    private static let timeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss.SSS"
        return f
    }()

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            // Event type icon
            Image(systemName: event.iconName)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(categoryColor)
                .frame(width: 22, height: 22)
                .background(categoryColor.opacity(0.12))
                .clipShape(.rect(cornerRadius: 6))

            // Event content
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline) {
                    Text(event.notificationLabel)
                        .font(.system(.caption, design: .monospaced, weight: .semibold))
                        .foregroundStyle(categoryColor)

                    Spacer()

                    Text(Self.timeFormatter.string(from: event.timestamp))
                        .font(.system(size: 9, weight: .regular, design: .monospaced))
                        .foregroundStyle(.secondary.opacity(0.7))
                }

                if let role = event.role, !role.isEmpty {
                    HStack(spacing: 4) {
                        Text(role)
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .foregroundStyle(.primary.opacity(0.8))
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(.white.opacity(0.08))
                            .clipShape(.rect(cornerRadius: 3))

                        if let title = event.title, !title.isEmpty {
                            Text(title)
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary.opacity(0.7))
                                .lineLimit(1)
                        }
                    }
                }

                if let value = event.value, !value.isEmpty, value != "None" {
                    Text(value)
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
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
