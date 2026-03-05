import SwiftUI
import AppKit

@main
struct PyAxAssistantApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        Settings {
            EmptyView()
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var _panelController: FloatingPanelController?
    private var _appState: AppState?
    private var _webSocket: WebSocketService?
    private var _pythonBridge: PythonBridgeService?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let configuration = BridgeConfiguration.default
        let appState = AppState(configuration: configuration)
        let webSocket = WebSocketService(configuration: configuration)
        let pythonBridge = PythonBridgeService(configuration: configuration)

        self._appState = appState
        self._webSocket = webSocket
        self._pythonBridge = pythonBridge

        let controller = FloatingPanelController()
        controller.show(content:
            ContentView()
                .environment(appState)
                .environment(webSocket)
                .environment(pythonBridge)
        )
        self._panelController = controller
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
