import AppKit
import SwiftUI

@main
struct IZoneDesktopApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup("iZone Desktop") {
            ContentView(model: model)
                .frame(minWidth: 980, minHeight: 700)
                .preferredColorScheme(.dark)
                .task {
                    await model.loadIfNeeded()
                }
        }
        .defaultSize(width: 1200, height: 780)

        Settings {
            SettingsView(model: model)
                .frame(width: 560)
                .padding(24)
                .preferredColorScheme(.dark)
        }

        .commands {
            CommandMenu("iZone") {
                Button("Refresh Status") {
                    Task {
                        await model.reloadAll(force: true)
                    }
                }
                .keyboardShortcut("r")

                Button("Save Defaults") {
                    Task {
                        await model.saveDefaults()
                    }
                }

                Button("Restore Defaults") {
                    Task {
                        await model.restoreDefaults()
                    }
                }
                .disabled(model.savedDefaults == nil)
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

        let renderer = ImageRenderer(content: AppIconView())
        renderer.scale = 2
        if let image = renderer.nsImage {
            NSApp.applicationIconImage = image
        }
    }
}
