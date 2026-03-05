import Foundation

struct BridgeConfiguration: Sendable {
    let host: String
    let port: UInt16
    let pingInterval: Duration
    let commandTimeout: Duration
    let maxReconnectDelay: Duration
    let maxMessages: Int
    let gracefulShutdownTimeout: Duration

    static let `default` = BridgeConfiguration(
        host: "localhost",
        port: 8765,
        pingInterval: .seconds(15),
        commandTimeout: .seconds(10),
        maxReconnectDelay: .seconds(5),
        maxMessages: 500,
        gracefulShutdownTimeout: .seconds(2)
    )

    var webSocketURL: URL {
        URL(string: "ws://\(host):\(port)")!
    }
}
