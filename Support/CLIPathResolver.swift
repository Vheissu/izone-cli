import Foundation

enum CLIPathResolver {
    static func resolveCLI() -> URL {
        firstExistingURL(from: cliCandidates()) ?? cliCandidates().first ?? URL(fileURLWithPath: "/Users/dwayne/Code/izone-cli/izone")
    }

    private static func cliCandidates() -> [URL] {
        var candidates: [URL] = []
        let fileManager = FileManager.default

        if let overridePath = ProcessInfo.processInfo.environment["IZONE_CLI_PATH"], !overridePath.isEmpty {
            candidates.append(URL(fileURLWithPath: overridePath))
        }

        let bundleRoot = Bundle.main.bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        candidates.append(bundleRoot.appending(path: "izone"))

        candidates.append(URL(fileURLWithPath: fileManager.currentDirectoryPath).appending(path: "izone"))
        candidates.append(URL(fileURLWithPath: "/Users/dwayne/Code/izone-cli/izone"))
        candidates.append(URL(fileURLWithPath: "/opt/homebrew/bin/izone"))
        candidates.append(URL(fileURLWithPath: "/usr/local/bin/izone"))
        candidates.append(contentsOf: pathBasedCandidates(named: "izone"))

        return candidates
    }

    private static func pathBasedCandidates(named executable: String) -> [URL] {
        let defaultPath = "/opt/homebrew/opt/python@3.11/libexec/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        let path = ProcessInfo.processInfo.environment["PATH"] ?? defaultPath
        return path
            .split(separator: ":")
            .map { URL(fileURLWithPath: String($0)).appending(path: executable) }
    }

    private static func firstExistingURL(from candidates: [URL]) -> URL? {
        let fileManager = FileManager.default
        return candidates.first { fileManager.isExecutableFile(atPath: $0.path) }
    }
}
