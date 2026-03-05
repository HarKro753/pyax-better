import SwiftUI
import AppKit

/// PyAx Assistant - A macOS accessibility event viewer and agent.
///
/// This app connects to a Python bridge process that uses the pyax library
/// to observe accessibility events from the currently focused application
/// and streams them in a chat-style interface.
///
/// The app runs as an "accessory" so it doesn't steal focus from
/// the application being observed.
@main
struct PyAxAssistantApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 600, height: 700)
    }
}

/// App delegate to configure the app as an accessory (non-activating).
/// This prevents the app from stealing focus when users click in other apps.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Accessory policy: app doesn't appear in Dock, doesn't steal focus
        // from the observed app. The window still shows in the window list.
        NSApp.setActivationPolicy(.accessory)
    }
}
