import SwiftUI

struct ZoneCardView: View {
    let zone: ZoneSnapshot
    let isBusy: Bool
    let onApply: (ZoneUpdateDraft) -> Void

    @State private var draftMode: ZoneMode
    @State private var draftSetpoint: Double
    @State private var draftMaxAir: Int
    @State private var draftMinAir: Int

    init(zone: ZoneSnapshot, isBusy: Bool, onApply: @escaping (ZoneUpdateDraft) -> Void) {
        self.zone = zone
        self.isBusy = isBusy
        self.onApply = onApply
        _draftMode = State(initialValue: zone.mode ?? .auto)
        _draftSetpoint = State(initialValue: zone.setpointCelsius)
        _draftMaxAir = State(initialValue: zone.maxAir)
        _draftMinAir = State(initialValue: zone.minAir)
    }

    private var modeTint: Color {
        draftMode.tintColor
    }

    private var isClosed: Bool {
        draftMode == .close
    }

    var body: some View {
        HStack(spacing: 0) {
            // Color accent bar
            modeTint
                .frame(width: 4)

            VStack(alignment: .leading, spacing: 16) {
                // Header
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(zone.name)
                            .font(.headline)

                        HStack(spacing: 14) {
                            Label(formatTemperature(zone.temperature), systemImage: "thermometer.medium")
                                .font(.callout.monospacedDigit())
                                .foregroundStyle(.primary)

                            Label(formatTemperature(zone.setpoint), systemImage: "target")
                                .font(.callout.monospacedDigit())
                                .foregroundStyle(.secondary)
                        }
                    }

                    Spacer()

                    StatusBadge(
                        text: zone.mode?.displayName ?? "Unknown",
                        icon: zone.mode?.systemImage ?? "questionmark.circle",
                        color: (zone.mode ?? .auto).tintColor
                    )
                }

                Divider()

                // Mode selector
                VStack(alignment: .leading, spacing: 8) {
                    Text("Mode")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.tertiary)

                    HStack(spacing: 4) {
                        ForEach(ZoneMode.allCases) { mode in
                            zoneModeButton(for: mode)
                        }
                    }
                }

                // Setpoint & Airflow
                VStack(spacing: 12) {
                    HStack {
                        Label("Setpoint", systemImage: "thermometer")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Stepper(value: $draftSetpoint, in: 15...30, step: 0.5) {
                            Text(formatCelsius(draftSetpoint))
                                .font(.callout.weight(.semibold))
                                .monospacedDigit()
                                .frame(minWidth: 64, alignment: .trailing)
                        }
                    }

                    HStack {
                        Label("Max Air", systemImage: "arrow.up.right")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Stepper(value: $draftMaxAir, in: 0...100, step: 5) {
                            Text("\(draftMaxAir)%")
                                .font(.callout.weight(.semibold))
                                .monospacedDigit()
                                .frame(minWidth: 48, alignment: .trailing)
                        }
                    }

                    HStack {
                        Label("Min Air", systemImage: "arrow.down.right")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Stepper(value: $draftMinAir, in: 0...100, step: 5) {
                            Text("\(draftMinAir)%")
                                .font(.callout.weight(.semibold))
                                .monospacedDigit()
                                .frame(minWidth: 48, alignment: .trailing)
                        }
                    }
                }

                // Actions
                HStack {
                    Button("Apply") {
                        onApply(
                            ZoneUpdateDraft(
                                mode: draftMode,
                                setpointCelsius: draftSetpoint,
                                maxAir: draftMaxAir,
                                minAir: draftMinAir
                            )
                        )
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy || !hasChanges)

                    Button("Reset") {
                        syncFromZone()
                    }
                    .disabled(isBusy || !hasChanges)
                }
            }
            .padding(16)
        }
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(.ultraThickMaterial)
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(.white.opacity(0.06))
        )
        .opacity(isClosed ? 0.6 : 1.0)
        .animation(.easeInOut(duration: 0.25), value: isClosed)
        .onChange(of: zone) { _, _ in
            syncFromZone()
        }
    }

    private func zoneModeButton(for mode: ZoneMode) -> some View {
        let isSelected = draftMode == mode
        let tint = mode.tintColor
        return Button {
            withAnimation(.snappy(duration: 0.2)) {
                draftMode = mode
            }
        } label: {
            VStack(spacing: 3) {
                Image(systemName: mode.systemImage)
                    .font(.caption)
                Text(mode.displayName)
                    .font(.caption2.weight(.medium))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 7)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(isSelected ? tint.opacity(0.15) : .clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .strokeBorder(isSelected ? AnyShapeStyle(tint.opacity(0.3)) : AnyShapeStyle(.quaternary), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .foregroundStyle(isSelected ? tint : .secondary)
    }

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
