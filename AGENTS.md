You are a senior developer working on pyax — a macOS Accessibility API toolkit.
The project is a monorepo with a Python library and a Swift macOS companion app.

For Swift and SwiftUI coding rules, load the `swift-rules` skill.

## Project Context

pyax wraps Apple's low-level AXUIElement C API (via pyobjc) into a Pythonic interface.
It provides a CLI tool for inspecting UI trees and observing accessibility events,
plus a WebSocket bridge server that enables the Swift companion app (and AI agents)
to programmatically query and interact with any macOS application's UI.

The Swift companion app (PyAxAssistant) is a floating overlay panel that connects
to the bridge, displays raw event streams, and exposes a command interface.

## Repository Structure

```
pyax-better/
├── AGENTS.md
├── LICENSE
├── README.md
├── .gitignore
├── .opencode/
│   └── skills/
│       ├── swift-rules/           — Swift & SwiftUI coding standards
│       ├── swiftui-expert-skill/  — SwiftUI advanced patterns
│       └── xcode-build/           — xcodebuild & simctl commands
└── packages/
    ├── pyax/                      — Python accessibility library
    └── PyAxAssistant/             — Swift macOS companion app
```

## packages/pyax — Python Accessibility Library

Python client library for the macOS Accessibility API.
Uses a mixin/monkey-patching pattern to inject Pythonic methods onto native AXUIElement objects at import time.

```
pyax/
├── pyproject.toml                 — Hatch config, deps (pyobjc, typer), optional extras [highlight], [bridge]
└── src/
    └── pyax/
        ├── __init__.py            — Public API facade: get_applications, create_observer, start/stop, EVENTS
        ├── __main__.py            — Typer CLI entry point (tree, observe, inspect commands)
        ├── _cli.py                — CLI command implementations (tree dump, observe, inspect)
        ├── _constants.py          — ~110 macOS AX event name strings
        ├── _highlighter.py        — PyQt6 transparent overlay for visual element highlighting
        ├── _mixin.py              — Runtime monkey-patching of Cocoa/AX classes with Python methods
        ├── _observer.py           — AX event observer: CFRunLoop integration, start/stop, callbacks
        ├── _uielement.py          — Core AXUIElement wrapper: attributes, actions, tree traversal, search
        ├── utils.py               — Interactive mouse-based element picker with highlight
        └── bridge/
            ├── __init__.py        — Re-exports server.run as main
            ├── __main__.py        — Allows `python3 -m pyax.bridge`
            └── server.py          — WebSocket bridge: CFRunLoop on main thread, asyncio on background thread
```

### Bridge Architecture

Two-thread design required because macOS AX APIs need CFRunLoop on the main thread:

- **Main thread**: CFRunLoop with timers polling for app changes (500ms) and draining command queue (50ms). All accessibility API calls happen here.
- **Background thread**: asyncio WebSocket server. Incoming commands go to command_queue, outgoing events/responses pulled from event_queue.

### Bridge Command Protocol

8 commands over WebSocket: `get_tree`, `find_elements`, `get_element`, `perform_action`, `set_attribute`, `get_element_at_position`, `get_focused_element`, `get_app_info`.

Request format: `{"type": "command", "id": "<uuid>", "command": "get_tree", ...}`
Response format: `{"type": "response", "id": "<uuid>", "command": "get_tree", ...}`

## packages/PyAxAssistant — Swift macOS Companion App

macOS floating overlay (NSPanel) that connects to the Python bridge via WebSocket.
Displays accessibility event streams and exposes the bridge command interface.

```
PyAxAssistant/
├── Package.swift                          — Swift 6.0, macOS 15+, executable + test targets
├── Sources/PyAxAssistant/
│   ├── PyAxAssistantApp.swift             — App entry point, @Environment injection in AppDelegate
│   ├── Models/
│   │   ├── AppState.swift                 — @Observable state manager, owns all app state
│   │   ├── BridgeConfiguration.swift      — Centralized config (ports, timeouts, limits)
│   │   ├── BridgeError.swift              — Typed error enum
│   │   ├── BridgeMessage.swift            — Typed enum for parsed WebSocket messages
│   │   ├── BridgeResponse.swift           — Sendable response wrapper
│   │   ├── BridgeStatus.swift             — Process lifecycle status enum
│   │   ├── ConnectionStatus.swift         — WebSocket connection status enum
│   │   └── RawMessage.swift               — Identifiable JSON message model
│   ├── Services/
│   │   ├── BridgeMessageParser.swift      — Stateless JSON parsing struct
│   │   ├── PortManager.swift              — Orphan process cleanup utility
│   │   ├── PythonBridgeService.swift      — Python process lifecycle + path resolution
│   │   ├── WebSocketConnection.swift      — Connection lifecycle, reconnection, keep-alive
│   │   └── WebSocketService.swift         — Command/response orchestrator, convenience API
│   └── Views/
│       ├── ContentView.swift              — Main composition, consumes @Environment
│       ├── EventStreamView.swift          — Scrollable message list + empty state
│       ├── FloatingPanel.swift            — NSPanel subclass + controller
│       └── StatusBarView.swift            — Status bar with connection indicator + controls
└── Tests/PyAxAssistantTests/
    ├── AppStateTests.swift
    ├── BridgeConfigurationTests.swift
    ├── BridgeMessageParserTests.swift
    ├── BridgeResponseTests.swift
    └── BridgeStatusTests.swift
```

### How the Two Packages Connect

1. `PyAxAssistant` spawns `python3 -m pyax.bridge` as a child process (`PythonBridgeService`)
2. After a 2-second startup delay, it connects via WebSocket to `ws://localhost:8765` (`WebSocketService`)
3. The bridge streams accessibility events as JSON; PyAxAssistant displays them in `EventStreamView`
4. Commands can be sent through `WebSocketService.sendBridgeCommand()` for UI tree queries and actions
