import SwiftUI

struct OverviewView: View {
    @Bindable var model: AppModel

    @State private var draftPower = false
    @State private var draftMode: SystemMode = .cool
    @State private var draftFan: FanSpeed = .auto
    @State private var draftSetpoint = 23.0

    private var activeModeTint: Color {
        draftPower ? draftMode.tintColor : .secondary
    }

    var body: some View {
        Group {
            if let snapshot = model.snapshot {
                ScrollView {
                    VStack(alignment: .leading, spacing: 28) {
                        heroSection(for: snapshot.system)
                        controlsSection(for: snapshot.system)
                        sensorsRow(for: snapshot.system)
                        defaultsSection
                    }
                    .padding(24)
                }
                .onAppear { syncDrafts(with: snapshot.system) }
                .onChange(of: snapshot.system) { _, s in syncDrafts(with: s) }
            } else if model.isLoading {
                ProgressView("Loading iZone status…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(
                    "No Status Available",
                    systemImage: "thermometer.medium.slash",
                    description: Text("Refresh the app after the iZone bridge is reachable.")
                )
            }
        }
        .navigationTitle("Overview")
    }

    // MARK: - Hero

    private func heroSection(for sys: SystemSnapshot) -> some View {
        VStack(spacing: 20) {
            // Mode + power pill
            HStack(spacing: 10) {
                if sys.isOn, let mode = sys.mode {
                    Image(systemName: mode.systemImage)
                        .font(.title3.weight(.medium))
                        .foregroundStyle(mode.tintColor)
                    Text(mode.displayName)
                        .font(.title3.weight(.medium))
                        .foregroundStyle(mode.tintColor)
                }

                Text(sys.isOn ? "On" : "Off")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(sys.isOn ? .green : .secondary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(Capsule().fill((sys.isOn ? Color.green : .secondary).opacity(0.14)))
            }

            // Large setpoint
            Text(formatCelsius(sys.setpointCelsius))
                .font(.system(size: 48, weight: .thin, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(sys.isOn ? .primary : .secondary)
                .shadow(color: (sys.mode?.tintColor ?? .clear).opacity(sys.isOn ? 0.25 : 0), radius: 24)
                .contentTransition(.numericText())

            // Return / Supply / Humidity
            HStack(spacing: 36) {
                statReading(label: "Return", value: formatTemperature(sys.returnAir), color: .orange)
                statReading(label: "Supply", value: formatTemperature(sys.supplyAir), color: .blue)
                if let h = sys.humidity {
                    statReading(label: "Humidity", value: "\(h)%", color: .cyan)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 36)
        .background(
            RadialGradient(
                colors: [(sys.mode?.tintColor ?? .cyan).opacity(sys.isOn ? 0.06 : 0.02), .clear],
                center: .center,
                startRadius: 30,
                endRadius: 240
            )
        )
        .background(AppColors.bgSurface)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func statReading(label: String, value: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.white.opacity(0.35))
            Text(value)
                .font(.callout.weight(.medium))
                .monospacedDigit()
                .foregroundStyle(color)
        }
    }

    // MARK: - Controls

    private func controlsSection(for sys: SystemSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 20) {
            // Power
            HStack {
                HStack(spacing: 10) {
                    Image(systemName: draftPower ? "power.circle.fill" : "power.circle")
                        .font(.title3)
                        .foregroundStyle(draftPower ? .green : .secondary)
                        .contentTransition(.symbolEffect(.replace))
                    Text("Power")
                        .font(.body.weight(.medium))
                }
                Spacer()
                Toggle("", isOn: $draftPower)
                    .toggleStyle(.switch)
                    .tint(.green)
                    .labelsHidden()
            }
            .padding(16)
            .background(AppColors.bgSurface, in: RoundedRectangle(cornerRadius: 12, style: .continuous))

            // Mode
            modeSelector

            // Fan
            fanSelector

            // Setpoint
            HStack {
                Text("Setpoint")
                    .font(.body.weight(.medium))
                Spacer()
                Stepper(value: $draftSetpoint, in: 15...30, step: 0.5) {
                    Text(formatCelsius(draftSetpoint))
                        .font(.title3.weight(.semibold))
                        .monospacedDigit()
                        .contentTransition(.numericText())
                        .frame(minWidth: 72, alignment: .trailing)
                }
            }
            .padding(16)
            .background(AppColors.bgSurface, in: RoundedRectangle(cornerRadius: 12, style: .continuous))

            // Warning
            if let warnings = sys.warnings {
                Label(warnings, systemImage: "exclamationmark.triangle.fill")
                    .font(.callout)
                    .foregroundStyle(.yellow)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.yellow.opacity(0.07), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            // Actions
            HStack {
                Button("Apply Settings") {
                    Task {
                        await model.applySystem(
                            SystemControlDraft(
                                isPoweredOn: draftPower,
                                mode: draftMode,
                                fan: draftFan,
                                setpointCelsius: draftSetpoint
                            )
                        )
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(model.isBusy)

                Button("Reset") { syncDrafts(with: sys) }
                    .disabled(model.isBusy)

                Spacer()

                if let sleep = sys.sleepTimerMinutes {
                    Label("Sleep \(sleep) min", systemImage: "moon.fill")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    // MARK: - Mode Selector

    private var modeSelector: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Mode")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                ForEach(SystemMode.allCases) { mode in
                    systemModeButton(for: mode)
                }
            }
        }
    }

    private func systemModeButton(for mode: SystemMode) -> some View {
        let isSelected = draftMode == mode
        let tint = mode.tintColor
        return Button {
            withAnimation(.snappy(duration: 0.25)) { draftMode = mode }
        } label: {
            VStack(spacing: 8) {
                Image(systemName: mode.systemImage)
                    .font(.title3.weight(.medium))
                    .frame(width: 38, height: 38)
                    .background(
                        Circle().fill(isSelected ? tint.opacity(0.18) : .clear)
                    )
                Text(mode.displayName)
                    .font(.caption.weight(.semibold))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(isSelected ? AppColors.bgElevated : AppColors.bgSurface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(isSelected ? tint.opacity(0.35) : AppColors.borderSubtle, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .foregroundStyle(isSelected ? tint : .secondary)
        .shadow(color: isSelected ? tint.opacity(0.12) : .clear, radius: 10)
    }

    // MARK: - Fan Selector

    private var fanSelector: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Fan Speed")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)

            HStack(spacing: 6) {
                ForEach(FanSpeed.allCases) { fan in
                    fanSpeedButton(for: fan)
                }
            }
        }
    }

    private func fanSpeedButton(for fan: FanSpeed) -> some View {
        let isSelected = draftFan == fan
        return Button {
            withAnimation(.snappy(duration: 0.25)) { draftFan = fan }
        } label: {
            Text(fan.displayName)
                .font(.callout.weight(.medium))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(isSelected ? Color.accentColor.opacity(0.14) : AppColors.bgSurface)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .strokeBorder(isSelected ? Color.accentColor.opacity(0.3) : AppColors.borderSubtle, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .foregroundStyle(isSelected ? .primary : .secondary)
    }

    // MARK: - Sensors

    private func sensorsRow(for sys: SystemSnapshot) -> some View {
        HStack(spacing: 8) {
            if let eco2 = sys.eco2 {
                sensorPill(icon: "leaf.fill", value: "\(eco2) ppm", label: "eCO2", tint: eco2 > 1000 ? .orange : .green)
            }
            if let tvoc = sys.tvoc {
                sensorPill(icon: "aqi.medium", value: "\(tvoc) ppb", label: "TVOC", tint: tvoc > 500 ? .orange : .teal)
            }
            sensorPill(icon: "square.grid.2x2", value: "\(sys.zoneCount)", label: "Zones", tint: .secondary)
            Spacer()
        }
    }

    private func sensorPill(icon: String, value: String, label: String, tint: Color) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(tint)
            Text(value)
                .font(.callout.weight(.medium).monospacedDigit())
            Text(label)
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(AppColors.bgSurface, in: Capsule(style: .continuous))
    }

    // MARK: - Defaults

    private var defaultsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Saved Defaults")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 14) {
                if let saved = model.savedDefaults {
                    HStack(spacing: 6) {
                        StatusBadge(
                            text: saved.modeLabel,
                            icon: SystemMode(rawValue: saved.mode)?.systemImage ?? "questionmark",
                            color: SystemMode(rawValue: saved.mode)?.tintColor ?? .secondary
                        )
                        StatusBadge(text: saved.fanLabel, icon: "fan", color: .secondary)
                        StatusBadge(text: formatTemperature(saved.setpoint), icon: "thermometer", color: .secondary)
                        StatusBadge(text: "\(saved.zones.count) zones", icon: "square.grid.2x2", color: .secondary)
                    }
                } else {
                    Text("No saved defaults yet.")
                        .font(.callout)
                        .foregroundStyle(.tertiary)
                }

                HStack {
                    Button("Save Current Settings") {
                        Task { await model.saveDefaults() }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.isBusy)

                    Button("Restore Saved Defaults") {
                        Task { await model.restoreDefaults() }
                    }
                    .disabled(model.isBusy || model.savedDefaults == nil)
                }
            }
            .padding(16)
            .background(AppColors.bgSurface, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
    }

    // MARK: - Sync

    private func syncDrafts(with sys: SystemSnapshot) {
        draftPower = sys.isOn
        draftMode = sys.mode ?? .cool
        draftFan = sys.fan ?? .auto
        draftSetpoint = sys.setpointCelsius
    }
}
