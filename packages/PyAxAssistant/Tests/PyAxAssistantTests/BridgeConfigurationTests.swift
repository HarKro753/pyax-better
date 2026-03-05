import Testing
import Foundation
@testable import PyAxAssistant

@Suite("BridgeConfiguration")
struct BridgeConfigurationTests {

    @Test("Default configuration has expected values")
    func defaultValues() {
        let sut = BridgeConfiguration.default

        #expect(sut.host == "localhost")
        #expect(sut.port == 8765)
        #expect(sut.pingInterval == .seconds(15))
        #expect(sut.commandTimeout == .seconds(10))
        #expect(sut.maxReconnectDelay == .seconds(5))
        #expect(sut.maxMessages == 500)
        #expect(sut.gracefulShutdownTimeout == .seconds(2))
    }

    @Test("WebSocket URL is constructed correctly")
    func webSocketURL() {
        let sut = BridgeConfiguration.default

        #expect(sut.webSocketURL.absoluteString == "ws://localhost:8765")
    }

    @Test("Custom configuration preserves values")
    func customConfiguration() {
        let sut = BridgeConfiguration(
            host: "192.168.1.100",
            port: 9999,
            pingInterval: .seconds(30),
            commandTimeout: .seconds(20),
            maxReconnectDelay: .seconds(10),
            maxMessages: 1000,
            gracefulShutdownTimeout: .seconds(5)
        )

        #expect(sut.host == "192.168.1.100")
        #expect(sut.port == 9999)
        #expect(sut.maxMessages == 1000)
        #expect(sut.webSocketURL.absoluteString == "ws://192.168.1.100:9999")
    }
}
