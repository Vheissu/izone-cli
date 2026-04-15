import Foundation

struct SystemControlDraft {
    var isPoweredOn: Bool
    var mode: SystemMode
    var fan: FanSpeed
    var setpointCelsius: Double
}

struct ZoneUpdateDraft {
    var mode: ZoneMode
    var setpointCelsius: Double
    var maxAir: Int
    var minAir: Int
}
