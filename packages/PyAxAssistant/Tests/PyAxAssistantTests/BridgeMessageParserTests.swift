import Testing
import Foundation
@testable import PyAxAssistant

@Suite("BridgeMessageParser")
struct BridgeMessageParserTests {

    private let sut = BridgeMessageParser()

    // MARK: - App Changed

    @Test("Parses app_changed message correctly")
    func parseAppChanged() {
        let json = "{\"type\": \"app_changed\", \"app\": \"Safari\", \"pid\": 1234}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .appChanged(let name, let pid) = result?.bridgeMessage {
            #expect(name == "Safari")
            #expect(pid == 1234)
        } else {
            Issue.record("Expected appChanged message")
        }
    }

    // MARK: - Response

    @Test("Parses response message correctly")
    func parseResponse() {
        let json = "{\"type\": \"response\", \"id\": \"abc-123\", \"command\": \"get_tree\", \"tree\": {}}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .response(let requestId, let responseJson) = result?.bridgeMessage {
            #expect(requestId == "abc-123")
            #expect(responseJson["command"] as? String == "get_tree")
        } else {
            Issue.record("Expected response message")
        }
    }

    // MARK: - Error Response

    @Test("Parses error response correctly")
    func parseErrorResponse() {
        let json = "{\"type\": \"response\", \"id\": \"abc-123\", \"error\": \"Element not found\"}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .error(let requestId, let errorMessage) = result?.bridgeMessage {
            #expect(requestId == "abc-123")
            #expect(errorMessage == "Element not found")
        } else {
            Issue.record("Expected error message")
        }
    }

    // MARK: - Pong

    @Test("Parses pong message correctly")
    func parsePong() {
        let json = "{\"type\": \"pong\"}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .pong = result?.bridgeMessage {
            // success
        } else {
            Issue.record("Expected pong message")
        }
    }

    // MARK: - Event

    @Test("Parses event message correctly")
    func parseEvent() {
        let json = "{\"type\": \"event\", \"data\": \"something\"}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .event(let eventJson) = result?.bridgeMessage {
            #expect(eventJson["type"] as? String == "event")
        } else {
            Issue.record("Expected event message")
        }
    }

    // MARK: - Unknown Type

    @Test("Parses unknown message type as unknown")
    func parseUnknown() {
        let json = "{\"type\": \"custom_type\"}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .unknown(let type) = result?.bridgeMessage {
            #expect(type == "custom_type")
        } else {
            Issue.record("Expected unknown message")
        }
    }

    // MARK: - Raw Text Passthrough

    @Test("Raw text is preserved in output")
    func rawTextPreserved() {
        let originalJSON = "{\"type\": \"event\", \"data\": \"test\"}"
        let message = URLSessionWebSocketTask.Message.string(originalJSON)

        let result = sut.parse(message)

        #expect(result?.rawText == originalJSON)
    }

    // MARK: - Invalid Input

    @Test("Returns nil for invalid JSON")
    func invalidJSON() {
        let message = URLSessionWebSocketTask.Message.string("not json")

        let result = sut.parse(message)

        #expect(result == nil)
    }

    @Test("Returns nil for JSON without type field")
    func missingTypeField() {
        let json = "{\"data\": \"no type\"}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result == nil)
    }

    // MARK: - Malformed Messages

    @Test("Returns unknown for app_changed missing required fields")
    func appChangedMissingFields() {
        let json = "{\"type\": \"app_changed\"}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .unknown = result?.bridgeMessage {
            // Correctly falls back to unknown
        } else {
            Issue.record("Expected unknown for malformed app_changed")
        }
    }

    @Test("Returns unknown for response missing id")
    func responseMissingId() {
        let json = "{\"type\": \"response\", \"command\": \"get_tree\"}"
        let message = URLSessionWebSocketTask.Message.string(json)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .unknown = result?.bridgeMessage {
            // Correctly falls back to unknown
        } else {
            Issue.record("Expected unknown for response without id")
        }
    }

    // MARK: - Binary Data

    @Test("Parses binary data message")
    func parseBinaryData() {
        let json = "{\"type\": \"pong\"}"
        let data = json.data(using: .utf8)!
        let message = URLSessionWebSocketTask.Message.data(data)

        let result = sut.parse(message)

        #expect(result != nil)
        if case .pong = result?.bridgeMessage {
            // success
        } else {
            Issue.record("Expected pong from binary data")
        }
    }
}
