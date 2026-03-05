import Foundation

@Observable
@MainActor
final class PythonBridgeService {

    // MARK: - Private State

    private var _status: BridgeStatus = .stopped
    private var _process: Process?
    private var _outputPipe: Pipe?
    private var _errorPipe: Pipe?
    private let _pythonPath: String
    private let _portManager: PortManager
    private let _configuration: BridgeConfiguration

    // MARK: - Read Access

    var status: BridgeStatus { _status }

    // MARK: - Init

    init(
        portManager: PortManager = PortManager(),
        configuration: BridgeConfiguration = .default
    ) {
        self._portManager = portManager
        self._configuration = configuration
        self._pythonPath = Self.findPython3()
    }

    // MARK: - Lifecycle

    func start() {
        guard _status.canStart else { return }

        _status = .starting
        _portManager.killProcessOnPort(_configuration.port)

        let process = Process()
        let outputPipe = Pipe()
        let errorPipe = Pipe()

        process.executableURL = URL(fileURLWithPath: _pythonPath)
        process.arguments = ["-m", "pyax.bridge"]
        process.standardOutput = outputPipe
        process.standardError = errorPipe
        process.environment = buildEnvironment()

        outputPipe.fileHandleForReading.readabilityHandler = { handle in
            _ = handle.availableData
        }
        errorPipe.fileHandleForReading.readabilityHandler = { handle in
            _ = handle.availableData
        }

        process.terminationHandler = { [weak self] terminatedProcess in
            Task { @MainActor in
                guard let self else { return }
                if terminatedProcess.terminationStatus != 0 {
                    self._status = .error("Process exited with code \(terminatedProcess.terminationStatus)")
                } else {
                    self._status = .stopped
                }
            }
        }

        do {
            try process.run()
            self._process = process
            self._outputPipe = outputPipe
            self._errorPipe = errorPipe
            _status = .running
        } catch {
            _status = .error("Failed to start: \(error.localizedDescription)")
        }
    }

    func stop() {
        guard let process = _process, process.isRunning else {
            _status = .stopped
            return
        }

        process.terminate()
        cleanupPipes()

        let capturedProcess = process
        let shutdownTimeout = _configuration.gracefulShutdownTimeout

        DispatchQueue.global().async { [weak self] in
            let intervals = Int(shutdownTimeout.components.seconds * 10)
            for _ in 0..<intervals {
                if !capturedProcess.isRunning { break }
                usleep(100_000)
            }
            if capturedProcess.isRunning {
                capturedProcess.interrupt()
                usleep(500_000)
                if capturedProcess.isRunning {
                    kill(capturedProcess.processIdentifier, SIGKILL)
                }
            }
            Task { @MainActor in
                self?._status = .stopped
            }
        }

        _process = nil
    }

    func restart() {
        stop()
        Task {
            try? await Task.sleep(for: .seconds(1))
            start()
        }
    }

    // MARK: - Private — Pipe Cleanup

    private func cleanupPipes() {
        _outputPipe?.fileHandleForReading.readabilityHandler = nil
        _errorPipe?.fileHandleForReading.readabilityHandler = nil
        _outputPipe = nil
        _errorPipe = nil
    }

    // MARK: - Private — Python Path Resolution

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

    private static func findPyaxSourcePath() -> String {
        let executablePath = Bundle.main.executablePath ?? ""
        var directory = (executablePath as NSString).deletingLastPathComponent

        for _ in 0..<15 {
            let candidate = (directory as NSString).appendingPathComponent("packages/pyax/src")
            if FileManager.default.fileExists(atPath: candidate) {
                return candidate
            }
            directory = (directory as NSString).deletingLastPathComponent
        }

        let developmentPath = "\(NSHomeDirectory())/Desktop/pyax-better/packages/pyax/src"
        if FileManager.default.fileExists(atPath: developmentPath) {
            return developmentPath
        }

        return ""
    }

    private func buildEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        let pyaxSourcePath = Self.findPyaxSourcePath()
        let userSitePackages = "\(NSHomeDirectory())/Library/Python/3.9/lib/python/site-packages"
        var pythonPaths = [pyaxSourcePath, userSitePackages]
        if let existing = env["PYTHONPATH"] {
            pythonPaths.append(existing)
        }
        env["PYTHONPATH"] = pythonPaths.joined(separator: ":")
        return env
    }
}
