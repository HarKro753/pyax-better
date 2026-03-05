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

    func start() {
        guard status == .stopped || {
            if case .error = status { return true }
            return false
        }() else { return }

        status = .starting

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
        // Give it a moment to clean up, then force kill if needed
        DispatchQueue.global().asyncAfter(deadline: .now() + 2.0) { [weak self] in
            if process.isRunning {
                process.interrupt()
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
