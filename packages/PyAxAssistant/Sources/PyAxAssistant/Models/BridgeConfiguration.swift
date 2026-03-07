import Foundation

struct BridgeConfiguration: Sendable {
    let host: String
    let agentPort: UInt16
    let maxChatMessages: Int
    let agentRequestTimeout: Duration

    static let `default` = BridgeConfiguration(
        host: "localhost",
        agentPort: 8766,
        maxChatMessages: 200,
        agentRequestTimeout: .seconds(120)
    )

    var agentChatURL: URL {
        URL(string: "http://\(host):\(agentPort)/chat")!
    }

    var agentStopURL: URL {
        URL(string: "http://\(host):\(agentPort)/stop")!
    }

    var agentHealthURL: URL {
        URL(string: "http://\(host):\(agentPort)/health")!
    }
}
