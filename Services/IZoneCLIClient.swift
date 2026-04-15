import Foundation

enum IZoneCLIError: LocalizedError {
    case executableNotFound(path: String)
    case commandFailed(arguments: [String], exitCode: Int32, message: String)
    case invalidJSONOutput

    var errorDescription: String? {
        switch self {
        case let .executableNotFound(path):
            return "The iZone backend executable could not be found at \(path)."
        case let .commandFailed(arguments, exitCode, message):
            let joined = arguments.joined(separator: " ")
            let detail = message.isEmpty ? "The command returned no output." : message
            return "`izone \(joined)` failed with exit code \(exitCode). \(detail)"
        case .invalidJSONOutput:
            return "The iZone CLI returned data that the desktop app could not parse."
        }
    }
}

@MainActor
final class IZoneCLIClient {
    let cliScriptURL: URL

    private let runner = CLIProcessRunner()
    private let decoder = JSONDecoder()
    private let fileManager = FileManager.default

    init() {
        cliScriptURL = CLIPathResolver.resolveCLI()
    }

    func fetchStatus(ipOverride: String?) async throws -> IZoneSnapshot {
        let output = try await run(arguments: ["json"], ipOverride: ipOverride)
        guard let data = output.data(using: .utf8) else {
            throw IZoneCLIError.invalidJSONOutput
        }
        let payload = try decoder.decode(RawStatusPayload.self, from: data)
        return IZoneSnapshot(payload: payload)
    }

    func applySystem(_ draft: SystemControlDraft, ipOverride: String?) async throws {
        if draft.isPoweredOn {
            _ = try await run(arguments: ["on"], ipOverride: ipOverride)
        }
        _ = try await run(arguments: ["mode", draft.mode.cliValue], ipOverride: ipOverride)
        _ = try await run(arguments: ["fan", draft.fan.cliValue], ipOverride: ipOverride)
        _ = try await run(arguments: ["temp", String(format: "%.1f", quantizeHalfDegree(draft.setpointCelsius))], ipOverride: ipOverride)
        if !draft.isPoweredOn {
            _ = try await run(arguments: ["off"], ipOverride: ipOverride)
        }
    }

    func applyZone(index: Int, draft: ZoneUpdateDraft, ipOverride: String?) async throws {
        let arguments = [
            "zone",
            String(index),
            "--mode",
            draft.mode.cliValue,
            "--temp",
            String(format: "%.1f", quantizeHalfDegree(draft.setpointCelsius)),
            "--max-air",
            String(quantizeAirflow(draft.maxAir)),
            "--min-air",
            String(quantizeAirflow(draft.minAir)),
        ]
        _ = try await run(arguments: arguments, ipOverride: ipOverride)
    }

    func saveDefaults(ipOverride: String?) async throws {
        _ = try await run(arguments: ["defaults", "save"], ipOverride: ipOverride)
    }

    func restoreDefaults(ipOverride: String?) async throws {
        _ = try await run(arguments: ["defaults", "restore"], ipOverride: ipOverride)
    }

    func saveCurrentProfile(named name: String, ipOverride: String?) async throws {
        _ = try await run(arguments: ["profile", "save", name], ipOverride: ipOverride)
    }

    func applyProfile(named name: String, ipOverride: String?) async throws {
        _ = try await run(arguments: ["profile", "apply", name], ipOverride: ipOverride)
    }

    func deleteProfile(named name: String, ipOverride: String?) async throws {
        _ = try await run(arguments: ["profile", "delete", name], ipOverride: ipOverride)
    }

    func loadProfiles() throws -> [StoredProfile] {
        let url = configFileURL(named: "profiles.json")
        guard fileManager.fileExists(atPath: url.path) else { return [] }

        let data = try Data(contentsOf: url)
        let payload = try decoder.decode([String: StoredProfilePayload].self, from: data)
        return payload
            .map { name, profile in
                StoredProfile(
                    name: name,
                    modeName: profile.mode,
                    fanName: profile.fan,
                    temp: profile.temp,
                    closeOthers: profile.closeOthers ?? true,
                    zones: profile.zones ?? [:]
                )
            }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    func loadDefaults() throws -> SavedDefaults? {
        let url = configFileURL(named: "defaults.json")
        guard fileManager.fileExists(atPath: url.path) else { return nil }
        let data = try Data(contentsOf: url)
        return try decoder.decode(SavedDefaults.self, from: data)
    }

    private func run(arguments: [String], ipOverride: String?) async throws -> String {
        guard fileManager.isExecutableFile(atPath: cliScriptURL.path) else {
            throw IZoneCLIError.executableNotFound(path: cliScriptURL.path)
        }

        let fullArguments = baseArguments(ipOverride: ipOverride) + arguments
        let result = try await runner.run(
            executableURL: cliScriptURL,
            arguments: fullArguments,
            currentDirectoryURL: cliScriptURL.deletingLastPathComponent()
        )

        guard result.exitCode == 0 else {
            let message = [result.standardError, result.standardOutput]
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .first(where: { !$0.isEmpty }) ?? ""
            throw IZoneCLIError.commandFailed(arguments: fullArguments, exitCode: result.exitCode, message: message)
        }

        return result.standardOutput.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func baseArguments(ipOverride: String?) -> [String] {
        guard let ipOverride, !ipOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return []
        }
        return ["--ip", ipOverride.trimmingCharacters(in: .whitespacesAndNewlines)]
    }

    private func configFileURL(named name: String) -> URL {
        fileManager.homeDirectoryForCurrentUser
            .appending(path: ".config")
            .appending(path: "izone")
            .appending(path: name)
    }
}
