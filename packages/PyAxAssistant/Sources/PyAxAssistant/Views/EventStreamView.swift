import SwiftUI

struct EventStreamView: View {
    let messages: [RawMessage]
    let autoScroll: Bool

    private let _bottomAnchorID = "stream-bottom"

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(messages) { message in
                        RawMessageView(message: message)
                            .id(message.id)

                        Divider()
                            .opacity(0.15)
                    }

                    Color.clear
                        .frame(height: 1)
                        .id(_bottomAnchorID)
                }
            }
            .scrollIndicators(.hidden)
            .onChange(of: messages.count) { _, _ in
                if autoScroll {
                    withAnimation(.easeOut(duration: 0.15)) {
                        proxy.scrollTo(_bottomAnchorID, anchor: .bottom)
                    }
                }
            }
            .onAppear {
                if autoScroll {
                    proxy.scrollTo(_bottomAnchorID, anchor: .bottom)
                }
            }
        }
    }
}

struct RawMessageView: View {
    let message: RawMessage

    var body: some View {
        Text(message.json)
            .font(.system(size: 10, design: .monospaced))
            .foregroundStyle(.primary.opacity(0.85))
            .textSelection(.enabled)
            .lineLimit(nil)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
    }
}

struct EmptyStreamView: View {
    let connectionStatus: ConnectionStatus

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
        case .disconnected: return "wifi.slash"
        case .connecting: return "antenna.radiowaves.left.and.right"
        case .connected: return "eye.slash"
        }
    }

    private var statusTitle: String {
        switch connectionStatus {
        case .disconnected: return "Disconnected"
        case .connecting: return "Connecting..."
        case .connected: return "Waiting for Events"
        }
    }

    private var statusMessage: String {
        switch connectionStatus {
        case .disconnected: return "The Python bridge is not running."
        case .connecting: return "Connecting to the accessibility bridge..."
        case .connected: return "Switch to another app to see raw JSON events."
        }
    }
}
