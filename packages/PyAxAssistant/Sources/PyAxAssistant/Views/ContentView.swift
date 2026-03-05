import SwiftUI

/// Main content view composing the status bar, search, and event stream.
/// Designed for a translucent floating panel — all backgrounds are clear/glassy.
struct ContentView: View {
    @State private var appState = AppState()
    @State private var webSocket = WebSocketService()
    @State private var pythonBridge = PythonBridgeService()

    var body: some View {
        VStack(spacing: 0) {
            // Draggable title area with status
            StatusBarView(
                observedAppName: appState.observedAppName,
                connectionStatus: appState.connectionStatus,
                eventCount: appState.events.count,
                isPaused: appState.isPaused,
                onTogglePause: togglePause,
                onClear: clearEvents,
                onToggleBridge: toggleBridge
            )

            Divider()
                .opacity(0.3)

            // Search/filter bar
            SearchBar(filterText: Binding(
                get: { appState.filterText },
                set: { appState.filterText = $0 }
            ))

            Divider()
                .opacity(0.3)

            // Event stream or empty state
            if appState.filteredEvents.isEmpty {
                EmptyStreamView(connectionStatus: appState.connectionStatus)
            } else {
                EventStreamView(
                    events: appState.filteredEvents,
                    autoScroll: appState.autoScroll
                )
            }
        }
        .frame(minWidth: 340, minHeight: 300)
        .task {
            setupWebSocketCallbacks()
            startBridge()
        }
        .onDisappear {
            webSocket.disconnect()
            pythonBridge.stop()
        }
    }

    // MARK: - Actions

    private func togglePause() {
        appState.isPaused.toggle()
    }

    private func clearEvents() {
        appState.clearEvents()
    }

    private func toggleBridge() {
        if appState.connectionStatus == .connected {
            webSocket.disconnect()
            pythonBridge.stop()
        } else {
            startBridge()
        }
    }

    private func startBridge() {
        pythonBridge.start()

        // Give the Python process a moment to start the WebSocket server
        Task {
            try? await Task.sleep(for: .seconds(2))
            webSocket.connect()
        }
    }

    private func setupWebSocketCallbacks() {
        webSocket.onEvent = { event in
            appState.appendEvent(event)
        }

        webSocket.onAppChanged = { name, pid in
            appState.updateObservedApp(name: name, pid: pid)
        }

        webSocket.onConnectionStatusChanged = { status in
            appState.connectionStatus = status
        }
    }
}

/// Search/filter bar for filtering events by text.
private struct SearchBar: View {
    @Binding var filterText: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
                .font(.system(size: 11))

            TextField("Filter events...", text: $filterText)
                .textFieldStyle(.plain)
                .font(.system(.caption))

            if !filterText.isEmpty {
                Button {
                    filterText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.tertiary)
                        .font(.system(size: 11))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 5)
    }
}
