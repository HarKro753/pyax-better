import Foundation

/// Manages the pyax bridge and pyax-agent Python process lifecycles.
///
/// Launches both `python -m pyax.bridge` (WebSocket on port 8765) and
/// `python -m pyax_agent` (HTTP on port 8766) as child processes on startup.
@Observable
@MainActor
final class AgentProcessService {

    // MARK: - Private State

    private var _bridgeProcess: Process?
    private var _agentProcess: Process?
    private var _bridgePipes: (out: Pipe, err: Pipe)?
    private var _agentPipes: (out: Pipe, err: Pipe)?
    private var _isRunning = false
    private let _configuration: BridgeConfiguration
    private let _repoRoot: String

    // MARK: - Read Access

    var isRunning: Bool { _isRunning }

    // MARK: - Init

    init(configuration: BridgeConfiguration = .default) {
        self._configuration = configuration
        self._repoRoot = Self.findRepoRoot()
        print("[Startup] Repo root: \(_repoRoot)")
    }

    // MARK: - Lifecycle

    func start() {
        guard !_isRunning else {
            print("[Startup] Already running")
            return
        }

        startBridge()

        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { [weak self] in
            self?.startAgent()
            self?._isRunning = true
        }
    }

    func stop() {
        print("[Startup] Stopping all processes...")
        stopProcess(_agentProcess, label: "pyax-agent")
        stopProcess(_bridgeProcess, label: "pyax-bridge")
        cleanupPipes(_agentPipes)
        cleanupPipes(_bridgePipes)
        _agentProcess = nil
        _bridgeProcess = nil
        _agentPipes = nil
        _bridgePipes = nil
        _isRunning = false
    }

    // MARK: - Bridge

    private func startBridge() {
        killExistingProcess(port: 8765, label: "bridge")

        let pythonPath = findPython(venvSubpath: "packages/pyax-agent/.venv/bin/python")
        let pyaxSrc = _repoRoot + "/packages/pyax/src"

        print("[pyax-bridge] Starting with Python: \(pythonPath)")

        let process = Process()
        let pipes = makePipes(label: "pyax-bridge")

        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = ["-m", "pyax.bridge"]
        process.standardOutput = pipes.out
        process.standardError = pipes.err

        var env = ProcessInfo.processInfo.environment
        var pythonPaths = [pyaxSrc]
        if let existing = env["PYTHONPATH"] { pythonPaths.append(existing) }
        env["PYTHONPATH"] = pythonPaths.joined(separator: ":")
        process.environment = env

        process.terminationHandler = { proc in
            Task { @MainActor in
                print("[pyax-bridge] Exited (code \(proc.terminationStatus))")
            }
        }

        do {
            try process.run()
            _bridgeProcess = process
            _bridgePipes = pipes
            print("[pyax-bridge] Started (PID \(process.processIdentifier))")
        } catch {
            print("[pyax-bridge] ERROR: Failed to start: \(error.localizedDescription)")
        }
    }

    // MARK: - Agent

    private func startAgent() {
        killExistingProcess(port: _configuration.agentPort, label: "agent")

        let pythonPath = findPython(venvSubpath: "packages/pyax-agent/.venv/bin/python")
        let agentSrc = _repoRoot + "/packages/pyax-agent/src"
        let pyaxSrc = _repoRoot + "/packages/pyax/src"

        print("[pyax-agent] Starting with Python: \(pythonPath)")

        let process = Process()
        let pipes = makePipes(label: "pyax-agent")

        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = ["-m", "pyax_agent"]
        process.standardOutput = pipes.out
        process.standardError = pipes.err

        var env = ProcessInfo.processInfo.environment
        var pythonPaths = [agentSrc, pyaxSrc]
        if let existing = env["PYTHONPATH"] { pythonPaths.append(existing) }
        env["PYTHONPATH"] = pythonPaths.joined(separator: ":")
        process.environment = env

        process.terminationHandler = { proc in
            Task { @MainActor in
                print("[pyax-agent] Exited (code \(proc.terminationStatus))")
            }
        }

        do {
            try process.run()
            _agentProcess = process
            _agentPipes = pipes
            print("[pyax-agent] Started (PID \(process.processIdentifier))")
        } catch {
            print("[pyax-agent] ERROR: Failed to start: \(error.localizedDescription)")
        }
    }

    // MARK: - Helpers

    private func makePipes(label: String) -> (out: Pipe, err: Pipe) {
        let outPipe = Pipe()
        let errPipe = Pipe()

        outPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty, let text = String(data: data, encoding: .utf8) {
                for line in text.split(separator: "\n", omittingEmptySubsequences: false) {
                    let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty {
                        print("[\(label)] \(trimmed)")
                    }
                }
            }
        }

        errPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if !data.isEmpty, let text = String(data: data, encoding: .utf8) {
                for line in text.split(separator: "\n", omittingEmptySubsequences: false) {
                    let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty {
                        print("[\(label)] \(trimmed)")
                    }
                }
            }
        }

        return (outPipe, errPipe)
    }

    private func stopProcess(_ process: Process?, label: String) {
        guard let process, process.isRunning else { return }
        print("[\(label)] Stopping (PID \(process.processIdentifier))...")
        process.terminate()

        let capturedProcess = process
        DispatchQueue.global().async {
            for _ in 0..<20 {
                if !capturedProcess.isRunning { return }
                usleep(100_000)
            }
            if capturedProcess.isRunning {
                capturedProcess.interrupt()
                usleep(500_000)
                if capturedProcess.isRunning {
                    kill(capturedProcess.processIdentifier, SIGKILL)
                }
            }
        }
    }

    private func cleanupPipes(_ pipes: (out: Pipe, err: Pipe)?) {
        pipes?.out.fileHandleForReading.readabilityHandler = nil
        pipes?.err.fileHandleForReading.readabilityHandler = nil
    }

    private func killExistingProcess(port: UInt16, label: String) {
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
            print("[Startup] Killing existing \(label) on port \(port): PID \(pid)")
            kill(pid, SIGTERM)
        }
        usleep(500_000)
    }

    private func findPython(venvSubpath: String) -> String {
        let venvPath = _repoRoot + "/" + venvSubpath
        if FileManager.default.isExecutableFile(atPath: venvPath) {
            return venvPath
        }

        let candidates = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
        ]
        for candidate in candidates {
            if FileManager.default.isExecutableFile(atPath: candidate) {
                return candidate
            }
        }
        return "/usr/bin/python3"
    }

    // MARK: - Path Resolution

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
