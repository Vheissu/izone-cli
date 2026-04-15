import SwiftUI

struct ZoneCardView: View {
    let zone: ZoneSnapshot
    let isBusy: Bool
    let onApply: (ZoneUpdateDraft) -> Void

    @State private var draftMode: ZoneMode
    @State private var draftSetpoint: Double
    @State private var draftMaxAir: Int
    @State private var draftMinAir: Int
    @State private var isHovered = false

    init(zone: ZoneSnapshot, isBusy: Bool, onApply: @escaping (ZoneUpdateDraft) -> Void) {
        self.zone = zone
        self.isBusy = isBusy
        self.onApply = onApply
        _draftMode = State(initialValue: zone.mode ?? .auto)
        _draftSetpoint = State(initialValue: zone.setpointCelsius)
        _draftMaxAir = State(initialValue: zone.maxAir)
        _draftMinAir = State(initialValue: zone.minAir)
    }

    private var modeTint: Color { draftMode.tintColor }
    private var isClosed: Bool { draftMode == .close }

    var body: some View {
        HStack(spacing: 0) {
            // Accent bar with subtle glow
            modeTint
                .frame(width: 5)
                .shadow(color: modeTint.opacity(isClosed ? 0 : 0.25), radius: 6, x: 3)

            VStack(alignment: .leading, spacing: 16) {
                // Header
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(zone.name)
                            .font(.title3.weight(.semibold))

                        HStack(spacing: 16) {
                            HStack(spacing: 4) {
                                Image(systemName: "thermometer.medium")
                                    .font(.caption)
                                    .foregroundStyle(.orange)
                                Text(formatTemperature(zone.temperature))
                                    .font(.callout.weight(.medium).monospacedDigit())
                            }
                            HStack(spacing: 4) {
                                Image(systemName: "target")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Text(formatTemperature(zone.setpoint))
                                    .font(.callout.monospacedDigit())
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }

                    Spacer()

                    StatusBadge(
                        text: zone.mode?.displayName ?? "Unknown",
                        icon: zone.mode?.systemImage ?? "questionmark.circle",
                        color: (zone.mode ?? .auto).tintColor
                    )
                }

                Divider().opacity(0.3)

                // Mode
                VStack(alignment: .leading, spacing: 8) {
                    Text("Mode")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.tertiary)

                    HStack(spacing: 5) {
                        ForEach(ZoneMode.allCases) { mode in
                            zoneModeButton(for: mode)
                        }
                    }
                }

                // Controls
                VStack(spacing: 10) {
                    controlRow(label: "Setpoint", icon: "thermometer") {
                        Stepper(value: $draftSetpoint, in: 15...30, step: 0.5) {
                            Text(formatCelsius(draftSetpoint))
                                .font(.callout.weight(.semibold).monospacedDigit())
                                .frame(minWidth: 60, alignment: .trailing)
                        }
                    }
                    controlRow(label: "Max Air", icon: "arrow.up.right") {
                        Stepper(value: $draftMaxAir, in: 0...100, step: 5) {
                            Text("\(draftMaxAir)%")
                                .font(.callout.weight(.semibold).monospacedDigit())
                                .frame(minWidth: 44, alignment: .trailing)
                        }
                    }
                    controlRow(label: "Min Air", icon: "arrow.down.right") {
                        Stepper(value: $draftMinAir, in: 0...100, step: 5) {
                            Text("\(draftMinAir)%")
                                .font(.callout.weight(.semibold).monospacedDigit())
                                .frame(minWidth: 44, alignment: .trailing)
                        }
                    }
                }

                // Actions
                HStack {
                    Button("Apply") {
                        onApply(ZoneUpdateDraft(
                            mode: draftMode,
                            setpointCelsius: draftSetpoint,
                            maxAir: draftMaxAir,
                            minAir: draftMinAir
                        ))
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy || !hasChanges)

                    Button("Reset") { syncFromZone() }
                        .disabled(isBusy || !hasChanges)
                }
            }
            .padding(18)
        }
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(isHovered ? AppColors.bgElevated : AppColors.bgSurface)
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .opacity(isClosed ? 0.55 : 1.0)
        .animation(.easeInOut(duration: 0.2), value: isClosed)
        .animation(.easeInOut(duration: 0.15), value: isHovered)
        .onHover { isHovered = $0 }
        .onChange(of: zone) { _, _ in syncFromZone() }
    }

    // MARK: - Subviews

    private func controlRow<Content: View>(label: String, icon: String, @ViewBuilder content: () -> Content) -> some View {
        HStack {
            Label(label, systemImage: icon)
                .font(.callout)
                .foregroundStyle(.secondary)
            Spacer()
            content()
        }
    }

    private func zoneModeButton(for mode: ZoneMode) -> some View {
        let isSelected = draftMode == mode
        let tint = mode.tintColor
        return Button {
            withAnimation(.snappy(duration: 0.2)) { draftMode = mode }
        } label: {
            VStack(spacing: 3) {
                Image(systemName: mode.systemImage)
                    .font(.caption)
                Text(mode.displayName)
                    .font(.caption2.weight(.medium))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(isSelected ? tint.opacity(0.14) : AppColors.bgElevated.opacity(0.5))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .strokeBorder(isSelected ? tint.opacity(0.3) : AppColors.borderSubtle, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .foregroundStyle(isSelected ? tint : .secondary)
    }

    // MARK: - State

    private var hasChanges: Bool {
        draftMode != (zone.mode ?? .auto)
            || quantizeHalfDegree(draftSetpoint) != quantizeHalfDegree(zone.setpointCelsius)
            || quantizeAirflow(draftMaxAir) != zone.maxAir
            || quantizeAirflow(draftMinAir) != zone.minAir
    }

    private func syncFromZone() {
        draftMode = zone.mode ?? .auto
        draftSetpoint = zone.setpointCelsius
        draftMaxAir = zone.maxAir
        draftMinAir = zone.minAir
    }
}
