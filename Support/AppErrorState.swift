import Foundation

struct AppErrorState: Equatable {
    let title: String
    let message: String
    let details: String?

    static func from(_ error: Error) -> AppErrorState {
        if let cliError = error as? IZoneCLIError {
            return from(cliError)
        }

        if let localized = error as? LocalizedError, let description = localized.errorDescription {
            return AppErrorState(title: "Something Went Wrong", message: description, details: nil)
        }

        return AppErrorState(title: "Something Went Wrong", message: error.localizedDescription, details: nil)
    }

    private static func from(_ error: IZoneCLIError) -> AppErrorState {
        switch error {
        case let .executableNotFound(path):
            return AppErrorState(
                title: "iZone CLI Not Found",
                message: "The desktop app couldn't find the `izone` script it needs to run.",
                details: path
            )
        case let .commandFailed(_, _, message):
            return summarizeCommandFailure(details: message)
        case .invalidJSONOutput:
            return AppErrorState(
                title: "Unexpected iZone Response",
                message: "The CLI returned data the desktop app couldn't parse.",
                details: nil
            )
        }
    }

    private static func summarizeCommandFailure(details: String) -> AppErrorState {
        let trimmed = details.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowercase = trimmed.lowercased()

        if lowercase.contains("no route to host")
            || lowercase.contains("timed out")
            || lowercase.contains("connection refused")
            || lowercase.contains("network is unreachable") {
            return AppErrorState(
                title: "Can't Reach the iZone Bridge",
                message: "The app couldn't connect to the bridge on your local network. If the bridge IP changed, set it in Settings or reconnect to the same LAN as the aircon bridge.",
                details: trimmed
            )
        }

        if lowercase.contains("no izone bridge found on the network") {
            return AppErrorState(
                title: "No iZone Bridge Found",
                message: "Auto-discovery didn't find a bridge on the current network. If discovery is unreliable on your setup, enter the bridge IP in Settings.",
                details: trimmed
            )
        }

        if lowercase.contains("bridge returned non-json response") {
            return AppErrorState(
                title: "Bridge Returned an Invalid Response",
                message: "The bridge answered, but not with the JSON payload the CLI expected. Try refreshing again in a few seconds.",
                details: trimmed
            )
        }

        let lastLine = trimmed
            .split(whereSeparator: \.isNewline)
            .map(String.init)
            .last(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty }) ?? trimmed

        return AppErrorState(
            title: "iZone Command Failed",
            message: lastLine,
            details: trimmed == lastLine ? nil : trimmed
        )
    }
}
