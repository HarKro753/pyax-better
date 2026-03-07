import AppKit
import SwiftUI

/// A transparent, click-through, full-screen overlay window that draws
/// colored rectangles over UI elements. Used by the agent to show the user
/// what it's looking at or about to interact with.
final class HighlightOverlayWindow: NSWindow {

    private let _overlayView: HighlightOverlayView

    init() {
        let screenFrame = NSScreen.main?.frame ?? NSRect(x: 0, y: 0, width: 1920, height: 1080)
        self._overlayView = HighlightOverlayView(frame: screenFrame)

        super.init(
            contentRect: screenFrame,
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )

        level = .screenSaver
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        ignoresMouseEvents = true
        contentView = _overlayView
    }

    /// Show highlight rectangles for a given duration, then auto-clear.
    @MainActor
    func showHighlights(_ rects: [HighlightRect], duration: Double) {
        _overlayView.setHighlights(rects)
        orderFrontRegardless()

        Task { @MainActor in
            try? await Task.sleep(for: .seconds(duration))
            clearHighlights()
        }
    }

    /// Remove all highlight rectangles immediately.
    @MainActor
    func clearHighlights() {
        _overlayView.setHighlights([])
        orderOut(nil)
    }
}

// MARK: - Overlay NSView

private final class HighlightOverlayView: NSView {

    private var _highlights: [HighlightRect] = []

    func setHighlights(_ highlights: [HighlightRect]) {
        _highlights = highlights
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }

        context.clear(dirtyRect)

        for highlight in _highlights {
            let rect = convertToScreen(highlight)
            let color = nsColor(from: highlight.color)

            context.setStrokeColor(color.withAlphaComponent(0.9).cgColor)
            context.setLineWidth(2.5)
            context.stroke(rect)

            context.setFillColor(color.withAlphaComponent(0.15).cgColor)
            context.fill(rect)

            if let label = highlight.label, !label.isEmpty {
                drawLabel(label, at: rect, color: color, in: context)
            }
        }
    }

    // MARK: - Private

    private func convertToScreen(_ highlight: HighlightRect) -> NSRect {
        guard let screen = NSScreen.main else {
            return NSRect(x: highlight.x, y: highlight.y, width: highlight.width, height: highlight.height)
        }

        let screenHeight = screen.frame.height
        let flippedY = screenHeight - highlight.y - highlight.height

        return NSRect(
            x: highlight.x,
            y: flippedY,
            width: highlight.width,
            height: highlight.height
        )
    }

    private func nsColor(from name: String) -> NSColor {
        switch name.lowercased() {
        case "red": return .systemRed
        case "green": return .systemGreen
        case "blue": return .systemBlue
        case "yellow": return .systemYellow
        case "orange": return .systemOrange
        case "purple": return .systemPurple
        case "cyan": return .systemTeal
        case "pink": return .systemPink
        default: return .systemBlue
        }
    }

    private func drawLabel(_ text: String, at rect: NSRect, color: NSColor, in context: CGContext) {
        let attributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 10, weight: .semibold),
            .foregroundColor: NSColor.white,
        ]

        let attributedString = NSAttributedString(string: text, attributes: attributes)
        let textSize = attributedString.size()

        let padding: CGFloat = 4
        let labelWidth = textSize.width + padding * 2
        let labelHeight = textSize.height + padding

        let labelRect = NSRect(
            x: rect.minX,
            y: rect.maxY,
            width: labelWidth,
            height: labelHeight
        )

        context.setFillColor(color.withAlphaComponent(0.85).cgColor)
        let labelPath = CGPath(
            roundedRect: labelRect,
            cornerWidth: 3,
            cornerHeight: 3,
            transform: nil
        )
        context.addPath(labelPath)
        context.fillPath()

        let textPoint = NSPoint(
            x: labelRect.minX + padding,
            y: labelRect.minY + (labelHeight - textSize.height) / 2
        )
        attributedString.draw(at: textPoint)
    }
}
