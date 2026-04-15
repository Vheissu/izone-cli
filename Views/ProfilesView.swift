import SwiftUI

struct ProfilesView: View {
    @Bindable var model: AppModel
    @State private var showingSaveSheet = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Saved Profiles")
                            .font(.title2.weight(.semibold))
                        Text("Manage reusable presets for your iZone system.")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Button {
                        showingSaveSheet = true
                    } label: {
                        Label("Save Current As…", systemImage: "plus.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.isBusy || model.snapshot == nil)
                }

                if model.profiles.isEmpty {
                    ContentUnavailableView(
                        "No Profiles Yet",
                        systemImage: "bookmark.slash",
                        description: Text("Save the current system state to create your first reusable profile.")
                    )
                    .frame(maxWidth: .infinity, minHeight: 320)
                } else {
                    ForEach(model.profiles) { profile in
                        ProfileCardView(
                            profile: profile,
                            isBusy: model.isBusy,
                            onApply: {
                                Task { await model.applyProfile(named: profile.name) }
                            },
                            onDelete: {
                                Task { await model.deleteProfile(named: profile.name) }
                            }
                        )
                    }
                }
            }
            .padding(24)
        }
        .navigationTitle("Profiles")
        .sheet(isPresented: $showingSaveSheet) {
            SaveProfileSheet(
                isBusy: model.isBusy,
                onCancel: { showingSaveSheet = false },
                onSave: { name in
                    Task {
                        await model.saveCurrentProfile(named: name)
                        showingSaveSheet = false
                    }
                }
            )
        }
    }
}
