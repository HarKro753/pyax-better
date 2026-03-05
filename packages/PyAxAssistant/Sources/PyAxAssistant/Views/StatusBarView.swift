import SwiftUI

/// Status bar at the top of the window showing connection state and observed app.
struct StatusBarView: View {
    let observedAppName: String?
    let connectionStatus: AppState.ConnectionStatus
    let eventCount: Int
    let isPaused: Bool
    let onTogglePause: () -> Void
    let onClear: () -> Void
    let onToggleBridge: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            // Connection indicator
            ConnectionIndicator(status: connectionStatus)

            // App name
            VStack(alignment: .leading, spacing: 1) {
                Text(observedAppName ?? "No App Focused")
                    .font(.system(.subheadline, weight: .semibold))
                    .foregroundStyle(observedAppName != nil ? .primary : .secondary)

                Text(statusLabel)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            // Event counter
            Text("\(eventCount) events")
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(.quaternary)
                .clipShape(.rect(cornerRadius: 6))

            // Controls
            ToolbarControls(
                isPaused: isPaused,
                connectionStatus: connectionStatus,
                onTogglePause: onTogglePause,
                onClear: onClear,
                onToggleBridge: onToggleBridge
            )
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.bar)
    }

    private var statusLabel: String {
        switch connectionStatus {
        case .disconnected:
            return "Bridge offline"
        case .connecting:
            return "Connecting..."
        case .connected:
            return isPaused ? "Paused" : "Streaming"
        }
    }
}

/// Animated connection status indicator dot.
private struct ConnectionIndicator: View {
    let status: AppState.ConnectionStatus

    @State private var isAnimating = false

    var body: some View {
        Circle()
            .fill(indicatorColor)
            .frame(width: 10, height: 10)
            .overlay {
                Circle()
                    .stroke(indicatorColor.opacity(0.4), lineWidth: 2)
                    .scaleEffect(isAnimating ? 2.0 : 1.0)
                    .opacity(isAnimating ? 0 : 1)
            }
            .onChange(of: status) { _, newStatus in
                isAnimating = newStatus == .connected
            }
            .animation(
                isAnimating
                    ? .easeOut(duration: 1.5).repeatForever(autoreverses: false)
                    : .default,
                value: isAnimating
            )
            .onAppear {
                isAnimating = status == .connected
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

/// Toolbar control buttons.
private struct ToolbarControls: View {
    let isPaused: Bool
    let connectionStatus: AppState.ConnectionStatus
    let onTogglePause: () -> Void
    let onClear: () -> Void
    let onToggleBridge: () -> Void

    var body: some View {
        HStack(spacing: 6) {
            // Start/Stop Bridge
            Button(action: onToggleBridge) {
                Image(systemName: connectionStatus == .connected ? "stop.fill" : "play.fill")
                    .font(.system(size: 12))
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .help(connectionStatus == .connected ? "Stop bridge" : "Start bridge")

            // Pause/Resume
            Button(action: onTogglePause) {
                Image(systemName: isPaused ? "play" : "pause")
                    .font(.system(size: 12))
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .disabled(connectionStatus != .connected)
            .help(isPaused ? "Resume streaming" : "Pause streaming")

            // Clear
            Button(action: onClear) {
                Image(systemName: "trash")
                    .font(.system(size: 12))
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .help("Clear events")
        }
    }
}
