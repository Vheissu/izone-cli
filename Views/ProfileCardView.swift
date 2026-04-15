import SwiftUI

struct ProfileCardView: View {
    let profile: StoredProfile
    let isBusy: Bool
    let onApply: () -> Void
    let onDelete: () -> Void

    @State private var isHovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 14) {
                // Profile icon
                Image(systemName: "bookmark.fill")
                    .font(.title3)
                    .foregroundStyle(profile.mode?.tintColor ?? .accentColor)
                    .frame(width: 38, height: 38)
                    .background(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill((profile.mode?.tintColor ?? .accentColor).opacity(0.12))
                    )

                VStack(alignment: .leading, spacing: 8) {
                    Text(profile.name)
                        .font(.headline)

                    HStack(spacing: 6) {
                        if let mode = profile.mode {
                            StatusBadge(text: mode.displayName, icon: mode.systemImage, color: mode.tintColor)
                        }
                        if let fan = profile.fan {
                            StatusBadge(text: fan.displayName, icon: "fan", color: .secondary)
                        }
                        if let temp = profile.temp {
                            StatusBadge(text: formatTemperature(temp), icon: "thermometer", color: .secondary)
                        }
                        StatusBadge(
                            text: "\(profile.zoneCount) zone\(profile.zoneCount == 1 ? "" : "s")",
                            icon: "square.grid.2x2",
                            color: .secondary
                        )
                        if profile.closeOthers {
                            StatusBadge(text: "Closes others", icon: "xmark.circle", color: .orange)
                        }
                    }
                }

                Spacer()

                HStack(spacing: 8) {
                    Button("Apply", action: onApply)
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                        .disabled(isBusy)

                    Button(action: onDelete) {
                        Image(systemName: "trash")
                            .foregroundStyle(.red.opacity(0.7))
                    }
                    .buttonStyle(.borderless)
                    .disabled(isBusy)
                    .help("Delete profile")
                }
            }

            if !profile.zones.isEmpty {
                Divider().opacity(0.3)

                Text(zoneSummary)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .lineLimit(2)
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(isHovered ? AppColors.bgElevated : AppColors.bgSurface)
        )
        .animation(.easeInOut(duration: 0.15), value: isHovered)
        .onHover { isHovered = $0 }
    }

    private var zoneSummary: String {
        profile.zones
            .sorted { Int($0.key) ?? 0 < Int($1.key) ?? 0 }
            .map { key, zone in
                let mode = zone.zoneMode?.displayName ?? "\(zone.mode)"
                return "Zone \(key): \(mode) at \(formatTemperature(zone.temp))"
            }
            .joined(separator: " \u{2022} ")
    }
}
