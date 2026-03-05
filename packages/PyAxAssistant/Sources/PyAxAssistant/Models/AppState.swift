import Foundation
import SwiftUI

@Observable
@MainActor
final class AppState {

    // MARK: - Private State

    private var _connectionStatus: ConnectionStatus = .disconnected
    private var _observedAppName: String?
    private var _observedAppPID: Int?
    private var _messages: [RawMessage] = []
    private var _autoScroll = true
    private var _isPaused = false
    private var _filterText = ""
    private let _configuration: BridgeConfiguration

    // MARK: - Read Access

    var connectionStatus: ConnectionStatus { _connectionStatus }
    var observedAppName: String? { _observedAppName }
    var observedAppPID: Int? { _observedAppPID }
    var messages: [RawMessage] { _messages }
    var autoScroll: Bool { _autoScroll }
    var isPaused: Bool { _isPaused }
    var filterText: String { _filterText }

    var filteredMessages: [RawMessage] {
        if _filterText.isEmpty {
            return _messages
        }
        return _messages.filter { $0.json.localizedStandardContains(_filterText) }
    }

    // MARK: - Init

    init(configuration: BridgeConfiguration = .default) {
        self._configuration = configuration
    }

    // MARK: - Mutation Methods

    func updateConnectionStatus(_ status: ConnectionStatus) {
        _connectionStatus = status
    }

    func updateObservedApp(name: String?, pid: Int?) {
        _observedAppName = name
        _observedAppPID = pid
    }

    func appendMessage(_ json: String) {
        guard !_isPaused else { return }
        _messages.append(RawMessage(id: UUID(), json: json))
        if _messages.count > _configuration.maxMessages {
            _messages.removeFirst(_messages.count - _configuration.maxMessages)
        }
    }

    func clearMessages() {
        _messages.removeAll()
    }

    func togglePause() {
        _isPaused.toggle()
    }

    func toggleAutoScroll() {
        _autoScroll.toggle()
    }

    func updateFilterText(_ text: String) {
        _filterText = text
    }
}
