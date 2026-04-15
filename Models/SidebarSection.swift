import Foundation

enum SidebarSection: String, CaseIterable, Identifiable {
    case overview
    case zones
    case profiles

    var id: String { rawValue }

    var title: String {
        switch self {
        case .overview: "Overview"
        case .zones: "Zones"
        case .profiles: "Profiles"
        }
    }

    var systemImage: String {
        switch self {
        case .overview: "gauge.with.dots.needle.67percent"
        case .zones: "square.grid.2x2"
        case .profiles: "bookmark"
        }
    }
}
