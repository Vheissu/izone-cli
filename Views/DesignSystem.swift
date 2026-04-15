import SwiftUI

// MARK: - App Color Palette

enum AppColors {
    static let bgBase     = Color(red: 0.075, green: 0.082, blue: 0.110)
    static let bgSurface  = Color(red: 0.110, green: 0.122, blue: 0.161)
    static let bgElevated = Color(red: 0.153, green: 0.167, blue: 0.212)
    static let bgHover    = Color(red: 0.184, green: 0.200, blue: 0.251)
    static let borderSubtle = Color.white.opacity(0.05)
}

// MARK: - Mode & Zone Tint Colors

extension SystemMode {
    var tintColor: Color {
        switch self {
        case .cool: .cyan
        case .heat: .orange
        case .vent: .teal
        case .dry: .yellow
        case .auto: .purple
        }
    }
}

extension ZoneMode {
    var tintColor: Color {
        switch self {
        case .open: .green
        case .close: .secondary
        case .auto: .blue
        case .overrideMode: .orange
        case .constant: .purple
        }
    }
}

extension FanSpeed {
    var systemImage: String {
        switch self {
        case .low: "fan.floor"
        case .medium: "fan"
        case .high: "fan.fill"
        case .auto: "fan.badge.automatic"
        case .top: "fan.ceiling.fill"
        }
    }
}

// MARK: - Status Badge

struct StatusBadge: View {
    let text: String
    let icon: String
    let color: Color

    var body: some View {
        Label(text, systemImage: icon)
            .font(.caption.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(
                Capsule(style: .continuous)
                    .fill(color.opacity(0.12))
            )
    }
}

// MARK: - App Icon

struct AppIconView: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 120, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 0.08, green: 0.18, blue: 0.33),
                            Color(red: 0.03, green: 0.06, blue: 0.12),
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )

            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            Color(red: 0.25, green: 0.78, blue: 0.85).opacity(0.14),
                            .clear,
                        ],
                        center: .center,
                        startRadius: 50,
                        endRadius: 230
                    )
                )

            Image(systemName: "snowflake")
                .font(.system(size: 200, weight: .ultraLight))
                .foregroundStyle(
                    LinearGradient(
                        colors: [
                            Color(red: 0.50, green: 0.96, blue: 0.92),
                            Color(red: 0.22, green: 0.70, blue: 0.88),
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .shadow(color: Color(red: 0.30, green: 0.85, blue: 0.80).opacity(0.35), radius: 30)
        }
        .frame(width: 512, height: 512)
    }
}
