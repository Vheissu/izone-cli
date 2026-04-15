import Foundation

enum SystemMode: Int, CaseIterable, Codable, Identifiable {
    case cool = 1
    case heat = 2
    case vent = 3
    case dry = 4
    case auto = 5

    var id: Int { rawValue }

    var cliValue: String {
        switch self {
        case .cool: "cool"
        case .heat: "heat"
        case .vent: "vent"
        case .dry: "dry"
        case .auto: "auto"
        }
    }

    var displayName: String {
        switch self {
        case .cool: "Cool"
        case .heat: "Heat"
        case .vent: "Vent"
        case .dry: "Dry"
        case .auto: "Auto"
        }
    }

    var systemImage: String {
        switch self {
        case .cool: "snowflake"
        case .heat: "sun.max"
        case .vent: "wind"
        case .dry: "drop"
        case .auto: "dial.high"
        }
    }

    init?(cliValue: String) {
        switch cliValue.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
        case "cool": self = .cool
        case "heat": self = .heat
        case "vent": self = .vent
        case "dry": self = .dry
        case "auto": self = .auto
        default: return nil
        }
    }
}

enum FanSpeed: Int, CaseIterable, Codable, Identifiable {
    case low = 1
    case medium = 2
    case high = 3
    case auto = 4
    case top = 5

    var id: Int { rawValue }

    var cliValue: String {
        switch self {
        case .low: "low"
        case .medium: "medium"
        case .high: "high"
        case .auto: "auto"
        case .top: "top"
        }
    }

    var displayName: String {
        switch self {
        case .low: "Low"
        case .medium: "Medium"
        case .high: "High"
        case .auto: "Auto"
        case .top: "Top"
        }
    }

    init?(cliValue: String) {
        switch cliValue.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
        case "low": self = .low
        case "medium": self = .medium
        case "high": self = .high
        case "auto": self = .auto
        case "top": self = .top
        default: return nil
        }
    }
}

enum ZoneMode: Int, CaseIterable, Codable, Identifiable {
    case open = 1
    case close = 2
    case auto = 3
    case overrideMode = 4
    case constant = 5

    var id: Int { rawValue }

    var cliValue: String {
        switch self {
        case .open: "open"
        case .close: "close"
        case .auto: "auto"
        case .overrideMode: "override"
        case .constant: "constant"
        }
    }

    var displayName: String {
        switch self {
        case .open: "Open"
        case .close: "Closed"
        case .auto: "Auto"
        case .overrideMode: "Override"
        case .constant: "Constant"
        }
    }

    var systemImage: String {
        switch self {
        case .open: "door.left.hand.open"
        case .close: "xmark.circle"
        case .auto: "dial.medium"
        case .overrideMode: "hand.raised"
        case .constant: "equal.circle"
        }
    }
}
