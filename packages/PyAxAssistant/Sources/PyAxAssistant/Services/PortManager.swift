import Foundation

struct PortManager {

    func killProcessOnPort(_ port: UInt16) {
        let pids = findProcessesOnPort(port)
        guard !pids.isEmpty else { return }

        let myPID = ProcessInfo.processInfo.processIdentifier

        for pid in pids where pid != myPID {
            kill(pid, SIGTERM)
        }

        usleep(500_000)

        for pid in pids where pid != myPID {
            if kill(pid, 0) == 0 {
                kill(pid, SIGKILL)
            }
        }
    }

    // MARK: - Private

    private func findProcessesOnPort(_ port: UInt16) -> [Int32] {
        let lsof = Process()
        let pipe = Pipe()
        lsof.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        lsof.arguments = ["-ti", "tcp:\(port)"]
        lsof.standardOutput = pipe
        lsof.standardError = FileHandle.nullDevice

        do {
            try lsof.run()
            lsof.waitUntilExit()
        } catch {
            return []
        }

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let output = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              !output.isEmpty
        else { return [] }

        return output
            .split(separator: "\n")
            .compactMap { Int32($0.trimmingCharacters(in: .whitespaces)) }
    }
}
