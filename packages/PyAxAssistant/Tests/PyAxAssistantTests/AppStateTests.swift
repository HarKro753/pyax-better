import Testing
import Foundation
@testable import PyAxAssistant

@MainActor
@Suite("AppState")
struct AppStateTests {

    // MARK: - Initial State

    @Test("Initial state has correct defaults")
    func initialState() {
        let sut = AppState()

        #expect(sut.connectionStatus == .disconnected)
        #expect(sut.observedAppName == nil)
        #expect(sut.observedAppPID == nil)
        #expect(sut.messages.isEmpty)
        #expect(sut.autoScroll == true)
        #expect(sut.isPaused == false)
        #expect(sut.filterText == "")
    }

    // MARK: - Connection Status

    @Test("Updating connection status changes state")
    func updateConnectionStatus() {
        let sut = AppState()

        sut.updateConnectionStatus(.connecting)
        #expect(sut.connectionStatus == .connecting)

        sut.updateConnectionStatus(.connected)
        #expect(sut.connectionStatus == .connected)

        sut.updateConnectionStatus(.disconnected)
        #expect(sut.connectionStatus == .disconnected)
    }

    // MARK: - Observed App

    @Test("Updating observed app stores name and pid")
    func updateObservedApp() {
        let sut = AppState()

        sut.updateObservedApp(name: "Safari", pid: 1234)

        #expect(sut.observedAppName == "Safari")
        #expect(sut.observedAppPID == 1234)
    }

    @Test("Clearing observed app sets nil values")
    func clearObservedApp() {
        let sut = AppState()
        sut.updateObservedApp(name: "Safari", pid: 1234)

        sut.updateObservedApp(name: nil, pid: nil)

        #expect(sut.observedAppName == nil)
        #expect(sut.observedAppPID == nil)
    }

    // MARK: - Messages

    @Test("Appending message adds to messages array")
    func appendMessage() {
        let sut = AppState()

        sut.appendMessage("{\"type\": \"event\"}")

        #expect(sut.messages.count == 1)
        #expect(sut.messages.first?.json == "{\"type\": \"event\"}")
    }

    @Test("Appending message while paused does nothing")
    func appendMessageWhilePaused() {
        let sut = AppState()
        sut.togglePause()

        sut.appendMessage("{\"type\": \"event\"}")

        #expect(sut.messages.isEmpty)
    }

    @Test("Messages are capped at configured maximum")
    func messagesCappedAtMax() {
        let config = BridgeConfiguration(
            host: "localhost",
            port: 8765,
            pingInterval: .seconds(15),
            commandTimeout: .seconds(10),
            maxReconnectDelay: .seconds(5),
            maxMessages: 5,
            gracefulShutdownTimeout: .seconds(2)
        )
        let sut = AppState(configuration: config)

        for i in 0..<10 {
            sut.appendMessage("message-\(i)")
        }

        #expect(sut.messages.count == 5)
        #expect(sut.messages.first?.json == "message-5")
        #expect(sut.messages.last?.json == "message-9")
    }

    @Test("Clear messages removes all messages")
    func clearMessages() {
        let sut = AppState()
        sut.appendMessage("test-1")
        sut.appendMessage("test-2")

        sut.clearMessages()

        #expect(sut.messages.isEmpty)
    }

    // MARK: - Filtering

    @Test("Filtered messages returns all when filter is empty")
    func filteredMessagesNoFilter() {
        let sut = AppState()
        sut.appendMessage("hello")
        sut.appendMessage("world")

        #expect(sut.filteredMessages.count == 2)
    }

    @Test("Filtered messages filters by text content")
    func filteredMessagesWithFilter() {
        let sut = AppState()
        sut.appendMessage("{\"type\": \"event\"}")
        sut.appendMessage("{\"type\": \"response\"}")
        sut.appendMessage("{\"type\": \"event\"}")

        sut.updateFilterText("response")

        #expect(sut.filteredMessages.count == 1)
        #expect(sut.filteredMessages.first?.json.contains("response") == true)
    }

    // MARK: - Toggle Actions

    @Test("Toggle pause flips isPaused state")
    func togglePause() {
        let sut = AppState()

        sut.togglePause()
        #expect(sut.isPaused == true)

        sut.togglePause()
        #expect(sut.isPaused == false)
    }

    @Test("Toggle auto scroll flips autoScroll state")
    func toggleAutoScroll() {
        let sut = AppState()

        sut.toggleAutoScroll()
        #expect(sut.autoScroll == false)

        sut.toggleAutoScroll()
        #expect(sut.autoScroll == true)
    }

    @Test("Update filter text changes filterText")
    func updateFilterText() {
        let sut = AppState()

        sut.updateFilterText("search term")

        #expect(sut.filterText == "search term")
    }


}
