import SwiftUI

struct ContentView: View {
    @Environment(AppState.self) private var appState
    @Environment(WebSocketService.self) private var webSocket
    @Environment(PythonBridgeService.self) private var pythonBridge

    var body: some View {
        VStack(spacing: 0) {
            StatusBarView(
                observedAppName: appState.observedAppName,
                connectionStatus: appState.connectionStatus,
                eventCount: appState.messages.count,
                isPaused: appState.isPaused,
                onTogglePause: { appState.togglePause() },
                onClear: { appState.clearMessages() },
                onToggleBridge: toggleBridge
            )

            Divider()
                .opacity(0.3)

            SearchBar(
                filterText: appState.filterText,
                onFilterChanged: { appState.updateFilterText($0) }
            )

            Divider()
                .opacity(0.3)

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
            webSocket.delegate = appState
            startBridge()
        }
        .onDisappear {
            webSocket.disconnect()
            pythonBridge.stop()
        }
    }

    // MARK: - Actions

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
}

struct SearchBar: View {
    let filterText: String
    let onFilterChanged: (String) -> Void

    @State private var _localText = ""

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)
                .font(.system(size: 11))

            TextField("Filter...", text: $_localText)
                .textFieldStyle(.plain)
                .font(.system(.caption, design: .monospaced))

            if !_localText.isEmpty {
                Button {
                    _localText = ""
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
        .onAppear { _localText = filterText }
        .onChange(of: _localText) { _, newValue in
            onFilterChanged(newValue)
        }
    }
}
