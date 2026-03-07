import Foundation

/// Manages the pyax-agent Python process lifecycle.
///
/// Launches `python -m pyax_agent` as a child process on startup,
/// monitors its health, and restarts if needed.
@Observable
@MainActor
final class AgentProcessService {

    // MARK: - Private State

    private var _process: Process?
    private var _outputPipe: Pipe?
    private var _errorPipe: Pipe?
    private var _isRunning = false
    private let _configuration: BridgeConfiguration
    private let _pythonPath: String
    private let _agentSourcePath: String

    // MARK: - Read Access

    var isRunning: Bool { _isRunning }

    // MARK: - Init

    init(configuration: BridgeConfiguration = .default) {
        self._configuration = configuration
        self._pythonPath = Self.findAgentPython()
        self._agentSourcePath = Self.findAgentSourcePath()
        print("[AgentProcess] Python: \(_pythonPath)")
        print("[AgentProcess] Agent source: \(_agentSourcePath)")
    }

    // MARK: - Lifecycle

    func start() {
        guard !_isRunning else {
            print("[AgentProcess] Already running")
            return
        }

        killExistingProcess(port: _configuration.agentPort)

        let process = Process()
        let outputPipe = Pipe()
        let errorPipe = Pipe()

        process.executableURL = URL(fileURLWithPath: _pythonPath)
        process.arguments = ["-m", "pyax_agent"]
        process.standardOutput = outputPipe
        process.standardError = errorPipe
        process.environment = buildEnvironment()

        outputPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty, let text = String(data: data, encoding: .utf8) {
                for line in text.split(separator: "\n") {
                    print("[pyax-agent] \(line)")
                }
            }
        }

        errorPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty, let text = String(data: data, encoding: .utf8) {
                for line in text.split(separator: "\n") {
                    print("[pyax-agent] \(line)")
                }
            }
        }

        process.terminationHandler = { [weak self] terminatedProcess in
            Task { @MainActor in
                guard let self else { return }
                self._isRunning = false
                if terminatedProcess.terminationStatus != 0 {
                    print("[AgentProcess] Exited with code \(terminatedProcess.terminationStatus)")
                } else {
                    print("[AgentProcess] Stopped")
                }
            }
        }

        do {
            try process.run()
            self._process = process
            self._outputPipe = outputPipe
            self._errorPipe = errorPipe
            _isRunning = true
            print("[AgentProcess] Started (PID \(process.processIdentifier))")
        } catch {
            print("[AgentProcess] ERROR: Failed to start: \(error.localizedDescription)")
        }
    }

    func stop() {
        guard let process = _process, process.isRunning else {
            _isRunning = false
            return
        }

        print("[AgentProcess] Stopping...")
        process.terminate()
        cleanupPipes()

        let capturedProcess = process
        DispatchQueue.global().async {
            for _ in 0..<20 {
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
                print("[AgentProcess] Stopped")
            }
        }

        _process = nil
        _isRunning = false
    }

    // MARK: - Private

    private func cleanupPipes() {
        _outputPipe?.fileHandleForReading.readabilityHandler = nil
        _errorPipe?.fileHandleForReading.readabilityHandler = nil
        _outputPipe = nil
        _errorPipe = nil
    }

    private func killExistingProcess(port: UInt16) {
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
        guard let output = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              !output.isEmpty
        else { return }

        let myPID = ProcessInfo.processInfo.processIdentifier
        let pids = output.split(separator: "\n")
            .compactMap { Int32($0.trimmingCharacters(in: .whitespaces)) }

        for pid in pids where pid != myPID {
            print("[AgentProcess] Killing existing process on port \(port): PID \(pid)")
            kill(pid, SIGTERM)
        }
        usleep(500_000)
    }

    private func buildEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment

        if !_agentSourcePath.isEmpty {
            var pythonPaths = [_agentSourcePath]

            let pyaxSourcePath = Self.findPyaxSourcePath()
            if !pyaxSourcePath.isEmpty {
                pythonPaths.append(pyaxSourcePath)
            }

            if let existing = env["PYTHONPATH"] {
                pythonPaths.append(existing)
            }
            env["PYTHONPATH"] = pythonPaths.joined(separator: ":")
        }

        return env
    }

    // MARK: - Path Resolution

    private static func findAgentPython() -> String {
        let agentVenv = findRepoRoot() + "/packages/pyax-agent/.venv/bin/python"
        if FileManager.default.isExecutableFile(atPath: agentVenv) {
            return agentVenv
        }

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

    private static func findAgentSourcePath() -> String {
        let root = findRepoRoot()
        let candidate = root + "/packages/pyax-agent/src"
        if FileManager.default.fileExists(atPath: candidate) {
            return candidate
        }
        return ""
    }

    private static func findPyaxSourcePath() -> String {
        let root = findRepoRoot()
        let candidate = root + "/packages/pyax/src"
        if FileManager.default.fileExists(atPath: candidate) {
            return candidate
        }
        return ""
    }

    private static func findRepoRoot() -> String {
        let executablePath = Bundle.main.executablePath ?? ""
        var directory = (executablePath as NSString).deletingLastPathComponent

        for _ in 0..<15 {
            let marker = (directory as NSString).appendingPathComponent("packages/pyax-agent")
            if FileManager.default.fileExists(atPath: marker) {
                return directory
            }
            directory = (directory as NSString).deletingLastPathComponent
        }

        let devPath = "\(NSHomeDirectory())/Desktop/pyax-better"
        if FileManager.default.fileExists(atPath: devPath + "/packages/pyax-agent") {
            return devPath
        }

        return ""
    }
}
