import SwiftUI

/// Main content view composing the status bar, search, and raw JSON event stream.
struct ContentView: View {
    @State private var appState = AppState()
    @State private var webSocket = WebSocketService()
    @State private var pythonBridge = PythonBridgeService()

    var body: some View {
        VStack(spacing: 0) {
            StatusBarView(
                observedAppName: appState.observedAppName,
                connectionStatus: appState.connectionStatus,
                eventCount: appState.messages.count,
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

            // Raw JSON stream or empty state
            if appState.filteredMessages.isEmpty {
                EmptyStreamView(connectionStatus: appState.connectionStatus)
            } else {
                EventStreamView(
                    messages: appState.filteredMessages,
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
        Task {
            try? await Task.sleep(for: .seconds(2))
            webSocket.connect()
        }
    }

    private func setupWebSocketCallbacks() {
        // Every raw JSON message goes straight to the UI
        webSocket.onRawMessage = { rawJSON in
            appState.appendMessage(rawJSON)
        }

        webSocket.onAppChanged = { name, pid in
            appState.updateObservedApp(name: name, pid: pid)
        }

        webSocket.onConnectionStatusChanged = { status in
            appState.connectionStatus = status
        }
    }
}

/// Search/filter bar for filtering messages by text.
private struct SearchBar: View {
    @Binding var filterText: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
                .font(.system(size: 11))

            TextField("Filter...", text: $filterText)
                .textFieldStyle(.plain)
                .font(.system(.caption, design: .monospaced))

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
