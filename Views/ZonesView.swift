import SwiftUI

struct ZonesView: View {
    @Bindable var model: AppModel

    var body: some View {
        Group {
            if let snapshot = model.snapshot {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        ForEach(snapshot.zones) { zone in
                            ZoneCardView(zone: zone, isBusy: model.isBusy) { draft in
                                Task {
                                    await model.applyZone(draft, for: zone.index)
                                }
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
}
