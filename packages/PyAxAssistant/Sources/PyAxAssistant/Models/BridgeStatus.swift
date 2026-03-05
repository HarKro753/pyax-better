import Foundation

enum BridgeStatus: Equatable {
    case stopped
    case starting
    case running
    case error(String)

    var canStart: Bool {
        switch self {
        case .stopped, .error:
            return true
        case .starting, .running:
            return false
        }
    }

    var isError: Bool {
        if case .error = self {
            return true
        }
        return false
    }
}
