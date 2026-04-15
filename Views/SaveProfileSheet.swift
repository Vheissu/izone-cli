import SwiftUI

struct SaveProfileSheet: View {
    let isBusy: Bool
    let onCancel: () -> Void
    let onSave: (String) -> Void

    @State private var profileName = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Save Current Settings")
                .font(.title3.weight(.semibold))

            Text("Create a reusable profile from the live iZone state.")
                .foregroundStyle(.secondary)

            TextField("Profile name", text: $profileName)
                .textFieldStyle(.roundedBorder)
                .onSubmit {
                    submit()
                }

            HStack {
                Spacer()
                Button("Cancel", action: onCancel)
                Button("Save", action: submit)
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy || trimmedProfileName.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 360)
    }

    private var trimmedProfileName: String {
        profileName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func submit() {
        guard !trimmedProfileName.isEmpty else { return }
        onSave(trimmedProfileName)
    }
}
