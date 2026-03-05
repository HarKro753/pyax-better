import SwiftUI
import AppKit

/// PyAx Assistant - A macOS accessibility event viewer and agent.
///
/// Runs as a floating overlay panel (like Cluely) that stays on top
/// of all windows with a frosted glass background. Does not steal
/// focus from the application being observed.
@main
struct PyAxAssistantApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        // We use a hidden WindowGroup as a workaround —
        // the actual UI is shown via the floating NSPanel from AppDelegate.
        Settings {
            EmptyView()
        }
    }
}

/// App delegate that creates and manages the floating overlay panel.
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var panelController: FloatingPanelController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Accessory: no Dock icon, doesn't activate over other apps
        NSApp.setActivationPolicy(.accessory)

        // Create and show the floating panel with our SwiftUI content
        let controller = FloatingPanelController()
        controller.show(content: ContentView())
        self.panelController = controller
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
