import Testing
import Foundation
@testable import PyAxAssistant

@Suite("BridgeResponse")
struct BridgeResponseTests {

    @Test("Subscript returns values from json")
    func subscriptAccess() {
        let sut = BridgeResponse(json: ["key": "value", "number": 42])

        #expect(sut["key"] as? String == "value")
        #expect(sut["number"] as? Int == 42)
        #expect(sut["missing"] == nil)
    }

    @Test("Command computed property extracts command field")
    func commandProperty() {
        let sut = BridgeResponse(json: ["command": "get_tree"])

        #expect(sut.command == "get_tree")
    }

    @Test("Command returns nil when not present")
    func commandMissing() {
        let sut = BridgeResponse(json: [:])

        #expect(sut.command == nil)
    }

    @Test("Error computed property extracts error field")
    func errorProperty() {
        let sut = BridgeResponse(json: ["error": "not found"])

        #expect(sut.error == "not found")
    }

    @Test("IsSuccess returns true when no error")
    func isSuccessTrue() {
        let sut = BridgeResponse(json: ["command": "get_tree"])

        #expect(sut.isSuccess == true)
    }

    @Test("IsSuccess returns false when error present")
    func isSuccessFalse() {
        let sut = BridgeResponse(json: ["error": "failed"])

        #expect(sut.isSuccess == false)
    }

    @Test("Json property exposes the underlying dictionary")
    func jsonProperty() {
        let original: [String: Any] = ["type": "response", "id": "abc"]
        let sut = BridgeResponse(json: original)

        #expect(sut.json["type"] as? String == "response")
        #expect(sut.json["id"] as? String == "abc")
    }
}
