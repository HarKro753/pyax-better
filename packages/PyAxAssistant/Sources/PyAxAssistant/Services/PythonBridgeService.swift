import Foundation

/// Service responsible for spawning and managing the Python bridge process.
/// Launches `python3 -m pyax.bridge` as a child process that communicates via WebSocket.
@Observable
@MainActor
final class PythonBridgeService {

    // MARK: - State

    enum BridgeStatus: Equatable {
        case stopped
        case starting
        case running
        case error(String)
    }

    private(set) var status: BridgeStatus = .stopped
    private var process: Process?
    private var outputPipe: Pipe?
    private var errorPipe: Pipe?

    /// Path to the Python 3 executable.
    private let pythonPath: String

    // MARK: - Init

    init() {
        self.pythonPath = Self.findPython3()
    }

    // MARK: - Lifecycle

    /// The port used by the Python bridge WebSocket server.
    private static let bridgePort: UInt16 = 8765

    func start() {
        guard status == .stopped || {
            if case .error = status { return true }
            return false
        }() else { return }

        status = .starting

        // Kill any orphaned process still holding the bridge port
        Self.killProcessOnPort(Self.bridgePort)

        let process = Process()
        let outputPipe = Pipe()
        let errorPipe = Pipe()

        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = ["-m", "pyax.bridge"]
        process.standardOutput = outputPipe
        process.standardError = errorPipe

        // Set environment so Python can find the pyax package
        var env = ProcessInfo.processInfo.environment
        let userSitePackages = "\(NSHomeDirectory())/Library/Python/3.9/lib/python/site-packages"
        let localPyaxSrc = Self.findPyaxSrcPath()
        var pythonPaths = [localPyaxSrc, userSitePackages]
        if let existing = env["PYTHONPATH"] {
            pythonPaths.append(existing)
        }
        env["PYTHONPATH"] = pythonPaths.joined(separator: ":")
        process.environment = env

        // Drain stdout/stderr so the pipe doesn't block
        outputPipe.fileHandleForReading.readabilityHandler = { handle in
            _ = handle.availableData
        }
        errorPipe.fileHandleForReading.readabilityHandler = { handle in
            _ = handle.availableData
        }

        process.terminationHandler = { [weak self] process in
            Task { @MainActor in
                guard let self else { return }
                if process.terminationStatus != 0 {
                    self.status = .error("Process exited with code \(process.terminationStatus)")
                } else {
                    self.status = .stopped
                }
            }
        }

        do {
            try process.run()
            self.process = process
            self.outputPipe = outputPipe
            self.errorPipe = errorPipe
            status = .running
        } catch {
            status = .error("Failed to start: \(error.localizedDescription)")
        }
    }

    func stop() {
        guard let process, process.isRunning else {
            status = .stopped
            return
        }

        process.terminate()

        // Wait for graceful exit on a background queue, then force-kill if needed
        let capturedProcess = process
        DispatchQueue.global().async { [weak self] in
            // Give the process up to 2 seconds to terminate gracefully
            for _ in 0..<20 {
                if !capturedProcess.isRunning { break }
                usleep(100_000) // 100ms
            }
            if capturedProcess.isRunning {
                capturedProcess.interrupt()
                usleep(500_000) // 500ms
                if capturedProcess.isRunning {
                    // Last resort: kill via pid
                    kill(capturedProcess.processIdentifier, SIGKILL)
                }
            }
            Task { @MainActor in
                self?.status = .stopped
            }
        }

        outputPipe?.fileHandleForReading.readabilityHandler = nil
        errorPipe?.fileHandleForReading.readabilityHandler = nil
        self.process = nil
        self.outputPipe = nil
        self.errorPipe = nil
    }

    func restart() {
        stop()
        Task {
            try? await Task.sleep(for: .seconds(1))
            start()
        }
    }

    // MARK: - Port Management

    /// Kill any process currently listening on the given TCP port.
    /// Uses `lsof` to find the PID, then sends SIGTERM followed by SIGKILL if needed.
    private static func killProcessOnPort(_ port: UInt16) {
        // Use lsof to find PIDs listening on the port
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
            return
        }

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
              !output.isEmpty else {
            return
        }

        // Parse PIDs (one per line) and kill each
        let myPID = ProcessInfo.processInfo.processIdentifier
        let pids = output.split(separator: "\n").compactMap { Int32($0.trimmingCharacters(in: .whitespaces)) }

        for pid in pids where pid != myPID {
            print("[PythonBridge] Killing orphaned process on port \(port): PID \(pid)")
            kill(pid, SIGTERM)
        }

        // Brief wait, then force-kill any survivors
        if !pids.isEmpty {
            usleep(500_000) // 500ms
            for pid in pids where pid != myPID {
                // Check if still alive (kill with signal 0 tests existence)
                if kill(pid, 0) == 0 {
                    print("[PythonBridge] Force-killing PID \(pid)")
                    kill(pid, SIGKILL)
                }
            }
        }
    }

    // MARK: - Path Resolution

    /// Find the local pyax source directory (packages/pyax/src) for development.
    private static func findPyaxSrcPath() -> String {
        // Walk up from executable to find the monorepo root
        let executablePath = Bundle.main.executablePath ?? ""
        var dir = (executablePath as NSString).deletingLastPathComponent

        for _ in 0..<15 {
            let candidate = (dir as NSString).appendingPathComponent("packages/pyax/src")
            if FileManager.default.fileExists(atPath: candidate) {
                return candidate
            }
            dir = (dir as NSString).deletingLastPathComponent
        }

        // Fallback: common development path
        let devPath = "\(NSHomeDirectory())/Desktop/pyax-better/packages/pyax/src"
        if FileManager.default.fileExists(atPath: devPath) {
            return devPath
        }

        return ""
    }

    /// Find Python 3 executable on the system.
    private static func findPython3() -> String {
        let candidates = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
            "\(NSHomeDirectory())/.pyenv/shims/python3",
        ]

        for candidate in candidates {
            if FileManager.default.isExecutableFile(atPath: candidate) {
                return candidate
            }
        }

        return "/usr/bin/python3"
    }
}
