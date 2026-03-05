import AppKit
import SwiftUI

/// A floating NSPanel that stays on top of all windows, doesn't steal focus,
/// and has a translucent/vibrancy background — like a Cluely-style overlay.
final class FloatingPanel: NSPanel {

    init(contentRect: NSRect) {
        super.init(
            contentRect: contentRect,
            styleMask: [
                .borderless,
                .resizable,
                .fullSizeContentView,
                .nonactivatingPanel,
            ],
            backing: .buffered,
            defer: false
        )

        // Always on top
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

        // No titlebar, draggable by background
        isMovableByWindowBackground = true

        // Don't steal focus
        isFloatingPanel = true
        becomesKeyOnlyIfNeeded = true

        // Translucent background
        isOpaque = false
        backgroundColor = .clear

        // Rounded corners
        hasShadow = true

        // Minimum size
        minSize = NSSize(width: 340, height: 300)

        // Restore position or default to top-right corner
        if let screen = NSScreen.main {
            let screenFrame = screen.visibleFrame
            let x = screenFrame.maxX - contentRect.width - 20
            let y = screenFrame.maxY - contentRect.height - 20
            setFrameOrigin(NSPoint(x: x, y: y))
        }
    }

    // Allow the panel to become key (for scrolling/text input)
    // but don't activate the app
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

/// Manages the floating panel lifecycle and hosts SwiftUI content inside it.
@MainActor
final class FloatingPanelController {
    private var panel: FloatingPanel?

    func show(content: some View) {
        let panel = FloatingPanel(
            contentRect: NSRect(x: 0, y: 0, width: 380, height: 600)
        )

        // Host SwiftUI content in the panel
        let hostingView = NSHostingView(rootView:
            content
                .background(VisualEffectBackground())
        )
        panel.contentView = hostingView

        panel.orderFrontRegardless()
        self.panel = panel
    }

    func close() {
        panel?.close()
        panel = nil
    }
}

/// NSVisualEffectView wrapper for the frosted glass background.
struct VisualEffectBackground: NSViewRepresentable {
    var material: NSVisualEffectView.Material = .hudWindow
    var blendingMode: NSVisualEffectView.BlendingMode = .behindWindow
    var state: NSVisualEffectView.State = .active

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = state
        view.isEmphasized = true
        return view
    }

    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
        nsView.blendingMode = blendingMode
        nsView.state = state
    }
}
