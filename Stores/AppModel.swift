import Foundation
import Observation

@MainActor
@Observable
final class AppModel {
    var selection: SidebarSection? = .overview
    var snapshot: IZoneSnapshot?
    var profiles: [StoredProfile] = []
    var savedDefaults: SavedDefaults?
    var isLoading = false
    var isRunningCommand = false
    var errorState: AppErrorState?
    var lastUpdated: Date?
    var bridgeIPOverride: String {
        didSet {
            UserDefaults.standard.set(bridgeIPOverride, forKey: Self.bridgeIPOverrideKey)
        }
    }

    private let client = IZoneCLIClient()
    private var hasLoaded = false

    static let bridgeIPOverrideKey = "bridgeIPOverride"

    init() {
        bridgeIPOverride = UserDefaults.standard.string(forKey: Self.bridgeIPOverrideKey) ?? ""
    }

    var isBusy: Bool {
        isLoading || isRunningCommand
    }

    var resolvedCLIPath: String {
        client.cliScriptURL.path
    }

    var lastUpdatedLabel: String {
        formattedTimestamp(lastUpdated)
    }

    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        hasLoaded = true
        await reloadAll()
    }

    func reloadAll(force: Bool = false) async {
        if isLoading && !force {
            return
        }

        isLoading = true
        defer { isLoading = false }

        loadLocalData()

        do {
            snapshot = try await client.fetchStatus(ipOverride: normalizedBridgeIPOverride())
            errorState = nil
            lastUpdated = Date()
        } catch {
            errorState = AppErrorState.from(error)
        }
    }

    func applySystem(_ draft: SystemControlDraft) async {
        await runCommand(refreshLocalData: false) {
            try await client.applySystem(draft, ipOverride: normalizedBridgeIPOverride())
        }
    }

    func applyZone(_ draft: ZoneUpdateDraft, for index: Int) async {
        await runCommand(refreshLocalData: false) {
            try await client.applyZone(index: index, draft: draft, ipOverride: normalizedBridgeIPOverride())
        }
    }

    func saveDefaults() async {
        await runCommand {
            try await client.saveDefaults(ipOverride: normalizedBridgeIPOverride())
        }
    }

    func restoreDefaults() async {
        await runCommand {
            try await client.restoreDefaults(ipOverride: normalizedBridgeIPOverride())
        }
    }

    func saveCurrentProfile(named name: String) async {
        await runCommand {
            try await client.saveCurrentProfile(named: name, ipOverride: normalizedBridgeIPOverride())
        }
    }

    func applyProfile(named name: String) async {
        await runCommand {
            try await client.applyProfile(named: name, ipOverride: normalizedBridgeIPOverride())
        }
    }

    func deleteProfile(named name: String) async {
        await runCommand {
            try await client.deleteProfile(named: name, ipOverride: normalizedBridgeIPOverride())
        }
    }

    func clearBridgeIPOverride() {
        bridgeIPOverride = ""
    }

    private func runCommand(
        refreshLocalData: Bool = true,
        action: () async throws -> Void
    ) async {
        guard !isRunningCommand else { return }

        isRunningCommand = true
        errorState = nil
        defer { isRunningCommand = false }

        do {
            try await action()
            do {
                snapshot = try await client.fetchStatus(ipOverride: normalizedBridgeIPOverride())
                lastUpdated = Date()
            } catch {
                let refreshError = AppErrorState.from(error)
                errorState = AppErrorState(
                    title: "Command Applied, Refresh Failed",
                    message: refreshError.message,
                    details: refreshError.details
                )
            }

            if refreshLocalData {
                loadLocalData()
            }
        } catch {
            errorState = AppErrorState.from(error)
        }
    }

    private func loadLocalData() {
        do {
            profiles = try client.loadProfiles()
            savedDefaults = try client.loadDefaults()
        } catch {
            errorState = AppErrorState.from(error)
        }
    }

    private func normalizedBridgeIPOverride() -> String? {
        let trimmed = bridgeIPOverride.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
