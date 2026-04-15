import Foundation

struct StoredProfile: Identifiable, Equatable {
    let name: String
    let modeName: String?
    let fanName: String?
    let temp: Int?
    let closeOthers: Bool
    let zones: [String: StoredProfileZone]

    var id: String { name }
    var zoneCount: Int { zones.count }
    var mode: SystemMode? { modeName.flatMap(SystemMode.init(cliValue:)) }
    var fan: FanSpeed? { fanName.flatMap(FanSpeed.init(cliValue:)) }
}

struct StoredProfileZone: Decodable, Equatable {
    let mode: Int
    let temp: Int

    var zoneMode: ZoneMode? { ZoneMode(rawValue: mode) }
}

struct SavedDefaults: Decodable, Equatable {
    let mode: Int
    let fan: Int
    let setpoint: Int
    let zones: [SavedDefaultZone]

    var modeLabel: String { SystemMode(rawValue: mode)?.displayName ?? "\(mode)" }
    var fanLabel: String { FanSpeed(rawValue: fan)?.displayName ?? "\(fan)" }
}

struct SavedDefaultZone: Decodable, Equatable, Identifiable {
    let index: Int
    let name: String
    let mode: Int
    let setpoint: Int
    let maxAir: Int
    let minAir: Int

    var id: Int { index }
    var zoneMode: ZoneMode? { ZoneMode(rawValue: mode) }

    enum CodingKeys: String, CodingKey {
        case index
        case name
        case mode
        case setpoint
        case maxAir = "max_air"
        case minAir = "min_air"
    }
}

struct StoredProfilePayload: Decodable {
    let mode: String?
    let fan: String?
    let temp: Int?
    let closeOthers: Bool?
    let zones: [String: StoredProfileZone]?

    enum CodingKeys: String, CodingKey {
        case mode
        case fan
        case temp
        case closeOthers = "close_others"
        case zones
    }
}
