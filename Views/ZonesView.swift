import SwiftUI

struct ZonesView: View {
    @Bindable var model: AppModel

    var body: some View {
        Group {
            if let snapshot = model.snapshot {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        zoneSummary(for: snapshot.zones)

                        ForEach(snapshot.zones) { zone in
                            ZoneCardView(zone: zone, isBusy: model.isBusy) { draft in
                                Task { await model.applyZone(draft, for: zone.index) }
                            }
                        }
                    }
                    .padding(24)
                }
            } else if model.isLoading {
                ProgressView("Loading zones…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView(
                    "No Zones Available",
                    systemImage: "square.grid.2x2",
                    description: Text("The app needs a successful bridge refresh before it can show zone controls.")
                )
            }
        }
        .navigationTitle("Zones")
    }

    private func zoneSummary(for zones: [ZoneSnapshot]) -> some View {
        let open = zones.filter { $0.mode == .open }.count
        let closed = zones.filter { $0.mode == .close }.count
        let auto = zones.filter { $0.mode == .auto }.count

        return HStack(spacing: 14) {
            if open > 0 {
                Label("\(open) Open", systemImage: "circle.fill")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.green)
            }
            if closed > 0 {
                Label("\(closed) Closed", systemImage: "circle.fill")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
            }
            if auto > 0 {
                Label("\(auto) Auto", systemImage: "circle.fill")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.blue)
            }
            Spacer()
        }
        .padding(.bottom, 4)
    }
}
