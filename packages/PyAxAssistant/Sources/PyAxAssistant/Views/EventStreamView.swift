import SwiftUI

/// Chat-style scrolling event stream that displays accessibility events.
/// Uses LazyVStack for performance and ScrollViewReader for auto-scrolling.
struct EventStreamView: View {
    let events: [AccessibilityEvent]
    let autoScroll: Bool

    private let bottomAnchorID = "stream-bottom"

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(events) { event in
                        EventBubbleView(event: event)
                            .id(event.id)

                        Divider()
                            .opacity(0.15)
                            .padding(.leading, 40)
                    }

                    // Invisible anchor for auto-scrolling
                    Color.clear
                        .frame(height: 1)
                        .id(bottomAnchorID)
                }
            }
            .scrollIndicators(.hidden)
            .onChange(of: events.count) { _, _ in
                if autoScroll {
                    withAnimation(.easeOut(duration: 0.15)) {
                        proxy.scrollTo(bottomAnchorID, anchor: .bottom)
                    }
                }
            }
            .onAppear {
                if autoScroll {
                    proxy.scrollTo(bottomAnchorID, anchor: .bottom)
                }
            }
        }
    }
}

/// Placeholder view when no events are being received.
struct EmptyStreamView: View {
    let connectionStatus: AppState.ConnectionStatus

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: statusIcon)
                .font(.system(size: 32))
                .foregroundStyle(.tertiary)

            Text(statusTitle)
                .font(.system(.caption, weight: .semibold))
                .foregroundStyle(.secondary)

            Text(statusMessage)
                .font(.system(size: 10))
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 240)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var statusIcon: String {
        switch connectionStatus {
        case .disconnected:
            return "wifi.slash"
        case .connecting:
            return "antenna.radiowaves.left.and.right"
        case .connected:
            return "eye.slash"
        }
    }

    private var statusTitle: String {
        switch connectionStatus {
        case .disconnected:
            return "Disconnected"
        case .connecting:
            return "Connecting..."
        case .connected:
            return "Waiting for Events"
        }
    }

    private var statusMessage: String {
        switch connectionStatus {
        case .disconnected:
            return "The Python bridge is not running. Click the play button to start."
        case .connecting:
            return "Establishing connection to the accessibility bridge..."
        case .connected:
            return "Switch to another application to see its accessibility events here."
        }
    }
}
