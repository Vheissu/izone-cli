import SwiftUI

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

// MARK: - Section Header

struct SectionHeader: View {
    let title: String
    let icon: String?

    init(_ title: String, icon: String? = nil) {
        self.title = title
        self.icon = icon
    }

    var body: some View {
        HStack(spacing: 7) {
            if let icon {
                Image(systemName: icon)
                    .foregroundStyle(.secondary)
                    .font(.subheadline)
            }
            Text(title)
                .font(.title3.weight(.semibold))
        }
    }
}

// MARK: - Small Metric (for environment sensors)

struct SmallMetricView: View {
    let label: String
    let value: String
    let icon: String
    let tint: Color

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.callout)
                .foregroundStyle(tint)
                .frame(width: 28, height: 28)
                .background(
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .fill(tint.opacity(0.1))
                )

            VStack(alignment: .leading, spacing: 1) {
                Text(value)
                    .font(.callout.weight(.semibold))
                    .monospacedDigit()
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer(minLength: 0)
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(.thickMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .strokeBorder(.white.opacity(0.04))
        )
    }
}
