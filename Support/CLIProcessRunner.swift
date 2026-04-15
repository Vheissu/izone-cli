import Foundation

struct CLICommandResult {
    let standardOutput: String
    let standardError: String
    let exitCode: Int32
}

actor CLIProcessRunner {
    func run(
        executableURL: URL,
        arguments: [String],
        currentDirectoryURL: URL
    ) async throws -> CLICommandResult {
        try await Task.detached(priority: .userInitiated) {
            let process = Process()
            let stdoutPipe = Pipe()
            let stderrPipe = Pipe()

            process.executableURL = executableURL
            process.arguments = arguments
            process.currentDirectoryURL = currentDirectoryURL
            process.standardOutput = stdoutPipe
            process.standardError = stderrPipe

            var environment = ProcessInfo.processInfo.environment
            let preferredPathComponents = [
                "/opt/homebrew/opt/python@3.11/libexec/bin",
                "/opt/homebrew/bin",
                "/usr/local/bin",
                "/usr/bin",
                "/bin",
                "/usr/sbin",
                "/sbin",
            ]
            let existingPathComponents = (environment["PATH"] ?? "")
                .split(separator: ":")
                .map(String.init)
            let mergedPathComponents = preferredPathComponents + existingPathComponents.filter { !preferredPathComponents.contains($0) }
            environment["PATH"] = mergedPathComponents.joined(separator: ":")
            environment["PYTHONUNBUFFERED"] = "1"
            process.environment = environment

            try process.run()
            let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
            let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()

            return CLICommandResult(
                standardOutput: String(decoding: stdoutData, as: UTF8.self),
                standardError: String(decoding: stderrData, as: UTF8.self),
                exitCode: process.terminationStatus
            )
        }.value
    }
}
