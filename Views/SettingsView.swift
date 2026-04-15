import SwiftUI

struct SettingsView: View {
    @Bindable var model: AppModel

    var body: some View {
        Form {
            Section("Bridge") {
                TextField("Auto-discover bridge", text: $model.bridgeIPOverride)
                    .textFieldStyle(.roundedBorder)

                Text("Leave this blank to keep using the CLI's discovery and cache logic. Set it only if you want the desktop app to target one bridge IP every time.")
                    .font(.callout)
                    .foregroundStyle(.secondary)

                HStack {
                    Button("Clear Override") {
                        model.clearBridgeIPOverride()
                    }
                    .disabled(model.bridgeIPOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                    Button("Reload Now") {
                        Task {
                            await model.reloadAll(force: true)
                        }
                    }
                    .disabled(model.isBusy)
                }
            }

            Section("Backend") {
                VStack(alignment: .leading, spacing: 10) {
                    Text("CLI Script")
                        .font(.subheadline.weight(.medium))
                    Text(model.resolvedCLIPath)
                        .textSelection(.enabled)
                        .font(.system(.callout, design: .monospaced))
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text("Execution Mode")
                        .font(.subheadline.weight(.medium))
                    Text("The app runs the `izone` script directly, so it follows the script's own shebang and PATH lookup instead of forcing Xcode's Python.")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
    }
}
