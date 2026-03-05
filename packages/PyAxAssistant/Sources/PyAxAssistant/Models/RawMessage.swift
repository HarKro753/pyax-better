import Foundation

struct RawMessage: Identifiable, Equatable {
    let id: UUID
    let json: String

    static func == (lhs: RawMessage, rhs: RawMessage) -> Bool {
        lhs.id == rhs.id
    }
}
