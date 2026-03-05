import Testing
import Foundation
@testable import PyAxAssistant

@Suite("BridgeStatus")
struct BridgeStatusTests {

    @Test("Stopped status can start")
    func stoppedCanStart() {
        let status = BridgeStatus.stopped
        #expect(status.canStart == true)
    }

    @Test("Error status can start")
    func errorCanStart() {
        let status = BridgeStatus.error("something failed")
        #expect(status.canStart == true)
    }

    @Test("Starting status cannot start")
    func startingCannotStart() {
        let status = BridgeStatus.starting
        #expect(status.canStart == false)
    }

    @Test("Running status cannot start")
    func runningCannotStart() {
        let status = BridgeStatus.running
        #expect(status.canStart == false)
    }

    @Test("Error status is detected as error")
    func isErrorTrue() {
        let status = BridgeStatus.error("failure")
        #expect(status.isError == true)
    }

    @Test("Non-error statuses are not errors")
    func isErrorFalse() {
        #expect(BridgeStatus.stopped.isError == false)
        #expect(BridgeStatus.starting.isError == false)
        #expect(BridgeStatus.running.isError == false)
    }

    @Test("Equatable works for error cases with same message")
    func equatableErrorSameMessage() {
        let a = BridgeStatus.error("crash")
        let b = BridgeStatus.error("crash")
        #expect(a == b)
    }

    @Test("Equatable works for error cases with different messages")
    func equatableErrorDifferentMessage() {
        let a = BridgeStatus.error("crash")
        let b = BridgeStatus.error("timeout")
        #expect(a != b)
    }
}
