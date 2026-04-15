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
                    VStack(alignment: .leading, spacing: 24) {
                        metricsGrid(for: snapshot.system)
                        controlsCard(for: snapshot.system)
                        environmentGrid(for: snapshot.system)
                        defaultsCard
                    }
                    .padding(24)
                }
                .onAppear {
                    syncDrafts(with: snapshot.system)
                }
                .onChange(of: snapshot.system) { _, newValue in
                    syncDrafts(with: newValue)
                }
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

    // MARK: - Metrics Grid

    private func metricsGrid(for system: SystemSnapshot) -> some View {
        let cards = [
            ("System", system.isOn ? "On" : "Off", system.isOn ? "power.circle.fill" : "power.circle", system.isOn ? Color.green : Color.secondary),
            ("Setpoint", formatTemperature(system.setpoint), "thermometer", activeModeTint),
            ("Return Air", formatTemperature(system.returnAir), "arrow.down.circle", Color.orange),
            ("Supply Air", formatTemperature(system.supplyAir), "arrow.up.circle", Color.blue),
        ]

        return LazyVGrid(columns: [GridItem(.adaptive(minimum: 190), spacing: 14)], spacing: 14) {
            ForEach(cards, id: \.0) { title, value, image, tint in
                MetricCardView(title: title, value: value, systemImage: image, tint: tint)
            }
        }
    }

    // MARK: - Controls Card

    private func controlsCard(for system: SystemSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionHeader("Controls", icon: "slider.horizontal.3")

            VStack(alignment: .leading, spacing: 20) {
                // Power toggle
                HStack {
                    Label("Power", systemImage: draftPower ? "power.circle.fill" : "power.circle")
                        .font(.callout.weight(.medium))
                        .foregroundStyle(draftPower ? .green : .secondary)

                    Spacer()

                    Toggle("", isOn: $draftPower)
                        .toggleStyle(.switch)
                        .tint(.green)
                        .labelsHidden()
                }

                Divider()

                // Mode selector
                modeSelector

                // Fan selector
                fanSelector

                Divider()

                // Setpoint
                HStack {
                    Text("Setpoint")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(.secondary)

                    Spacer()

                    Stepper(value: $draftSetpoint, in: 15...30, step: 0.5) {
                        Text(formatCelsius(draftSetpoint))
                            .font(.title3.weight(.semibold))
                            .monospacedDigit()
                            .contentTransition(.numericText())
                            .frame(minWidth: 72, alignment: .trailing)
                    }
                }

                if let warnings = system.warnings {
                    Label(warnings, systemImage: "exclamationmark.triangle.fill")
                        .font(.callout)
                        .foregroundStyle(.yellow)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .fill(.yellow.opacity(0.08))
                        )
                }

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

                    Button("Reset") {
                        syncDrafts(with: system)
                    }
                    .disabled(model.isBusy)

                    Spacer()

                    if let sleepTimer = system.sleepTimerMinutes {
                        Label("Sleep \(sleepTimer) min", systemImage: "moon.fill")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(18)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(.ultraThickMaterial)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(.white.opacity(0.06))
            )
        }
    }

    // MARK: - Mode Selector

    private var modeSelector: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Mode")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)

            HStack(spacing: 6) {
                ForEach(SystemMode.allCases) { mode in
                    Button {
                        withAnimation(.snappy(duration: 0.2)) {
                            draftMode = mode
                        }
                    } label: {
                        VStack(spacing: 5) {
                            Image(systemName: mode.systemImage)
                                .font(.body.weight(.medium))
                            Text(mode.displayName)
                                .font(.caption2.weight(.semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(draftMode == mode ? mode.tintColor.opacity(0.15) : .clear)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .strokeBorder(draftMode == mode ? AnyShapeStyle(mode.tintColor.opacity(0.3)) : AnyShapeStyle(.quaternary), lineWidth: 1)
                        )
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(draftMode == mode ? mode.tintColor : .secondary)
                }
            }
        }
    }

    // MARK: - Fan Selector

    private var fanSelector: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Fan Speed")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.secondary)

            HStack(spacing: 6) {
                ForEach(FanSpeed.allCases) { fan in
                    Button {
                        withAnimation(.snappy(duration: 0.2)) {
                            draftFan = fan
                        }
                    } label: {
                        Text(fan.displayName)
                            .font(.caption.weight(.semibold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .fill(draftFan == fan ? Color.accentColor.opacity(0.15) : .clear)
                            )
                            .overlay(
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .strokeBorder(draftFan == fan ? AnyShapeStyle(Color.accentColor.opacity(0.3)) : AnyShapeStyle(.quaternary), lineWidth: 1)
                            )
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(draftFan == fan ? .primary : .secondary)
                }
            }
        }
    }

    // MARK: - Environment Grid

    private func environmentGrid(for system: SystemSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionHeader("Environment", icon: "leaf")

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 10)], spacing: 10) {
                SmallMetricView(
                    label: "Mode",
                    value: system.mode?.displayName ?? "—",
                    icon: system.mode?.systemImage ?? "questionmark",
                    tint: (system.mode ?? .cool).tintColor
                )
                SmallMetricView(
                    label: "Fan",
                    value: system.fan?.displayName ?? "—",
                    icon: "fan",
                    tint: .secondary
                )
                if let humidity = system.humidity {
                    SmallMetricView(
                        label: "Humidity",
                        value: "\(humidity)%",
                        icon: "humidity",
                        tint: .cyan
                    )
                }
                if let eco2 = system.eco2 {
                    SmallMetricView(
                        label: "eCO2",
                        value: "\(eco2) ppm",
                        icon: "leaf.fill",
                        tint: eco2 > 1000 ? .orange : .green
                    )
                }
                if let tvoc = system.tvoc {
                    SmallMetricView(
                        label: "TVOC",
                        value: "\(tvoc) ppb",
                        icon: "aqi.medium",
                        tint: tvoc > 500 ? .orange : .teal
                    )
                }
                SmallMetricView(
                    label: "Zones",
                    value: "\(system.zoneCount)",
                    icon: "square.grid.2x2",
                    tint: .secondary
                )
            }
        }
    }

    // MARK: - Defaults Card

    private var defaultsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionHeader("Saved Defaults", icon: "archivebox")

            VStack(alignment: .leading, spacing: 14) {
                if let saved = model.savedDefaults {
                    HStack(spacing: 8) {
                        StatusBadge(
                            text: saved.modeLabel,
                            icon: SystemMode(rawValue: saved.mode)?.systemImage ?? "questionmark",
                            color: SystemMode(rawValue: saved.mode)?.tintColor ?? .secondary
                        )
                        StatusBadge(
                            text: saved.fanLabel,
                            icon: "fan",
                            color: .secondary
                        )
                        StatusBadge(
                            text: formatTemperature(saved.setpoint),
                            icon: "thermometer",
                            color: .secondary
                        )
                        StatusBadge(
                            text: "\(saved.zones.count) zones",
                            icon: "square.grid.2x2",
                            color: .secondary
                        )
                    }
                } else {
                    Text("No saved defaults yet. Save the current system state so you can restore it later.")
                        .font(.callout)
                        .foregroundStyle(.secondary)
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
            .padding(18)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(.ultraThickMaterial)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(.white.opacity(0.06))
            )
        }
    }

    // MARK: - Sync

    private func syncDrafts(with system: SystemSnapshot) {
        draftPower = system.isOn
        draftMode = system.mode ?? .cool
        draftFan = system.fan ?? .auto
        draftSetpoint = system.setpointCelsius
    }
}
