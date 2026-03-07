import Testing
import Foundation
@testable import PyAxAssistant

@Suite("BridgeConfiguration")
struct BridgeConfigurationTests {

    @Test("Default configuration has expected values")
    func defaultValues() {
        let sut = BridgeConfiguration.default

        #expect(sut.host == "localhost")
        #expect(sut.agentPort == 8766)
        #expect(sut.maxChatMessages == 200)
        #expect(sut.agentRequestTimeout == .seconds(120))
    }

    @Test("Agent URLs are constructed correctly")
    func agentURLs() {
        let sut = BridgeConfiguration.default

        #expect(sut.agentChatURL.absoluteString == "http://localhost:8766/chat")
        #expect(sut.agentStopURL.absoluteString == "http://localhost:8766/stop")
        #expect(sut.agentHealthURL.absoluteString == "http://localhost:8766/health")
    }

    @Test("Custom configuration preserves values")
    func customConfiguration() {
        let sut = BridgeConfiguration(
            host: "192.168.1.100",
            agentPort: 9998,
            maxChatMessages: 50,
            agentRequestTimeout: .seconds(60)
        )

        #expect(sut.host == "192.168.1.100")
        #expect(sut.agentPort == 9998)
        #expect(sut.maxChatMessages == 50)
        #expect(sut.agentChatURL.absoluteString == "http://192.168.1.100:9998/chat")
    }
}
