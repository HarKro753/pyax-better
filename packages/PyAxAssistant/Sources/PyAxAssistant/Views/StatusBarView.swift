import SwiftUI

struct StatusBarView: View {
    let observedAppName: String?
    let connectionStatus: ConnectionStatus
    let eventCount: Int
    let isPaused: Bool
    let onTogglePause: () -> Void
    let onClear: () -> Void
    let onToggleBridge: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            ConnectionIndicator(status: connectionStatus)

            VStack(alignment: .leading, spacing: 1) {
                Text(observedAppName ?? "No App Focused")
                    .font(.system(.caption, weight: .semibold))
                    .foregroundStyle(observedAppName != nil ? .primary : .secondary)

                Text(statusLabel)
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Text("\(eventCount)")
                .font(.system(.caption2, design: .monospaced, weight: .medium))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(.white.opacity(0.1))
                .clipShape(.rect(cornerRadius: 4))

            ToolbarControls(
                isPaused: isPaused,
                connectionStatus: connectionStatus,
                onTogglePause: onTogglePause,
                onClear: onClear,
                onToggleBridge: onToggleBridge
            )
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    private var statusLabel: String {
        switch connectionStatus {
        case .disconnected:
            return "Bridge offline"
        case .connecting:
            return "Connecting..."
        case .connected:
            if isPaused {
                return "Paused"
            } else {
                return "Streaming"
            }
        }
    }
}

private struct ConnectionIndicator: View {
    let status: ConnectionStatus

    @State private var _isAnimating = false

    var body: some View {
        Circle()
            .fill(indicatorColor)
            .frame(width: 8, height: 8)
            .overlay {
                Circle()
                    .stroke(indicatorColor.opacity(0.4), lineWidth: 1.5)
                    .scaleEffect(_isAnimating ? 2.0 : 1.0)
                    .opacity(_isAnimating ? 0 : 1)
            }
            .onChange(of: status) { _, newStatus in
                _isAnimating = newStatus == .connected
            }
            .animation(
                _isAnimating
                    ? .easeOut(duration: 1.5).repeatForever(autoreverses: false)
                    : .default,
                value: _isAnimating
            )
            .onAppear {
                _isAnimating = status == .connected
            }
    }

    private var indicatorColor: Color {
        switch status {
        case .disconnected:
            return .red
        case .connecting:
            return .yellow
        case .connected:
            return .green
        }
    }
}

private struct ToolbarControls: View {
    let isPaused: Bool
    let connectionStatus: ConnectionStatus
    let onTogglePause: () -> Void
    let onClear: () -> Void
    let onToggleBridge: () -> Void

    var body: some View {
        HStack(spacing: 4) {
            overlayButton(
                icon: connectionStatus == .connected ? "stop.fill" : "play.fill",
                action: onToggleBridge,
                help: connectionStatus == .connected ? "Stop bridge" : "Start bridge"
            )

            overlayButton(
                icon: isPaused ? "play" : "pause",
                action: onTogglePause,
                help: isPaused ? "Resume" : "Pause"
            )
            .disabled(connectionStatus != .connected)

            overlayButton(
                icon: "trash",
                action: onClear,
                help: "Clear"
            )
        }
    }

    private func overlayButton(icon: String, action: @escaping () -> Void, help: String) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 10, weight: .medium))
                .frame(width: 22, height: 22)
        }
        .buttonStyle(.plain)
        .foregroundStyle(.secondary)
        .background(.white.opacity(0.08))
        .clipShape(.rect(cornerRadius: 5))
        .help(help)
    }
}
