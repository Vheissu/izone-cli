import Foundation

struct IZoneSnapshot: Equatable {
    let system: SystemSnapshot
    let zones: [ZoneSnapshot]

    init(payload: RawStatusPayload) {
        system = SystemSnapshot(
            isOn: payload.system.sysOn != 0,
            mode: SystemMode(rawValue: payload.system.sysMode),
            fan: FanSpeed(rawValue: payload.system.sysFan),
            setpoint: payload.system.setpoint,
            returnAir: payload.system.temp,
            supplyAir: payload.system.supply,
            humidity: payload.system.inRh,
            eco2: payload.system.inECO2,
            tvoc: payload.system.inTVOC,
            zoneCount: payload.system.noOfZones,
            sleepTimerMinutes: payload.system.sleepTimer.flatMap { $0 > 0 ? $0 : nil },
            warnings: payload.system.warnings.flatMap { $0 == "none" ? nil : $0 }
        )
        zones = payload.zones.enumerated().map { offset, zone in
            ZoneSnapshot(
                index: zone.index ?? offset,
                name: zone.name,
                temperature: zone.temp,
                setpoint: zone.setpoint,
                mode: ZoneMode(rawValue: zone.mode),
                maxAir: zone.maxAir,
                minAir: zone.minAir
            )
        }
    }
}

struct SystemSnapshot: Equatable {
    let isOn: Bool
    let mode: SystemMode?
    let fan: FanSpeed?
    let setpoint: Int
    let returnAir: Int
    let supplyAir: Int
    let humidity: Int?
    let eco2: Int?
    let tvoc: Int?
    let zoneCount: Int
    let sleepTimerMinutes: Int?
    let warnings: String?

    var setpointCelsius: Double { Double(setpoint) / 100 }
}

struct ZoneSnapshot: Identifiable, Equatable {
    let index: Int
    let name: String
    let temperature: Int
    let setpoint: Int
    let mode: ZoneMode?
    let maxAir: Int
    let minAir: Int

    var id: Int { index }
    var temperatureCelsius: Double { Double(temperature) / 100 }
    var setpointCelsius: Double { Double(setpoint) / 100 }
}

struct RawStatusPayload: Decodable {
    let system: RawSystemPayload
    let zones: [RawZonePayload]
}

struct RawSystemPayload: Decodable {
    let sysOn: Int
    let sysMode: Int
    let sysFan: Int
    let setpoint: Int
    let temp: Int
    let supply: Int
    let inRh: Int?
    let inECO2: Int?
    let inTVOC: Int?
    let noOfZones: Int
    let sleepTimer: Int?
    let warnings: String?

    enum CodingKeys: String, CodingKey {
        case sysOn = "SysOn"
        case sysMode = "SysMode"
        case sysFan = "SysFan"
        case setpoint = "Setpoint"
        case temp = "Temp"
        case supply = "Supply"
        case inRh = "InRh"
        case inECO2 = "IneCO2"
        case inTVOC = "InTVOC"
        case noOfZones = "NoOfZones"
        case sleepTimer = "SleepTimer"
        case warnings = "Warnings"
    }
}

struct RawZonePayload: Decodable {
    let index: Int?
    let name: String
    let temp: Int
    let setpoint: Int
    let mode: Int
    let maxAir: Int
    let minAir: Int

    enum CodingKeys: String, CodingKey {
        case index = "Index"
        case name = "Name"
        case temp = "Temp"
        case setpoint = "Setpoint"
        case mode = "Mode"
        case maxAir = "MaxAir"
        case minAir = "MinAir"
    }
}
