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
    private var _chatState: ChatState?
    private var _voiceService: VoiceService?
    private var _highlightWindow: HighlightOverlayWindow?
    private var _agentProcess: AgentProcessService?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let configuration = BridgeConfiguration.default

        let agentProcess = AgentProcessService(configuration: configuration)
        agentProcess.start()

        let chatState = ChatState(configuration: configuration)
        let voiceService = VoiceService()
        let highlightWindow = HighlightOverlayWindow()

        self._agentProcess = agentProcess
        self._chatState = chatState
        self._voiceService = voiceService
        self._highlightWindow = highlightWindow

        chatState.onHighlight = { [weak highlightWindow] rects, duration in
            highlightWindow?.showHighlights(rects, duration: duration)
        }

        chatState.onClearHighlights = { [weak highlightWindow] in
            highlightWindow?.clearHighlights()
        }

        chatState.onSpeak = { [weak voiceService] text, rate in
            voiceService?.speak(text, rate: rate)
        }

        let controller = FloatingPanelController()
        controller.show(content:
            ContentView()
                .environment(chatState)
                .environment(voiceService)
        )
        self._panelController = controller
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    func applicationWillTerminate(_ notification: Notification) {
        _highlightWindow?.clearHighlights()
        _highlightWindow?.close()
        _voiceService?.stopSpeaking()
        _agentProcess?.stop()
    }
}
