import SwiftUI

struct ContentView: View {
    @Bindable var model: AppModel

    var body: some View {
        NavigationSplitView {
            List(SidebarSection.allCases, selection: $model.selection) { section in
                Label(section.title, systemImage: section.systemImage)
                    .tag(section)
            }
            .listStyle(.sidebar)
            .navigationTitle("iZone Desktop")
        } detail: {
            ZStack(alignment: .top) {
                detailView

                if let errorState = model.errorState {
                    VStack {
                        ErrorBannerView(error: errorState) {
                            model.errorState = nil
                        }
                        Spacer()
                    }
                    .padding()
                }
            }
            .background(.regularMaterial)
        }
        .toolbar {
            ToolbarItemGroup {
                Button {
                    Task {
                        await model.reloadAll(force: true)
                    }
                } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .keyboardShortcut("r")
                .disabled(model.isBusy)

                if model.isBusy {
                    ProgressView()
                        .controlSize(.small)
                }

                Text("Updated \(model.lastUpdatedLabel)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            ToolbarItem {
                SettingsLink {
                    Label("Settings", systemImage: "gearshape")
                }
            }
        }
    }

    @ViewBuilder
    private var detailView: some View {
        switch model.selection ?? .overview {
        case .overview:
            OverviewView(model: model)
        case .zones:
            ZonesView(model: model)
        case .profiles:
            ProfilesView(model: model)
        }
    }
}
